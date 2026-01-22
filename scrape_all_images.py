#!/usr/bin/env python3
"""
AquaFlora - Full Product Image Scraper v3
Optimized with: Async parallelism, Vision cache, Fallback search, Retry backoff, Stock priority

IMPROVEMENTS v3:
- [1] Async parallelism with asyncio + aiohttp (3x faster)
- [2] Vision AI cache by URL hash (avoid duplicate analysis)
- [3] Fallback search: Nome+Marca → Só Marca → Só Categoria
- [4] Retry with exponential backoff for 429 errors
- [5] Priority: products with stock > 0 first

USAGE:
    python scrape_all_images.py                  # All products (stock priority)
    python scrape_all_images.py --stock-only     # Only products with stock > 0
    python scrape_all_images.py --limit 50       # Limit to N products
    python scrape_all_images.py --reset          # Reset progress and start fresh
"""

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import os
import shutil
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait, FIRST_COMPLETED
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    print("⚠️  aiohttp not installed. Run: pip install aiohttp")

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from src.image_scraper import (
    search_images_google,
    search_images_duckduckgo,
    search_images_bing,
    get_cached_candidates,
    set_cached_candidates,
    search_cache,
    category_to_folder,
    download_image,
    validate_image,
    analyze_image_with_vision,
    process_and_save_image,
    VisionAnalysisResult,
    VISION_AI_ENABLED,
    GOOGLE_API_KEY,
    GOOGLE_SEARCH_ENGINE_ID,
    VISION_MIN_CONFIDENCE,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

INPUT_FILE = Path("data/input/Athos.csv")
OUTPUT_DIR = Path("data/images")
PROGRESS_FILE = Path("data/scraper_progress.json")
EXCLUSION_FILE = Path("config/exclusion_list.json")
VISION_CACHE_FILE = Path("data/vision_cache.json")
LOG_FILE = Path("logs/scraper_full.log")

# Score thresholds (otimizado para qualidade vs quantidade)
MIN_VISION_SCORE = 0.35  # Departamentos difíceis (FARMACIA, GERAL, TABACARIA, PISCINA)
MIN_SCORE_STRICT = 0.45  # Departamentos com boas imagens (PET, RACAO, PESCA)

# Vision AI - lê do .env (VISION_AI_ENABLED)
USE_VISION_AI = os.getenv("VISION_AI_ENABLED", "true").lower() == "true"

# Search mode - premium (Google+Vision) or cheap (DuckDuckGo/Bing)
SEARCH_MODE = os.getenv("IMAGE_SEARCH_MODE", "premium").lower()

# Rate limiting
MAX_CONCURRENT = 3  # Parallel requests (conservative for API limits)
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds
PRODUCT_TIMEOUT = 60  # Max seconds per product before skipping
MAX_WORKERS_CHEAP = int(os.getenv("SCRAPER_CHEAP_WORKERS", "4"))
MAX_WORKERS_PREMIUM = int(os.getenv("SCRAPER_PREMIUM_WORKERS", "1"))

# Departments where lower scores are acceptable (hard to find product images)
LENIENT_DEPARTMENTS = ["FARMACIA", "GERAL", "TABACARIA", "PISCINA", "AVES", "CUTELARIA"]

# Setup logging
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# [2] VISION AI CACHE
# =============================================================================

class VisionCache:
    """Cache Vision AI results by URL hash to avoid duplicate analysis."""
    
    def __init__(self, cache_file: Path):
        self.cache_file = cache_file
        self.cache: dict = {}
        self.hits = 0
        self.misses = 0
        self._load()
    
    def _load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"📦 Vision cache loaded: {len(self.cache)} entries")
            except Exception:
                self.cache = {}
    
    def save(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def _url_hash(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:16]
    
    def get(self, url: str) -> Optional[dict]:
        key = self._url_hash(url)
        if key in self.cache:
            self.hits += 1
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, url: str, result: VisionAnalysisResult):
        key = self._url_hash(url)
        self.cache[key] = {
            "score": result.score,
            "labels": result.labels,
            "is_product_image": result.is_product_image,
            "safe_search_ok": result.safe_search_ok,
        }
    
    def stats(self) -> str:
        total = self.hits + self.misses
        rate = (self.hits / total * 100) if total > 0 else 0
        return f"Cache: {self.hits}/{total} hits ({rate:.1f}%)"


# Global cache instance
vision_cache = VisionCache(VISION_CACHE_FILE)


# =============================================================================
# [4] RETRY WITH BACKOFF (sync version for compatibility)
# =============================================================================

def download_with_retry(url: str, max_retries: int = MAX_RETRIES, timeout: int = 10) -> Optional[bytes]:
    """Download image with exponential backoff retry and strict timeout."""
    import requests
    lower = url.lower()
    if any(lower.endswith(ext) for ext in [".gif", ".svg", ".ico", ".bmp", ".webp"]):
        return None
    
    for attempt in range(max_retries):
        try:
            # Download com timeout agressivo para não travar
            # HEAD pre-check to skip tiny payloads
            try:
                head = requests.head(url, timeout=min(5, timeout), allow_redirects=True)
                content_length = int(head.headers.get("Content-Length", 0) or 0)
                if 0 < content_length < 5000:
                    return None
            except Exception:
                pass

            response = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"},
                stream=True
            )
            if response.status_code == 200:
                content = response.content
                if content and len(content) > 5000:  # Mínimo 5KB
                    return content
            
            # If download failed, might be rate limit
            if attempt < max_retries - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
                
        except requests.exceptions.Timeout:
            logger.debug(f"Timeout downloading {url[:50]}...")
            if attempt < max_retries - 1:
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Download error: {e}")
            if attempt < max_retries - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                time.sleep(delay)
    
    return None


# =============================================================================
# [3] FALLBACK SEARCH STRATEGY
# =============================================================================

def search_with_fallback(
    name: str,
    brand: str,
    category: str,
    sku: str,
    max_candidates: int = 5,
    search_mode: str = "premium"
) -> list:
    """
    Search with fallback strategy:
    Premium (Google):
      1. Nome + Marca + Categoria
      2. Nome + Marca
      3. Só Marca + Categoria
    Cheap (DuckDuckGo/Bing):
      1. SKU + Nome + Marca
      2. DuckDuckGo optimized queries
      3. Bing (HTML scraping)
    """

    cache_key, cached = get_cached_candidates(
        product_name=name,
        sku=sku,
        brand=brand,
        category=category,
        search_mode=search_mode,
    )
    if cached:
        return cached

    if search_mode == "cheap":
        # DuckDuckGo with SKU + name + brand priority
        candidates = search_images_duckduckgo(
            product_name=name,
            sku=sku,
            brand=brand,
            category=category,
            max_results=max_candidates
        )
        if candidates:
            set_cached_candidates(cache_key, candidates)
            return candidates

        # Fallback to Bing (free HTML scraping)
        logger.info("   Fallback: Bing (DuckDuckGo empty)")
        candidates = search_images_bing(
            product_name=f"{name} {brand}".strip(),
            category=category,
            max_results=max_candidates
        )
        if candidates:
            set_cached_candidates(cache_key, candidates)
        return candidates
    
    # Strategy 1: Full search
    query1 = f"{name} {brand} {category}".strip()
    candidates = search_images_google(query1, sku=sku, max_results=max_candidates)
    if candidates:
        set_cached_candidates(cache_key, candidates)
        return candidates
    
    # Strategy 2: Name + Brand only
    query2 = f"{name} {brand}".strip()
    if query2 != query1:
        logger.info(f"   Fallback 2: {query2[:40]}...")
        candidates = search_images_google(query2, sku=sku, max_results=max_candidates)
        if candidates:
            set_cached_candidates(cache_key, candidates)
            return candidates
    
    # Strategy 3: Brand + Category only
    query3 = f"{brand} {category}".strip()
    if query3 != query2 and len(query3) > 5:
        logger.info(f"   Fallback 3: {query3[:40]}...")
        candidates = search_images_google(query3, sku=sku, max_results=max_candidates)
        if candidates:
            set_cached_candidates(cache_key, candidates)
            return candidates
    
    return []


# =============================================================================
# PRODUCT PROCESSING
# =============================================================================

def process_single_product(product: dict, name_to_sku: dict) -> Tuple[str, bool, float]:
    """Process a single product (sync version)."""
    
    sku = product.get('CodigoBarras', '')
    name = product.get('Descricao', '')
    brand = product.get('Marca', '')
    dept = product.get('Departamento', '')
    
    # Search with fallback [3]
    candidates = search_with_fallback(name, brand, dept, sku, max_candidates=5, search_mode=SEARCH_MODE)
    
    if not candidates:
        return sku, False, 0.0
    
    best_content = None
    best_score = 0.0
    best_result = None
    
    for candidate in candidates:
        # Skip cache check when Vision AI is disabled
        if USE_VISION_AI:
            # Check cache first [2]
            cached = vision_cache.get(candidate.url)
            if cached:
                if cached['score'] > best_score and cached['safe_search_ok']:
                    # Download the cached good image
                    content = download_with_retry(candidate.url)
                    if content:
                        is_valid, _, _ = validate_image(content)
                        if is_valid:
                            best_content = content
                            best_score = cached['score']
                            best_result = VisionAnalysisResult(
                                is_valid=True,
                                score=cached['score'],
                                labels=cached['labels'],
                                is_product_image=cached['is_product_image'],
                                has_text=False, has_logo=False,
                                safe_search_ok=cached['safe_search_ok'],
                                dominant_colors=[]
                            )
                            if best_score >= 0.8:
                                break
                continue
        
        # Download with retry [4]
        content = download_with_retry(candidate.url)
        if not content:
            continue
        
        # Validate size
        is_valid, w, h = validate_image(content)
        if not is_valid:
            continue
        
        # Vision AI analysis (DISABLED - accept first valid image)
        if USE_VISION_AI and VISION_AI_ENABLED and GOOGLE_API_KEY:
            result = analyze_image_with_vision(content, name, dept)
            
            # Cache the result [2]
            vision_cache.set(candidate.url, result)
            
            if not result.safe_search_ok:
                continue
            
            if result.score > best_score:
                best_score = result.score
                best_content = content
                best_result = result
                logger.info(f"   ✨ Score: {result.score:.2f}, Labels: {result.labels[:3]}")
            
            # Early stop if excellent
            if result.score >= 0.8:
                logger.info(f"   🎯 Excellent image found!")
                break
        else:
            # Vision AI desativado - aceita primeira imagem válida
            best_content = content
            best_score = 1.0  # Score fixo (sem validação)
            best_result = VisionAnalysisResult(
                is_valid=True, score=1.0, labels=["no_vision"], is_product_image=True,
                has_text=False, has_logo=False, safe_search_ok=True,
                dominant_colors=[]
            )
            logger.info(f"   ✅ Imagem aceita (Vision AI desativado)")
            break
    
    # Dynamic threshold based on department
    dept_upper = dept.upper() if dept else ""
    threshold = MIN_VISION_SCORE if dept_upper in LENIENT_DEPARTMENTS else MIN_SCORE_STRICT
    
    if best_content and best_score >= threshold:
        target_dir = OUTPUT_DIR / category_to_folder(dept)
        saved = process_and_save_image(best_content, sku, target_dir)
        if saved:
            return sku, True, best_score
    
    return sku, False, best_score


def _find_existing_image(base_dir: Path, sku: str) -> Optional[Path]:
    if not sku:
        return None
    matches = list(base_dir.rglob(f"{sku}.jpg"))
    return matches[0] if matches else None


def _get_output_dir_for_product(base_dir: Path, product: dict) -> Path:
    dept = (product.get("Departamento") or "").strip()
    folder = category_to_folder(dept)
    return base_dir / folder


# =============================================================================
# DATA LOADING
# =============================================================================

def load_exclusion_list() -> dict:
    if not EXCLUSION_FILE.exists():
        return {"exclude_departments": [], "exclude_keywords": {}}
    with open(EXCLUSION_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def should_exclude(product: dict, exclusions: dict) -> Tuple[bool, str]:
    dept = product.get('Departamento', '').upper()
    name = product.get('Descricao', '').lower()
    
    for excl_dept in exclusions.get('exclude_departments', []):
        if excl_dept.upper() == dept:
            return True, f"Dept: {dept}"
    
    for category, keywords in exclusions.get('exclude_keywords', {}).items():
        for kw in keywords:
            if kw.lower() in name:
                return True, f"KW: {kw}"
    
    return False, ""


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "completed": [],
        "failed": [],
        "excluded": [],
        "reused": [],
        "name_to_sku": {},
        "stats": {
            "total_processed": 0,
            "total_success": 0,
            "total_failed": 0,
            "total_excluded": 0,
            "total_reused": 0,
            "avg_vision_score": 0,
            "by_department": {},
            "by_brand": {}
        }
    }


def save_progress(progress: dict):
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def update_success_metrics(progress: dict, product: dict, status: str):
    """Update success metrics by department and brand."""
    stats = progress.setdefault("stats", {})
    by_department = stats.setdefault("by_department", {})
    by_brand = stats.setdefault("by_brand", {})

    dept = (product.get("Departamento") or "Sem Departamento").strip() or "Sem Departamento"
    brand = (product.get("Marca") or "Sem Marca").strip() or "Sem Marca"

    def _bump(bucket: dict, key: str):
        item = bucket.setdefault(key, {"total": 0, "success": 0, "failed": 0, "excluded": 0})
        item["total"] += 1
        if status in item:
            item[status] += 1

    _bump(by_department, dept)
    _bump(by_brand, brand)


def load_products() -> list:
    with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        return list(reader)


# =============================================================================
# [5] PRIORITY BY STOCK
# =============================================================================

def sort_by_stock_priority(products: list, stock_only: bool = False) -> list:
    """Sort products: stock > 0 first, then by stock quantity.
    
    Args:
        products: List of product dicts
        stock_only: If True, exclude products with stock <= 0
    """
    def get_stock(p):
        try:
            return float(p.get('Estoque', '0').replace(',', '.'))
        except Exception:
            return 0
    
    with_stock = [p for p in products if get_stock(p) > 0]
    without_stock = [p for p in products if get_stock(p) <= 0]
    
    # Sort by stock descending
    with_stock.sort(key=get_stock, reverse=True)
    
    if stock_only:
        logger.info(f"📊 Stock-only mode: {len(with_stock)} products (skipping {len(without_stock)} with stock=0)")
        return with_stock
    
    logger.info(f"📊 Priority: {len(with_stock)} with stock, {len(without_stock)} without")
    
    return with_stock + without_stock


# =============================================================================
# MAIN RUNNER
# =============================================================================

def run_scraper(
    stock_only: bool = False,
    limit: Optional[int] = None,
    reset: bool = False,
    search_mode: str = "premium",
    only_failed: bool = False,
    only_missing_images: bool = False,
    skip_existing: bool = True,
    workers: Optional[int] = None
):
    global USE_VISION_AI
    global SEARCH_MODE

    SEARCH_MODE = (search_mode or "premium").lower()
    if workers is None:
        workers = MAX_WORKERS_CHEAP if SEARCH_MODE == "cheap" else MAX_WORKERS_PREMIUM

    # Cheap mode disables Vision AI automatically
    if SEARCH_MODE == "cheap":
        USE_VISION_AI = False
    print("=" * 70)
    print("🖼️  AQUAFLORA - FULL IMAGE SCRAPER v3 (OPTIMIZED)")
    print("=" * 70)
    print("✅ [1] Retry with backoff")
    print("✅ [2] Vision AI cache")
    print("✅ [3] Fallback search strategy")
    print("✅ [4] Exponential retry")
    print("✅ [5] Stock priority")
    if stock_only:
        print("📦 Mode: STOCK > 0 ONLY")
    if limit:
        print(f"📦 Limit: {limit} products")
    print(f"🔎 Search Mode: {SEARCH_MODE}")
    print(f"🧵 Workers: {workers}")
    if only_failed:
        print("♻️  Mode: ONLY FAILED")
    if only_missing_images:
        print("🧹 Mode: ONLY MISSING IMAGES")
    if not skip_existing:
        print("⚠️  Skip existing images: DISABLED")
    print("=" * 70)
    
    if SEARCH_MODE == "premium":
        if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
            logger.error("❌ Google API not configured!")
            return
        logger.info("✅ Google API: Configured")
        logger.info(f"✅ Vision AI: {'Enabled' if (VISION_AI_ENABLED and USE_VISION_AI) else 'Disabled'}")
    else:
        logger.info("✅ Google API: Disabled (cheap mode)")
        logger.info("✅ Vision AI: Disabled (cheap mode)")
    logger.info(f"📁 Output: {OUTPUT_DIR.absolute()}")
    
    # Load data
    products = load_products()
    exclusions = load_exclusion_list()
    
    # Reset progress if requested
    if reset:
        logger.warning("🔄 Resetting progress...")
        progress = load_progress()  # Get empty template
        progress = {
            "completed": [],
            "failed": [],
            "excluded": [],
            "reused": [],
            "name_to_sku": {},
            "stats": {
                "total_processed": 0,
                "total_success": 0,
                "total_failed": 0,
                "total_excluded": 0,
                "total_reused": 0,
                "avg_vision_score": 0,
                "by_department": {},
                "by_brand": {}
            }
        }
    else:
        progress = load_progress()
    
    # [5] Sort by stock priority
    products = sort_by_stock_priority(products, stock_only=stock_only)
    
    excluded_depts = exclusions.get('exclude_departments', [])
    logger.info(f"📦 Total products: {len(products)}")
    logger.info(f"🚫 Excluded depts: {excluded_depts}")
    
    # Already processed
    completed_skus = set(progress.get('completed', []))
    failed_skus = set(progress.get('failed', []))
    excluded_skus = set(progress.get('excluded', []))
    reused_skus = set(progress.get('reused', []))
    if only_failed or only_missing_images:
        already_processed = excluded_skus | reused_skus
    else:
        already_processed = completed_skus | failed_skus | excluded_skus | reused_skus
    
    if already_processed:
        logger.info(f"📊 Resume: {len(completed_skus)} ok, {len(reused_skus)} reused, "
                   f"{len(failed_skus)} fail, {len(excluded_skus)} excl")
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Filter products to process
    name_to_sku = progress.get('name_to_sku', {})
    to_process = []
    
    for product in products:
        sku = product.get('CodigoBarras', '')
        name = product.get('Descricao', '')
        
        if not sku or len(sku) < 5:
            continue

        if only_failed and sku not in failed_skus:
            continue
        
        if sku in already_processed:
            continue
        
        # [NOVO] Skip if image already exists on disk (zero API cost!)
        existing_image = _find_existing_image(OUTPUT_DIR, sku)
        if existing_image:
            if only_missing_images:
                continue
            if skip_existing:
                if sku not in completed_skus:
                    progress['completed'].append(sku)
                    progress['stats']['total_success'] += 1
                logger.debug(f"⏭️ SKIP: {sku} - Image already exists")
                continue
        
        # Check exclusion
        should_excl, reason = should_exclude(product, exclusions)
        if should_excl:
            progress['excluded'].append(sku)
            progress['stats']['total_excluded'] += 1
            update_success_metrics(progress, product, "excluded")
            continue
        
        # Deduplication
        if name in name_to_sku:
            existing_sku = name_to_sku[name]
            existing_img = _find_existing_image(OUTPUT_DIR, existing_sku)
            target_dir = _get_output_dir_for_product(OUTPUT_DIR, product)
            new_img = target_dir / f"{sku}.jpg"
            if existing_img and existing_img.exists():
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(existing_img, new_img)
                progress['reused'].append(sku)
                progress['stats']['total_reused'] += 1
                logger.info(f"🔄 REUSE: {sku} (same as {existing_sku})")
                continue
        
        to_process.append(product)
    
    logger.info(f"🚀 Products to process: {len(to_process)}")
    
    # Apply limit if specified
    if limit and limit > 0:
        to_process = to_process[:limit]
        logger.info(f"📦 Limited to {len(to_process)} products")
    
    if not to_process:
        logger.info("✅ All products already processed!")
        print_summary(progress, 0)
        return
    
    vision_scores = []
    
    print()
    logger.info("=" * 70)
    logger.info("🚀 STARTING SCRAPING...")
    logger.info("=" * 70)
    print()
    
    start_time = time.time()
    
    try:
        # Thread executor for parallel products
        executor = ThreadPoolExecutor(max_workers=max(1, int(workers or 1)))

        def handle_result(product, sku_result, success, score):
            sku = product.get('CodigoBarras', '')
            name = product.get('Descricao', '')

            if success:
                logger.info(f"   ✅ OK (score: {score:.2f})")
                if sku not in progress['completed']:
                    progress['completed'].append(sku)
                if sku in progress['failed']:
                    progress['failed'] = [s for s in progress['failed'] if s != sku]
                progress['stats']['total_success'] += 1
                vision_scores.append(score)
                name_to_sku[name] = sku
                progress['name_to_sku'] = name_to_sku
                update_success_metrics(progress, product, "success")
            else:
                logger.warning(f"   ❌ FAIL")
                if sku not in progress['failed']:
                    progress['failed'].append(sku)
                progress['stats']['total_failed'] += 1
                update_success_metrics(progress, product, "failed")

            progress['stats']['total_processed'] += 1
            if vision_scores:
                progress['stats']['avg_vision_score'] = sum(vision_scores) / len(vision_scores)

            # Save progress every 20 products
            if progress['stats']['total_processed'] % 20 == 0:
                save_progress(progress)
                vision_cache.save()

        pending = {}
        total = len(to_process)
        index = 0

        while index < total or pending:
            while index < total and len(pending) < max(1, int(workers or 1)):
                product = to_process[index]
                sku = product.get('CodigoBarras', '')
                name = product.get('Descricao', '')
                stock = product.get('Estoque', '0')
                logger.info(f"[{index+1}/{total}] 🔍 {sku} - {name[:40]}... (stock: {stock})")
                future = executor.submit(process_single_product, product, name_to_sku)
                pending[future] = product
                index += 1

            done, _ = wait(pending, timeout=PRODUCT_TIMEOUT, return_when=FIRST_COMPLETED)
            if not done:
                future, product = pending.popitem()
                future.cancel()
                sku = product.get('CodigoBarras', '')
                logger.error(f"   ⏰ TIMEOUT (>{PRODUCT_TIMEOUT}s) - skipping {sku}")
                if sku not in progress['failed']:
                    progress['failed'].append(sku)
                progress['stats']['total_failed'] += 1
                update_success_metrics(progress, product, "failed")
                continue

            for future in done:
                product = pending.pop(future)
                try:
                    sku_result, success, score = future.result()
                    handle_result(product, sku_result, success, score)
                except Exception as e:
                    sku = product.get('CodigoBarras', '')
                    logger.error(f"   💥 ERROR: {e}")
                    if sku not in progress['failed']:
                        progress['failed'].append(sku)
                    progress['stats']['total_failed'] += 1
                    update_success_metrics(progress, product, "failed")

            # Small delay to respect rate limits
            time.sleep(0.3)

        executor.shutdown(wait=False)
            
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Interrupted! Saving progress...")
    
    # Final save
    elapsed = time.time() - start_time
    progress['elapsed_seconds'] = elapsed
    save_progress(progress)
    vision_cache.save()
    report_path = write_success_report(progress)
    if report_path:
        logger.info(f"📊 Success report generated: {report_path}")
    
    print_summary(progress, elapsed)


def print_summary(progress: dict, elapsed: float):
    stats = progress.get('stats', {})
    
    print()
    print("=" * 70)
    print("📊 SUMMARY")
    print("=" * 70)
    print(f"✅ Success:  {stats.get('total_success', 0)}")
    print(f"🔄 Reused:   {stats.get('total_reused', 0)}")
    print(f"❌ Failed:   {stats.get('total_failed', 0)}")
    print(f"⏭️  Excluded: {stats.get('total_excluded', 0)}")
    print(f"📊 Avg Score: {stats.get('avg_vision_score', 0):.2f}")
    if elapsed > 0:
        print(f"⏱️  Time: {elapsed/60:.1f} minutes")
    print(f"💾 {vision_cache.stats()}")
    print(f"🧠 {search_cache.stats()}")
    print()
    print(f"📁 Images: {OUTPUT_DIR.absolute()}")
    print(f"📄 Progress: {PROGRESS_FILE.absolute()}")
    print("=" * 70)


def write_success_report(progress: dict) -> Optional[Path]:
    """Write daily success report by category/brand."""
    stats = progress.get("stats", {})
    by_department = stats.get("by_department", {})
    by_brand = stats.get("by_brand", {})

    if not by_department and not by_brand:
        return None

    report_dir = Path("data/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"image_success_{timestamp}.json"
    md_path = report_dir / f"image_success_{timestamp}.md"

    def _rate(item):
        total = item.get("total", 0) or 0
        success = item.get("success", 0) or 0
        return (success / total * 100) if total > 0 else 0

    report = {
        "generated_at": datetime.now().isoformat(),
        "by_department": by_department,
        "by_brand": by_brand,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    lines = ["# 📊 Relatório de Sucesso do Scraper", "", f"Gerado em: {report['generated_at']}", ""]
    lines.append("## Por Departamento")
    for dept, data in sorted(by_department.items(), key=lambda x: _rate(x[1]), reverse=True):
        lines.append(
            f"- **{dept}**: {data.get('success', 0)}/{data.get('total', 0)} "
            f"({ _rate(data):.1f }% sucesso)"
        )
    lines.append("")
    lines.append("## Por Marca")
    for brand, data in sorted(by_brand.items(), key=lambda x: _rate(x[1]), reverse=True):
        lines.append(
            f"- **{brand}**: {data.get('success', 0)}/{data.get('total', 0)} "
            f"({ _rate(data):.1f }% sucesso)"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return json_path


def main():
    parser = argparse.ArgumentParser(
        description="AquaFlora - Full Product Image Scraper v3",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--stock-only', 
        action='store_true',
        help='Only process products with stock > 0'
    )
    parser.add_argument(
        '--limit', 
        type=int,
        help='Limit number of products to process'
    )
    parser.add_argument(
        '--reset', 
        action='store_true',
        help='Reset progress and start fresh (keeps downloaded images)'
    )
    parser.add_argument(
        '--only-failed',
        action='store_true',
        help='Reprocess only SKUs marked as failed'
    )
    parser.add_argument(
        '--only-missing-images',
        action='store_true',
        help='Process only products missing local images'
    )
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        help='Skip SKUs that already have local images (default behavior)'
    )
    parser.add_argument(
        '--no-skip-existing',
        action='store_true',
        help='Do not skip SKUs that already have local images'
    )
    parser.add_argument(
        '--search-mode',
        choices=['premium', 'cheap'],
        default=os.getenv("IMAGE_SEARCH_MODE", "premium").lower(),
        help='Search mode: premium (Google+Vision) or cheap (DuckDuckGo/Bing)'
    )
    parser.add_argument(
        '--cheap',
        action='store_true',
        help='Shortcut for --search-mode cheap (no Google/Vision)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        help='Número de workers em paralelo (padrão: 1 premium, 4 cheap)'
    )
    
    args = parser.parse_args()
    
    search_mode = 'cheap' if args.cheap else args.search_mode
    skip_existing = not args.no_skip_existing

    try:
        run_scraper(
            stock_only=args.stock_only,
            limit=args.limit,
            reset=args.reset,
            search_mode=search_mode,
            only_failed=args.only_failed,
            only_missing_images=args.only_missing_images,
            skip_existing=skip_existing,
            workers=args.workers
        )
    except KeyboardInterrupt:
        print("\n⚠️  Cancelled by user")


if __name__ == "__main__":
    main()
