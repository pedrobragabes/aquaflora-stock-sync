"""
AquaFlora Stock Sync - Image Scraper Module
Search and download product images using Google Custom Search (primary) 
with DuckDuckGo/Bing as fallback.
"""

import logging
import os
import random
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple

import requests

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False

try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

# Google Custom Search API (primary - most reliable)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID", "")

# Default configuration values
MIN_IMAGE_SIZE = 400  # Reduced from 600 to allow more flexibility
MAX_DIMENSION = 1200  # Maximum dimension (will resize if larger)
JPEG_QUALITY = 85
TIMEOUT_SECONDS = 15
SLEEP_MIN = 0.3
SLEEP_MAX = 1.0
MAX_FILE_SIZE_KB = 5  # Minimum file size to be valid

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ImageCandidate:
    """Represents an image candidate found during search."""
    url: str
    thumbnail: str
    title: str
    source: str
    width: int = 0
    height: int = 0


# =============================================================================
# TEXT PROCESSING (Reused from legacy scraper)
# =============================================================================

def clean_product_name(name: str) -> str:
    """
    Clean product name for search queries.
    Removes promotional text, special characters, and normalizes whitespace.
    
    Reused from: Scraping Images Old/src/scraper.py
    """
    if not name:
        return ""
    
    # Stopwords to remove (promotional text)
    stopwords = [
        r"\b(promoção|promocao|oferta|off|desconto|frete grátis|frete gratis)\b",
        r"\b(novo|lançamento|lancamento)\b",
        r"\b(\d+%\s*off)\b",
        r"[!@#$*]",
    ]
    
    s = name.lower()
    for pat in stopwords:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)
    
    return re.sub(r"\s+", " ", s).strip()


def is_bad_image_url(url: str) -> bool:
    """
    Check if URL is likely a bad image (placeholder, logo, etc).
    
    Reused from: Scraping Images Old/src/scraper.py
    """
    bad_tokens = [
        "sprite", "icon", "logo", "placeholder", "blank",
        "spinner", "loading", "1x1", "pixel", "favicon", "avatar",
        "banner", "ad", "advertisement", "tracking", "analytics"
    ]
    u = url.lower()
    return any(tok in u for tok in bad_tokens)


# =============================================================================
# HTTP HELPERS
# =============================================================================

def random_headers() -> dict:
    """Return HTTP headers with random User-Agent."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }


# =============================================================================
# SEARCH ENGINES
# =============================================================================

def search_images_google(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 1  # Default to 1 - first result is usually best
) -> List[ImageCandidate]:
    """
    Search images using Google Custom Search API.
    Primary search engine - most reliable results.
    
    Cost: ~$5 per 1000 queries
    """
    if not GOOGLE_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        logger.debug("Google API not configured, skipping")
        return []
    
    candidates = []
    clean_name = clean_product_name(product_name)
    
    if not clean_name:
        return []
    
    # Build query - product name + category for better results
    if category and category != "SEM_CATEGORIA":
        query = f"{clean_name} {category}"
    else:
        query = clean_name
    
    try:
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
        
        # Google Custom Search API
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_SEARCH_ENGINE_ID,
            "q": query,
            "searchType": "image",
            "num": min(max_results * 2, 10),  # Fetch more to filter
            "imgSize": "large",
            "imgType": "photo",
            "safe": "off",
        }
        
        resp = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
        
        if resp.status_code == 429:
            logger.warning("Google API rate limit reached")
            return []
        
        if resp.status_code != 200:
            logger.warning(f"Google API error: {resp.status_code}")
            return []
        
        data = resp.json()
        items = data.get("items", [])
        
        for item in items:
            image_url = item.get("link", "")
            
            if not image_url or is_bad_image_url(image_url):
                continue
            
            # Get image metadata
            image_info = item.get("image", {})
            
            candidates.append(ImageCandidate(
                url=image_url,
                thumbnail=item.get("image", {}).get("thumbnailLink", image_url),
                title=item.get("title", ""),
                source="google",
                width=image_info.get("width", 0),
                height=image_info.get("height", 0),
            ))
            
            if len(candidates) >= max_results:
                break
        
        if candidates:
            logger.info(f"Google found {len(candidates)} image(s) for: {query[:50]}")
        
    except Exception as e:
        logger.warning(f"Google search error: {e}")
    
    return candidates

def search_images_duckduckgo(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 6
) -> List[ImageCandidate]:
    """
    Search images using DuckDuckGo.
    
    Strategy (in order of specificity):
    1. Product name + SKU
    2. Product name + category
    3. EAN barcode (if available)
    4. Just product name
    """
    if not HAS_DDGS:
        logger.warning("duckduckgo-search not installed, skipping DuckDuckGo search")
        return []
    
    candidates = []
    queries = []
    
    clean_name = clean_product_name(product_name)
    
    # Build query list in order of preference
    if clean_name and sku:
        queries.append(f"{clean_name} {sku}")
    
    if clean_name and category:
        queries.append(f"{clean_name} {category}")
    
    if ean and len(ean) >= 8:
        queries.append(f'"{ean}"')
    
    if clean_name and len(clean_name) >= 5:
        queries.append(clean_name)
    
    # Try each query until we find results
    for query in queries:
        try:
            time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
            
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    keywords=query,
                    region="br-pt",
                    safesearch="off",
                    size="Medium",
                    type_image="photo",
                    max_results=max_results * 2  # Fetch more to filter bad ones
                ))
            
            for r in results:
                if not isinstance(r, dict):
                    continue
                
                url = r.get("image", "")
                if not url or is_bad_image_url(url):
                    continue
                
                candidates.append(ImageCandidate(
                    url=url,
                    thumbnail=r.get("thumbnail", url),
                    title=r.get("title", ""),
                    source="duckduckgo",
                    width=r.get("width", 0),
                    height=r.get("height", 0),
                ))
                
                if len(candidates) >= max_results:
                    break
            
            if candidates:
                logger.info(f"DuckDuckGo found {len(candidates)} images for query: {query}")
                break
                
        except Exception as e:
            logger.warning(f"DuckDuckGo search error for '{query}': {e}")
            continue
    
    return candidates[:max_results]


def search_images_bing(
    product_name: str,
    category: str = "",
    max_results: int = 6
) -> List[ImageCandidate]:
    """
    Search images using Bing as fallback.
    Uses HTML scraping since there's no free official API.
    """
    candidates = []
    clean_name = clean_product_name(product_name)
    
    if not clean_name:
        return []
    
    # Build query
    query = clean_name
    if category:
        query = f"{clean_name} {category}"
    
    try:
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
        
        # Bing Images search URL
        search_url = "https://www.bing.com/images/search"
        params = {
            "q": query,
            "form": "HDRSC2",
            "first": "1",
            "tsc": "ImageBasicHover",
        }
        
        session = requests.Session()
        session.headers.update(random_headers())
        
        resp = session.get(search_url, params=params, timeout=TIMEOUT_SECONDS)
        
        if resp.status_code != 200:
            logger.warning(f"Bing returned status {resp.status_code}")
            return []
        
        # Extract image URLs via regex (Bing uses murl:"URL" format)
        pattern = r'murl":"(https?://[^"]+)"'
        matches = re.findall(pattern, resp.text)
        
        seen = set()
        for url in matches:
            if url in seen:
                continue
            seen.add(url)
            
            if is_bad_image_url(url):
                continue
            
            # Decode escaped characters
            url = url.replace("\\u002f", "/").replace("\\/", "/")
            
            candidates.append(ImageCandidate(
                url=url,
                thumbnail=url,
                title="",
                source="bing",
                width=0,
                height=0,
            ))
            
            if len(candidates) >= max_results:
                break
        
        if candidates:
            logger.info(f"Bing found {len(candidates)} images for query: {query}")
        
    except Exception as e:
        logger.warning(f"Bing search error for '{query}': {e}")
    
    return candidates


def search_images(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 1  # Default to 1 - first result is usually best
) -> List[ImageCandidate]:
    """
    Main search function with cascade:
    1. Google Custom Search (if API key configured) - most reliable
    2. DuckDuckGo (free, decent quality)
    3. Bing scraping (last resort)
    """
    candidates = []
    
    # 1. Try Google first (if configured)
    if GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
        candidates = search_images_google(
            product_name=product_name,
            sku=sku,
            ean=ean,
            category=category,
            max_results=max_results
        )
        if candidates:
            return candidates
    
    # 2. Fallback to DuckDuckGo
    candidates = search_images_duckduckgo(
        product_name=product_name,
        sku=sku,
        ean=ean,
        category=category,
        max_results=max_results
    )
    
    if candidates:
        return candidates
    
    # 3. Last resort: Bing scraping
    logger.info(f"DuckDuckGo found nothing, trying Bing for SKU {sku}")
    candidates = search_images_bing(
        product_name=product_name,
        category=category,
        max_results=max_results
    )
    
    return candidates


# =============================================================================
# DOWNLOAD & VALIDATION
# =============================================================================

def download_image(url: str, timeout: int = TIMEOUT_SECONDS) -> Optional[bytes]:
    """Download image and return raw bytes."""
    try:
        session = requests.Session()
        session.headers.update(random_headers())
        
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        
        if resp.status_code != 200:
            return None
        
        content_type = resp.headers.get("Content-Type", "").lower()
        
        # Verify it's actually an image
        if "image" not in content_type and "octet-stream" not in content_type:
            if "text/html" in content_type:
                return None
        
        return resp.content
        
    except Exception as e:
        logger.debug(f"Download failed for {url}: {e}")
        return None


def validate_image(
    content: bytes,
    min_size: int = MIN_IMAGE_SIZE
) -> Tuple[bool, int, int]:
    """
    Validate image has minimum resolution.
    Returns (is_valid, width, height).
    """
    if not content or len(content) < MAX_FILE_SIZE_KB * 1024:
        return False, 0, 0
    
    if not HAS_PILLOW:
        # Can't validate without Pillow, assume it's OK
        return True, 0, 0
    
    try:
        img = Image.open(BytesIO(content))
        w, h = img.size
        
        if w < min_size or h < min_size:
            logger.debug(f"Image too small: {w}x{h} (min: {min_size})")
            return False, w, h
        
        return True, w, h
        
    except Exception as e:
        logger.debug(f"Image validation failed: {e}")
        return False, 0, 0


def process_and_save_image(
    content: bytes,
    sku: str,
    output_dir: Path,
    max_dimension: int = MAX_DIMENSION,
    quality: int = JPEG_QUALITY
) -> Optional[Path]:
    """
    Process image (resize, convert to JPEG) and save to disk.
    Returns path to saved file or None on error.
    """
    if not HAS_PILLOW:
        logger.warning("Pillow not installed - saving without processing")
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{sku}.jpg"
        with open(out_path, "wb") as f:
            f.write(content)
        return out_path
    
    try:
        img = Image.open(BytesIO(content))
        
        # Convert to RGB if necessary
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        w, h = img.size
        
        # Resize if too large
        if max(w, h) > max_dimension:
            ratio = max_dimension / max(w, h)
            img = img.resize(
                (int(w * ratio), int(h * ratio)),
                Image.Resampling.LANCZOS
            )
            w, h = img.size
        
        # Create square canvas with white background
        max_side = max(w, h)
        background = Image.new("RGB", (max_side, max_side), (255, 255, 255))
        offset = ((max_side - w) // 2, (max_side - h) // 2)
        background.paste(img, offset)
        
        # Save
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{sku}.jpg"
        background.save(out_path, "JPEG", quality=quality, optimize=True)
        
        logger.info(f"Saved processed image: {out_path}")
        return out_path
        
    except Exception as e:
        logger.error(f"Error processing image for SKU {sku}: {e}")
        return None


def download_and_validate(
    url: str,
    min_size: int = MIN_IMAGE_SIZE
) -> Tuple[Optional[bytes], int, int]:
    """
    Download image and validate resolution.
    Returns (content, width, height) or (None, 0, 0) on failure.
    """
    content = download_image(url)
    if not content:
        return None, 0, 0
    
    is_valid, w, h = validate_image(content, min_size)
    if not is_valid:
        return None, w, h
    
    return content, w, h


# =============================================================================
# HIGH-LEVEL API
# =============================================================================

def search_and_get_thumbnails(
    product_name: str,
    sku: str = "",
    ean: str = "",
    category: str = "",
    max_results: int = 6
) -> List[dict]:
    """
    Search for images and return list of candidates with metadata.
    Used by the curator service for displaying options to user.
    """
    candidates = search_images(
        product_name=product_name,
        sku=sku,
        ean=ean,
        category=category,
        max_results=max_results
    )
    
    return [
        {
            "url": c.url,
            "thumbnail": c.thumbnail,
            "title": c.title,
            "source": c.source,
            "width": c.width,
            "height": c.height,
        }
        for c in candidates
    ]
