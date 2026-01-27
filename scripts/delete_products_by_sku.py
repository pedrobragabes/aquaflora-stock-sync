#!/usr/bin/env python3
"""
Delete products from WooCommerce by SKU.
Uses the WooCommerce REST API to find and delete products.

Usage:
    python scripts/delete_products_by_sku.py --dry-run    # Preview only
    python scripts/delete_products_by_sku.py              # Actually delete
    python scripts/delete_products_by_sku.py --force      # Skip confirmation
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from woocommerce import API as WooAPI

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def delete_products_by_sku(
    skus: list,
    dry_run: bool = True,
    batch_size: int = 10,
    delay_between: float = 0.5
) -> dict:
    """
    Delete products from WooCommerce by SKU.
    
    Args:
        skus: List of SKUs to delete
        dry_run: If True, only preview without deleting
        batch_size: Number to process before delay
        delay_between: Seconds between batches
        
    Returns:
        dict with deleted, not_found, and errors counts
    """
    
    woo_url = os.getenv("WOO_URL")
    consumer_key = os.getenv("WOO_CONSUMER_KEY")
    consumer_secret = os.getenv("WOO_CONSUMER_SECRET")
    
    if not all([woo_url, consumer_key, consumer_secret]):
        logger.error("❌ WooCommerce credentials not configured!")
        logger.error("   Please set WOO_URL, WOO_CONSUMER_KEY, WOO_CONSUMER_SECRET in .env")
        return {"deleted": 0, "not_found": 0, "errors": []}
    
    wcapi = WooAPI(
        url=woo_url,
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        version="wc/v3",
        timeout=60,
    )
    
    results = {
        "deleted": 0,
        "not_found": 0,
        "errors": [],
        "deleted_skus": [],
        "not_found_skus": [],
    }
    
    total = len(skus)
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Processing {total} SKUs...")
    
    for i, sku in enumerate(skus, 1):
        try:
            # Find product by SKU
            response = wcapi.get(f"products?sku={sku}")
            
            if response.status_code != 200:
                logger.warning(f"[{i}/{total}] ❌ API error for {sku}: {response.status_code}")
                results["errors"].append(f"{sku}: API error {response.status_code}")
                continue
            
            products = response.json()
            
            if not products:
                logger.debug(f"[{i}/{total}] ⏭️ SKU not found: {sku}")
                results["not_found"] += 1
                results["not_found_skus"].append(sku)
                continue
            
            product = products[0]
            woo_id = product["id"]
            name = product.get("name", "")[:40]
            
            if dry_run:
                logger.info(f"[{i}/{total}] 🔍 Would delete: {sku} - {name} (ID: {woo_id})")
                results["deleted"] += 1
                results["deleted_skus"].append(sku)
            else:
                # Actually delete (force=True to bypass trash)
                del_response = wcapi.delete(f"products/{woo_id}?force=true")
                
                if del_response.status_code == 200:
                    logger.info(f"[{i}/{total}] 🗑️ Deleted: {sku} - {name}")
                    results["deleted"] += 1
                    results["deleted_skus"].append(sku)
                else:
                    logger.warning(f"[{i}/{total}] ❌ Delete failed: {sku} - {del_response.status_code}")
                    results["errors"].append(f"{sku}: Delete failed {del_response.status_code}")
            
            # Rate limiting
            if i % batch_size == 0 and i < total:
                time.sleep(delay_between)
                
        except Exception as e:
            logger.error(f"[{i}/{total}] ❌ Error processing {sku}: {e}")
            results["errors"].append(f"{sku}: {str(e)}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Delete WooCommerce products by SKU")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't delete")
    parser.add_argument("--force", action="store_true", help="Skip confirmation")
    parser.add_argument("--input", default="data/skus_to_delete.json", help="JSON file with SKU list")
    
    args = parser.parse_args()
    
    # Load SKUs
    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"❌ Input file not found: {input_file}")
        return 1
    
    with open(input_file, "r", encoding="utf-8") as f:
        skus = json.load(f)
    
    print("=" * 70)
    print("🗑️  WOOCOMMERCE PRODUCT DELETION")
    print("=" * 70)
    print(f"📄 Input file: {input_file}")
    print(f"📦 Products to delete: {len(skus)}")
    print(f"🔍 Mode: {'DRY RUN (preview only)' if args.dry_run else '⚠️ LIVE DELETE!'}")
    print("=" * 70)
    
    if not args.dry_run and not args.force:
        confirm = input(f"\n⚠️ Are you sure you want to DELETE {len(skus)} products? (yes/no): ")
        if confirm.lower() != "yes":
            print("❌ Aborted.")
            return 0
    
    results = delete_products_by_sku(skus, dry_run=args.dry_run)
    
    print("\n" + "=" * 70)
    print("📊 RESULTS")
    print("=" * 70)
    print(f"✅ Deleted: {results['deleted']}")
    print(f"⏭️ Not found (already deleted?): {results['not_found']}")
    print(f"❌ Errors: {len(results['errors'])}")
    
    if results["errors"]:
        print("\n❌ Errors:")
        for error in results["errors"][:10]:
            print(f"   - {error}")
        if len(results["errors"]) > 10:
            print(f"   ... and {len(results['errors']) - 10} more")
    
    # Save results
    results_file = Path("data/deletion_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n📄 Results saved to: {results_file}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
