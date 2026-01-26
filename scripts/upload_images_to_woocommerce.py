#!/usr/bin/env python3
"""
Upload product images to WooCommerce.

This script uploads images from data/images to WordPress media library
and updates the product with the image URL.

Usage:
    python scripts/upload_images_to_woocommerce.py --dry-run  # Simulate
    python scripts/upload_images_to_woocommerce.py            # Upload all
    python scripts/upload_images_to_woocommerce.py --sku 7891234567890  # Specific SKU
    python scripts/upload_images_to_woocommerce.py --category racao  # Specific category
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict
import mimetypes

try:
    from woocommerce import API
except ImportError:
    print("❌ WooCommerce API not installed. Run: pip install woocommerce")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("❌ Requests not installed. Run: pip install requests")
    sys.exit(1)

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# WooCommerce credentials from environment
WOO_URL = os.getenv("WOO_URL", "")
WOO_CONSUMER_KEY = os.getenv("WOO_CONSUMER_KEY", "")
WOO_CONSUMER_SECRET = os.getenv("WOO_CONSUMER_SECRET", "")

# Paths
IMAGES_DIR = Path("data/images")
REPORT_DIR = Path("data/reports")

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


def upload_image_to_wordpress(image_path: Path, sku: str) -> str:
    """Upload image to WordPress media library and return URL."""
    # WordPress REST API endpoint for media
    wp_url = WOO_URL.rstrip('/')
    media_url = f"{wp_url}/wp-json/wp/v2/media"
    
    # Prepare authentication
    auth = (WOO_CONSUMER_KEY, WOO_CONSUMER_SECRET)
    
    # Determine mime type
    mime_type, _ = mimetypes.guess_type(str(image_path))
    if not mime_type:
        mime_type = 'image/jpeg'
    
    # Read image file
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Prepare headers
    headers = {
        'Content-Type': mime_type,
        'Content-Disposition': f'attachment; filename="{image_path.name}"'
    }
    
    # Upload
    try:
        response = requests.post(
            media_url,
            headers=headers,
            data=image_data,
            auth=auth,
            timeout=60
        )
        
        if response.status_code in [200, 201]:
            media_data = response.json()
            return media_data.get('source_url', '')
        else:
            logger.error(f"Upload failed: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        return ""


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


def find_images(category: str = None, sku: str = None) -> List[Path]:
    """Find images in data/images directory."""
    images = []
    
    if sku:
        # Search for specific SKU
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            img_path = IMAGES_DIR / f"{sku}{ext}"
            if img_path.exists():
                images.append(img_path)
                break
    elif category:
        # Search in specific category folder
        category_dir = IMAGES_DIR / category
        if category_dir.exists():
            for ext in ['.jpg', '.jpeg', '.png', '.webp']:
                images.extend(category_dir.glob(f"*{ext}"))
    else:
        # Search all images
        for ext in ['.jpg', '.jpeg', '.png', '.webp']:
            images.extend(IMAGES_DIR.rglob(f"*{ext}"))
    
    return images


def main():
    parser = argparse.ArgumentParser(description="Upload images to WooCommerce")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without uploading")
    parser.add_argument("--sku", type=str, help="Upload image for specific SKU")
    parser.add_argument("--category", type=str, help="Upload images from specific category folder")
    parser.add_argument("--limit", type=int, help="Limit number of images to upload")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("📤 WOOCOMMERCE - UPLOAD PRODUCT IMAGES")
    print("=" * 80)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No uploads will be made")
    
    if args.sku:
        print(f"🎯 Uploading image for SKU: {args.sku}")
    elif args.category:
        print(f"📁 Uploading images from category: {args.category}")
    else:
        print("📁 Uploading all images")
    
    print("=" * 80)
    print()
    
    # Find images
    logger.info("Finding images...")
    images = find_images(category=args.category, sku=args.sku)
    
    if not images:
        logger.warning("No images found!")
        return
    
    logger.info(f"Found {len(images)} images")
    
    # Apply limit
    if args.limit and args.limit > 0:
        images = images[:args.limit]
        logger.info(f"Limited to {len(images)} images")
    
    # Show examples
    print()
    print("📋 IMAGES TO UPLOAD (first 10):")
    for img in images[:10]:
        # Extract SKU from filename (remove extension)
        sku = img.stem
        print(f"  {sku:20s} | {img.relative_to(IMAGES_DIR)}")
    if len(images) > 10:
        print(f"  ... and {len(images) - 10} more")
    print()
    
    if args.dry_run:
        logger.info("✅ DRY RUN COMPLETE - No uploads were made")
        return
    
    # Confirm
    confirm = input("⚠️  Proceed with upload? Type 'yes' to continue: ")
    if confirm.lower() != 'yes':
        logger.info("❌ Aborted by user")
        return
    print()
    
    # Initialize WooCommerce API
    logger.info("Connecting to WooCommerce...")
    wcapi = init_woo_api()
    
    # Process images
    logger.info("Uploading images...")
    print()
    
    results = {
        'uploaded': [],
        'updated': [],
        'not_found': [],
        'failed': []
    }
    
    for i, img_path in enumerate(images, 1):
        sku = img_path.stem
        
        logger.info(f"[{i}/{len(images)}] Processing {sku}...")
        
        # Find product
        product = find_product_by_sku(wcapi, sku)
        
        if not product:
            logger.warning(f"  ⚠️  Product not found in WooCommerce")
            results['not_found'].append(sku)
            continue
        
        product_id = product['id']
        product_name = product['name']
        
        logger.info(f"  Found: ID={product_id}, Name={product_name[:40]}")
        
        # Upload image
        logger.info(f"  Uploading image...")
        image_url = upload_image_to_wordpress(img_path, sku)
        
        if not image_url:
            logger.error(f"  ❌ Upload failed")
            results['failed'].append(sku)
            continue
        
        logger.info(f"  ✅ Uploaded: {image_url}")
        results['uploaded'].append(sku)
        
        # Update product
        logger.info(f"  Updating product...")
        success = update_product_image(wcapi, product_id, image_url)
        
        if success:
            logger.info(f"  ✅ Product updated")
            results['updated'].append(sku)
        else:
            logger.error(f"  ❌ Product update failed")
            results['failed'].append(sku)
        
        # Rate limiting
        time.sleep(1)
    
    # Summary
    print()
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Total processed:    {len(images)}")
    print(f"Images uploaded:    {len(results['uploaded'])}")
    print(f"Products updated:   {len(results['updated'])}")
    print(f"Products not found: {len(results['not_found'])}")
    print(f"Failed:             {len(results['failed'])}")
    print("=" * 80)
    
    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = REPORT_DIR / f"image_upload_{timestamp}.json"
    
    report = {
        "timestamp": timestamp,
        "category": args.category,
        "sku": args.sku,
        "total_processed": len(images),
        "results": results
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 Report saved: {report_file}")


if __name__ == "__main__":
    main()
