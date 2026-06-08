#!/usr/bin/env python3
"""
Restore synthetic WooCommerce parent products that were drafted by ghost zeroing.

By default this script is a dry run. Use --execute to publish changes.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import settings
from woocommerce import API as WooAPI


def load_last_ghost_skus(stats_file: Path) -> list[str]:
    if not stats_file.exists():
        raise FileNotFoundError(f"Stats file not found: {stats_file}")

    with stats_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    return [str(sku) for sku in data.get("ghost_skus_zeroed", []) if sku]


def is_parent_sku(sku: str) -> bool:
    return sku.upper().startswith("P-")


def find_product(wcapi: WooAPI, sku: str) -> dict | None:
    response = wcapi.get("products", params={"sku": sku, "status": "any"})
    if response.status_code != 200:
        raise RuntimeError(f"GET failed for {sku}: {response.status_code} {response.text[:200]}")

    products = response.json()
    return products[0] if products else None


def restore_product(wcapi: WooAPI, product: dict, execute: bool) -> bool:
    sku = product.get("sku", "")
    product_id = product["id"]
    current_status = product.get("status", "")

    payload = {
        "status": "publish",
        "catalog_visibility": "visible",
    }

    if not execute:
        print(f"[DRY RUN] Would publish {sku} (ID {product_id}, current status: {current_status})")
        return True

    response = wcapi.put(f"products/{product_id}", payload)
    if response.status_code != 200:
        print(f"[ERROR] Failed to publish {sku}: {response.status_code} {response.text[:200]}")
        return False

    print(f"[OK] Published {sku} (ID {product_id})")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restore synthetic parent SKUs drafted by ghost zeroing."
    )
    parser.add_argument(
        "--stats-file",
        type=Path,
        default=ROOT / "last_run_stats.json",
        help="last_run_stats.json to read ghost_skus_zeroed from",
    )
    parser.add_argument(
        "--sku",
        action="append",
        default=[],
        help="Specific SKU to restore. Can be repeated.",
    )
    parser.add_argument(
        "--include-non-parent",
        action="store_true",
        help="Allow restoring SKUs that do not start with P-.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually publish products. Without this, only prints planned changes.",
    )
    args = parser.parse_args()

    if not settings.woo_configured:
        print("WooCommerce credentials are not configured in .env")
        return 2

    skus = args.sku or load_last_ghost_skus(args.stats_file)
    if not args.include_non_parent:
        skus = [sku for sku in skus if is_parent_sku(sku)]

    skus = sorted(set(skus))
    if not skus:
        print("No parent SKUs to restore.")
        return 0

    wcapi = WooAPI(
        url=settings.woo_url,
        consumer_key=settings.woo_consumer_key,
        consumer_secret=settings.woo_consumer_secret,
        version="wc/v3",
        timeout=60,
    )

    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print(f"SKUs to inspect: {len(skus)}")

    ok = 0
    failed = 0
    missing = 0

    for sku in skus:
        product = find_product(wcapi, sku)
        if not product:
            print(f"[MISSING] {sku}")
            missing += 1
            continue

        if restore_product(wcapi, product, args.execute):
            ok += 1
        else:
            failed += 1

    print(f"Done. ok={ok}, missing={missing}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
