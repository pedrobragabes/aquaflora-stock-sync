#!/usr/bin/env python3
"""
Update WooCommerce product images with correct URLs based on category.

This script reads local images from data/images/{category}/ and updates
WooCommerce products with the correct image URLs.

URL Format: https://aquafloragroshop.com.br/wp-content/uploads/produtos/{category}/{sku}.jpg

Usage:
    python scripts/update_woo_image_urls.py --dry-run  # Simulate
    python scripts/update_woo_image_urls.py --category racao  # Specific category
    python scripts/update_woo_image_urls.py --limit 10  # Test with 10 products
    python scripts/update_woo_image_urls.py  # Update all
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple

try:
    from woocommerce import API
except ImportError:
    print("❌ WooCommerce API not installed. Run: pip install woocommerce")
    sys.exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# WooCommerce credentials
WOO_URL = os.getenv("WOO_URL", "")
WOO_CONSUMER_KEY = os.getenv("WOO_CONSUMER_KEY", "")
WOO_CONSUMER_SECRET = os.getenv("WOO_CONSUMER_SECRET", "")

# Paths and URLs
IMAGES_DIR = Path("data/images")
REPORT_DIR = Path("data/reports")
IMAGE_BASE_URL = "https://aquafloragroshop.com.br/wp-content/uploads/produtos"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def init_woo_api() -> API:
    """Initialize WooCommerce API client."""
    if not WOO_URL or not WOO_CONSUMER_KEY or not WOO_CONSUMER_SECRET:
        logger.error("WooCommerce credentials not configured in .env")
        sys.exit(1)
    
    return API(
        url=WOO_URL,
        consumer_key=WOO_CONSUMER_KEY,
        consumer_secret=WOO_CONSUMER_SECRET,
        version="wc/v3",
        timeout=60
    )


def find_images_by_category(category: str = None) -> List[Tuple[str, Path, str]]:
    """
    Find images organized by category.
    Returns list of (sku, local_path, image_url) tuples.
    """
    results = []
    
    if category:
        # Search specific category
        category_dir = IMAGES_DIR / category
        if category_dir.exists() and category_dir.is_dir():
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                for img in category_dir.glob(f"*{ext}"):
                    sku = img.stem
                    url = f"{IMAGE_BASE_URL}/{category}/{img.name}"
                    results.append((sku, img, url))
    else:
        # Search all categories (subdirectories)
        for category_dir in IMAGES_DIR.iterdir():
            if category_dir.is_dir():
                cat_name = category_dir.name
                for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    for img in category_dir.glob(f"*{ext}"):
                        sku = img.stem
                        url = f"{IMAGE_BASE_URL}/{cat_name}/{img.name}"
                        results.append((sku, img, url))
    
    return sorted(results, key=lambda x: x[0])


def find_product_by_sku(wcapi: API, sku: str) -> dict:
    """Find product in WooCommerce by SKU."""
    try:
        response = wcapi.get("products", params={"sku": sku, "per_page": 1})
        if response.status_code == 200:
            products = response.json()
            if products:
                return products[0]
        return None
    except Exception as e:
        logger.error(f"Error searching for SKU {sku}: {e}")
        return None


def update_product_image(wcapi: API, product_id: int, image_url: str) -> bool:
    """Update product with image URL."""
    try:
        data = {
            "images": [
                {
                    "src": image_url
                }
            ]
        }
        response = wcapi.put(f"products/{product_id}", data)
        return response.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Error updating product {product_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Update WooCommerce product images with correct URLs")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without updating")
    parser.add_argument("--category", type=str, help="Update only specific category")
    parser.add_argument("--limit", type=int, help="Limit number of products to update")
    parser.add_argument("--update-stock", action="store_true", help="Also update stock from CSV")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🖼️  WOOCOMMERCE - UPDATE PRODUCT IMAGE URLS")
    print("=" * 80)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No updates will be made")
    
    if args.category:
        print(f"📁 Category: {args.category}")
    else:
        print("📁 Processing all categories")
    
    print(f"🌐 Base URL: {IMAGE_BASE_URL}")
    print("=" * 80)
    print()
    
    # Find images
    logger.info("Finding images by category...")
    images = find_images_by_category(category=args.category)
    
    if not images:
        logger.warning("No images found!")
        return
    
    logger.info(f"Found {len(images)} images")
    
    # Apply limit
    if args.limit and args.limit > 0:
        images = images[:args.limit]
        logger.info(f"Limited to {len(images)} images")
    
    # Group by category for display
    categories = {}
    for sku, path, url in images:
        cat = path.parent.name
        categories[cat] = categories.get(cat, 0) + 1
    
    print()
    print("📋 IMAGES BY CATEGORY:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:20s} : {count} images")
    print()
    
    # Show examples
    print("📋 EXAMPLES (first 10):")
    for sku, path, url in images[:10]:
        cat = path.parent.name
        print(f"  {sku:20s} | {cat:15s} | {url}")
    if len(images) > 10:
        print(f"  ... and {len(images) - 10} more")
    print()
    
    if args.dry_run:
        logger.info("✅ DRY RUN COMPLETE - No updates were made")
        return
    
    # Confirm
    confirm = input("⚠️  Proceed with update? Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        logger.info("❌ Aborted by user")
        return
    print()
    
    # Initialize WooCommerce API
    logger.info("Connecting to WooCommerce...")
    wcapi = init_woo_api()
    
    # Process images
    logger.info("Updating products...")
    print()
    
    results = {
        'updated': [],
        'not_found': [],
        'failed': [],
        'skipped': []
    }
    
    for i, (sku, path, url) in enumerate(images, 1):
        cat = path.parent.name
        
        logger.info(f"[{i}/{len(images)}] Processing {sku} ({cat})...")
        
        # Find product
        product = find_product_by_sku(wcapi, sku)
        
        if not product:
            logger.warning(f"  ⚠️  Product not found in WooCommerce")
            results['not_found'].append(sku)
            continue
        
        product_id = product['id']
        product_name = product['name'][:40]
        
        # Check if image already set
        current_images = product.get('images', [])
        if current_images:
            current_url = current_images[0].get('src', '')
            if url in current_url:
                logger.info(f"  ⏭️  Image already set, skipping")
                results['skipped'].append(sku)
                continue
        
        logger.info(f"  📦 Found: ID={product_id}, Name={product_name}")
        logger.info(f"  🔗 Setting image: {url}")
        
        # Update product
        success = update_product_image(wcapi, product_id, url)
        
        if success:
            logger.info(f"  ✅ Updated successfully")
            results['updated'].append(sku)
        else:
            logger.error(f"  ❌ Update failed")
            results['failed'].append(sku)
        
        # Rate limiting
        time.sleep(0.5)
    
    # Summary
    print()
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Total processed:    {len(images)}")
    print(f"Successfully updated: {len(results['updated'])}")
    print(f"Already correct:    {len(results['skipped'])}")
    print(f"Products not found: {len(results['not_found'])}")
    print(f"Failed:             {len(results['failed'])}")
    print("=" * 80)
    
    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = REPORT_DIR / f"image_url_update_{timestamp}.json"
    
    report = {
        "timestamp": timestamp,
        "category": args.category,
        "total_processed": len(images),
        "base_url": IMAGE_BASE_URL,
        "results": results
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 Report saved: {report_file}")


if __name__ == "__main__":
    main()
