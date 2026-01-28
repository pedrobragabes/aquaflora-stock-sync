#!/usr/bin/env python3
"""
AquaFlora - Image Correction Scraper
Multithreaded scraper for downloading product images and updating CSVs.

USAGE:
    python scrape_correction_images.py --category aquarismo
    python scrape_correction_images.py --category aquarismo --workers 8
    python scrape_correction_images.py --all
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple, List, Dict

import requests

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from src.image_scraper import (
    search_images_duckduckgo,
    search_images_bing,
    validate_image,
    clean_product_name,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path("Correção Imagem")
WOOCOMMERCE_BASE_URL = "https://aquafloragroshop.com.br/wp-content/uploads/produtos"

# Default workers for multithreading
DEFAULT_WORKERS = 6

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


# =============================================================================
# IMAGE DOWNLOAD
# =============================================================================

def download_image(url: str, timeout: int = 15) -> Optional[bytes]:
    """Download image with retry."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        }
        response = requests.get(url, timeout=timeout, headers=headers)
        if response.status_code == 200:
            content = response.content
            if content and len(content) > 5000:  # Minimum 5KB
                return content
    except Exception as e:
        logger.debug(f"Download error: {e}")
    return None


def get_image_extension(content: bytes, url: str) -> str:
    """Detect image extension from content or URL."""
    # Check magic bytes
    if content[:4] == b'\x89PNG':
        return 'png'
    elif content[:3] == b'\xff\xd8\xff':
        return 'jpg'
    elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        return 'webp'
    
    # Fallback to URL extension
    url_lower = url.lower()
    if '.png' in url_lower:
        return 'png'
    elif '.webp' in url_lower:
        return 'webp'
    
    return 'jpg'  # Default


# =============================================================================
# SEARCH STRATEGY
# =============================================================================

def search_product_image(
    name: str,
    brand: str,
    sku: str,
    category: str = "",
    max_candidates: int = 5
) -> Optional[Tuple[bytes, str]]:
    """
    Search for product image using Nome + Marca strategy.
    Returns (image_content, extension) or None.
    
    Strategy:
    1. Nome + Marca
    2. Nome + Marca + SKU (fallback)
    """
    
    # Strategy 1: Nome + Marca
    clean_name = clean_product_name(name)
    clean_brand = clean_product_name(brand)
    
    candidates = search_images_duckduckgo(
        product_name=name,
        brand=brand,
        category=category,
        max_results=max_candidates
    )
    
    # Fallback to Bing if DuckDuckGo fails
    if not candidates:
        candidates = search_images_bing(
            product_name=name,
            brand=brand,
            category=category,
            max_results=max_candidates
        )
    
    # If still no results, try with SKU
    if not candidates and sku:
        query = f"{name} {brand} {sku}".strip()
        candidates = search_images_duckduckgo(
            product_name=query,
            sku=sku,
            brand=brand,
            category=category,
            max_results=max_candidates
        )
    
    # Try to download first valid image
    for candidate in candidates:
        content = download_image(candidate.url)
        if content:
            is_valid, w, h = validate_image(content)
            if is_valid:
                ext = get_image_extension(content, candidate.url)
                return content, ext
    
    return None


# =============================================================================
# CSV PROCESSING
# =============================================================================

def load_csv(csv_path: Path) -> List[Dict]:
    """Load CSV file and return list of products."""
    products = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            products.append(dict(row))
    return products


def save_csv(csv_path: Path, products: List[Dict], fieldnames: List[str]):
    """Save products back to CSV."""
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)


def extract_product_info(row: Dict) -> Tuple[str, str, str]:
    """Extract SKU, Name, and Brand from CSV row."""
    sku = row.get('SKU', '').strip()
    name = row.get('Nome', '').strip()
    
    # Brand can be in 'Marcas' or extracted from tags
    brand = row.get('Marcas', '').strip()
    if not brand:
        # Try to extract from Tags or other columns
        tags = row.get('Tags', '')
        if tags:
            # Usually brand is one of the tags
            tag_list = [t.strip() for t in tags.split(',')]
            if len(tag_list) > 0:
                brand = tag_list[0]
    
    return sku, name, brand


# =============================================================================
# MAIN PROCESSING
# =============================================================================

def process_single_product(
    product: Dict,
    output_dir: Path,
    category: str
) -> Tuple[str, bool, str]:
    """
    Process a single product: search and download image.
    Returns (sku, success, image_path_or_error).
    """
    sku, name, brand = extract_product_info(product)
    
    if not sku or not name:
        return sku, False, "Missing SKU or Name"
    
    # Check if image already exists
    existing = list(output_dir.glob(f"{sku}.*"))
    if existing:
        # Already has image
        ext = existing[0].suffix[1:]  # Remove the dot
        image_url = f"{WOOCOMMERCE_BASE_URL}/{category}/{sku}.{ext}"
        return sku, True, image_url
    
    # Search for image
    logger.info(f"🔍 {sku} - {name[:40]}... (Marca: {brand})")
    
    result = search_product_image(
        name=name,
        brand=brand,
        sku=sku,
        category=category
    )
    
    if not result:
        return sku, False, "No image found"
    
    content, ext = result
    
    # Save image
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"{sku}.{ext}"
    
    with open(image_path, 'wb') as f:
        f.write(content)
    
    image_url = f"{WOOCOMMERCE_BASE_URL}/{category}/{sku}.{ext}"
    logger.info(f"   ✅ Saved: {image_path.name}")
    
    return sku, True, image_url


def process_category(
    category: str,
    workers: int = DEFAULT_WORKERS,
    skip_existing: bool = True
) -> Dict:
    """Process all products in a category."""
    
    # Normalize category name
    category_lower = category.lower()
    category_title = category.title()
    
    csv_path = BASE_DIR / f"{category_title}.csv"
    output_dir = BASE_DIR / category_lower
    
    if not csv_path.exists():
        logger.error(f"❌ CSV not found: {csv_path}")
        return {"error": f"CSV not found: {csv_path}"}
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📂 Processing: {category_title}")
    logger.info(f"📄 CSV: {csv_path}")
    logger.info(f"📁 Output: {output_dir}")
    logger.info(f"🧵 Workers: {workers}")
    logger.info(f"{'='*60}\n")
    
    # Load products
    products = load_csv(csv_path)
    fieldnames = list(products[0].keys()) if products else []
    
    logger.info(f"📦 Total products: {len(products)}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Statistics
    stats = {
        "total": len(products),
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }
    
    # Process products with thread pool
    results = {}
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                process_single_product,
                product,
                output_dir,
                category_lower
            ): product for product in products
        }
        
        for future in as_completed(futures):
            product = futures[future]
            try:
                sku, success, result = future.result()
                results[sku] = (success, result)
                
                if success:
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
                    logger.warning(f"   ❌ {sku}: {result}")
                    
            except Exception as e:
                sku = product.get('SKU', 'unknown')
                results[sku] = (False, str(e))
                stats["failed"] += 1
                logger.error(f"   💥 {sku}: {e}")
    
    # Update CSV with new image URLs
    logger.info(f"\n📝 Updating CSV...")
    
    for product in products:
        sku = product.get('SKU', '').strip()
        if sku in results:
            success, image_url = results[sku]
            if success:
                product['Imagens'] = image_url
    
    save_csv(csv_path, products, fieldnames)
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SUMMARY: {category_title}")
    logger.info(f"{'='*60}")
    logger.info(f"   ✅ Success: {stats['success']}")
    logger.info(f"   ❌ Failed:  {stats['failed']}")
    logger.info(f"   📊 Total:   {stats['total']}")
    logger.info(f"{'='*60}\n")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="AquaFlora - Image Correction Scraper"
    )
    parser.add_argument(
        "--category", "-c",
        type=str,
        help="Category to process (e.g., aquarismo, pesca, pet)"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Process all categories"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of worker threads (default: {DEFAULT_WORKERS})"
    )
    
    args = parser.parse_args()
    
    if not args.category and not args.all:
        parser.print_help()
        print("\n❌ Please specify --category or --all")
        return
    
    print("="*60)
    print("🖼️  AQUAFLORA - IMAGE CORRECTION SCRAPER")
    print("="*60)
    
    if args.all:
        # Find all CSVs in BASE_DIR
        csv_files = list(BASE_DIR.glob("*.csv"))
        categories = [f.stem.lower() for f in csv_files]
        logger.info(f"Found {len(categories)} categories: {', '.join(categories)}")
        
        for category in categories:
            process_category(category, workers=args.workers)
    else:
        process_category(args.category, workers=args.workers)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
