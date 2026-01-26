#!/usr/bin/env python3
"""
Remove excluded products from WooCommerce.

This script reads the exclusion list and removes matching products from WooCommerce
via the REST API. Supports dry-run mode for safety.

Usage:
    python scripts/remove_excluded_from_woocommerce.py --dry-run  # Simulate
    python scripts/remove_excluded_from_woocommerce.py            # Move to trash
    python scripts/remove_excluded_from_woocommerce.py --force    # Delete permanently
    python scripts/remove_excluded_from_woocommerce.py --department FERRAMENTAS  # Specific dept
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

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

# WooCommerce credentials from environment
WOO_URL = os.getenv("WOO_URL", "")
WOO_CONSUMER_KEY = os.getenv("WOO_CONSUMER_KEY", "")
WOO_CONSUMER_SECRET = os.getenv("WOO_CONSUMER_SECRET", "")


# Paths
EXCLUSION_FILE = Path("config/exclusion_list.json")
INPUT_FILE = Path("data/input/Athos.csv")
REPORT_DIR = Path("data/reports")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_exclusion_list() -> dict:
    """Load exclusion rules from config."""
    if not EXCLUSION_FILE.exists():
        logger.error(f"Exclusion file not found: {EXCLUSION_FILE}")
        return {}
    
    with open(EXCLUSION_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_csv_products() -> List[dict]:
    """Load all products from CSV."""
    products = []
    with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            products.append(row)
    return products


def should_exclude(product: dict, exclusions: dict, target_dept: str = None) -> Tuple[bool, str]:
    """Check if product should be excluded."""
    dept = product.get('Departamento', '').upper().strip()
    name = product.get('Descricao', '').lower()
    brand = product.get('Marca', '').strip()
    
    # Filter by department if specified
    if target_dept:
        if dept != target_dept.upper():
            return False, ""
    
    # Check excluded departments
    for excl_dept in exclusions.get('exclude_departments', []):
        if excl_dept.upper() == dept:
            return True, f"Department: {dept}"
    
    # Check excluded brands
    for excl_brand in exclusions.get('exclude_brands', []):
        if excl_brand.upper() == brand.upper():
            return True, f"Brand: {brand}"
    
    # Check keywords
    for category, keywords in exclusions.get('exclude_keywords', {}).items():
        for kw in keywords:
            if kw.lower() in name:
                return True, f"Keyword: {kw} (category: {category})"
    
    return False, ""


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
        timeout=30
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


def delete_product(wcapi: API, product_id: int, force: bool = False) -> bool:
    """Delete or trash a product."""
    try:
        params = {"force": force}
        response = wcapi.delete(f"products/{product_id}", params=params)
        return response.status_code in [200, 201]
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Remove excluded products from WooCommerce")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    parser.add_argument("--force", action="store_true", help="Delete permanently (instead of trash)")
    parser.add_argument("--department", type=str, help="Only process specific department")
    parser.add_argument("--limit", type=int, help="Limit number of products to process")
    parser.add_argument("--skip-api", action="store_true", help="Skip API calls (just show what would be done)")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("🗑️  WOOCOMMERCE - REMOVE EXCLUDED PRODUCTS")
    print("=" * 80)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
    elif args.skip_api:
        print("📋 SKIP API MODE - Only analyzing, no API calls")
    elif args.force:
        print("⚠️  FORCE MODE - Products will be PERMANENTLY deleted")
    else:
        print("🗑️  TRASH MODE - Products will be moved to trash")
    
    if args.department:
        print(f"📦 Filtering by department: {args.department}")
    
    print("=" * 80)
    print()
    
    # Load data
    logger.info("Loading exclusion list...")
    exclusions = load_exclusion_list()
    
    logger.info("Loading products from CSV...")
    products = load_csv_products()
    
    # Find excluded products
    logger.info("Analyzing products...")
    excluded_products = []
    excluded_by_reason = defaultdict(list)
    
    for product in products:
        sku = product.get('CodigoBarras', '')
        if not sku or len(sku) < 5:
            continue
        
        should_excl, reason = should_exclude(product, exclusions, args.department)
        if should_excl:
            excluded_products.append({
                'sku': sku,
                'name': product.get('Descricao', ''),
                'dept': product.get('Departamento', ''),
                'brand': product.get('Marca', ''),
                'reason': reason
            })
            excluded_by_reason[reason].append(sku)
    
    logger.info(f"Found {len(excluded_products)} products to remove")
    
    # Show summary by reason
    print()
    print("📊 EXCLUSION SUMMARY:")
    for reason, skus in sorted(excluded_by_reason.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {reason:40s}: {len(skus):4d} products")
    print()
    
    # Apply limit if specified
    if args.limit and args.limit > 0:
        excluded_products = excluded_products[:args.limit]
        logger.info(f"Limited to {len(excluded_products)} products")
    
    if not excluded_products:
        logger.info("✅ No products to remove!")
        return
    
    # Show first 10 examples
    print("📋 EXAMPLES (first 10):")
    for p in excluded_products[:10]:
        print(f"  {p['sku']:15s} | {p['dept']:15s} | {p['name'][:50]:50s} | {p['reason']}")
    if len(excluded_products) > 10:
        print(f"  ... and {len(excluded_products) - 10} more")
    print()
    
    if args.skip_api:
        logger.info("✅ Analysis complete (--skip-api mode)")
        return
    
    # Confirm if not dry-run
    if not args.dry_run:
        print("⚠️  WARNING: This will remove products from WooCommerce!")
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            logger.info("❌ Aborted by user")
            return
        print()
    
    # Initialize WooCommerce API
    if not args.dry_run:
        logger.info("Connecting to WooCommerce...")
        wcapi = init_woo_api()
    else:
        wcapi = None
    
    # Process products
    logger.info("Processing products...")
    print()
    
    results = {
        'found': [],
        'not_found': [],
        'deleted': [],
        'failed': []
    }
    
    for i, product in enumerate(excluded_products, 1):
        sku = product['sku']
        name = product['name']
        
        logger.info(f"[{i}/{len(excluded_products)}] Processing {sku} - {name[:40]}...")
        
        if args.dry_run:
            # Simulate
            logger.info(f"  [DRY RUN] Would search for SKU {sku}")
            results['found'].append(sku)
            time.sleep(0.1)  # Simulate API delay
            continue
        
        # Find product in WooCommerce
        woo_product = find_product_by_sku(wcapi, sku)
        
        if not woo_product:
            logger.warning(f"  ⚠️  Product not found in WooCommerce")
            results['not_found'].append(sku)
            continue
        
        product_id = woo_product['id']
        woo_name = woo_product['name']
        
        logger.info(f"  Found: ID={product_id}, Name={woo_name[:40]}")
        results['found'].append(sku)
        
        # Delete product
        success = delete_product(wcapi, product_id, force=args.force)
        
        if success:
            action = "Deleted" if args.force else "Moved to trash"
            logger.info(f"  ✅ {action}")
            results['deleted'].append(sku)
        else:
            logger.error(f"  ❌ Failed to delete")
            results['failed'].append(sku)
        
        # Rate limiting
        time.sleep(0.5)
    
    # Summary
    print()
    print("=" * 80)
    print("📊 FINAL SUMMARY")
    print("=" * 80)
    print(f"Total analyzed:     {len(excluded_products)}")
    print(f"Found in WooCommerce: {len(results['found'])}")
    print(f"Not found:          {len(results['not_found'])}")
    print(f"Successfully removed: {len(results['deleted'])}")
    print(f"Failed:             {len(results['failed'])}")
    print("=" * 80)
    
    # Save report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = REPORT_DIR / f"woo_removal_{timestamp}.json"
    
    report = {
        "timestamp": timestamp,
        "mode": "dry_run" if args.dry_run else ("force" if args.force else "trash"),
        "department_filter": args.department,
        "total_analyzed": len(excluded_products),
        "results": results,
        "excluded_products": excluded_products
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    logger.info(f"📄 Report saved: {report_file}")
    
    if args.dry_run:
        print()
        print("✅ DRY RUN COMPLETE - No changes were made")
        print("   Run without --dry-run to actually remove products")


if __name__ == "__main__":
    main()
