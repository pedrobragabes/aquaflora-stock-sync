#!/usr/bin/env python3
"""
Test image scraping for 5 products from Athos.csv
Uses Vision AI for quality validation.
"""

import csv
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from src.image_scraper import (
    search_validate_and_save,
    VISION_AI_ENABLED,
    GOOGLE_API_KEY
)

# Test products from Athos.csv (good candidates)
TEST_PRODUCTS = [
    {
        "sku": "7896183302122",
        "name": "ABRILHANTADOR SANOL 500ML",
        "category": "PET",
        "brand": "SANOL"
    },
    {
        "sku": "7896108815102",
        "name": "ALCON CLUB JABUTI 300G",
        "category": "AQUARISMO",
        "brand": "ALCON"
    },
    {
        "sku": "7896108808784",
        "name": "ALCON GOLDFISH COLOUR BITS 10G",
        "category": "AQUARISMO",
        "brand": "ALCON"
    },
    {
        "sku": "7891528007755",
        "name": "ALARME SONORO ELETRONICO WS Y775",
        "category": "PESCA",
        "brand": "JWS"
    },
    {
        "sku": "7898942611438",
        "name": "ABSORVENTE HIGIENICO PET",
        "category": "PET",
        "brand": "FRALDOGS"
    },
]

OUTPUT_DIR = Path("data/images_test")


def main():
    print("=" * 60)
    print("🖼️  IMAGE SCRAPER TEST - 5 Products from Athos.csv")
    print("=" * 60)
    print(f"Vision AI: {'✅ Enabled' if VISION_AI_ENABLED else '❌ Disabled'}")
    print(f"API Key: {'✅ Configured' if GOOGLE_API_KEY else '❌ Missing'}")
    print(f"Output: {OUTPUT_DIR.absolute()}")
    print("=" * 60)
    print()
    
    results = []
    
    for i, product in enumerate(TEST_PRODUCTS, 1):
        print(f"\n[{i}/5] Processing: {product['name']}")
        print(f"       SKU: {product['sku']}")
        print(f"       Category: {product['category']} | Brand: {product['brand']}")
        
        # Search with brand included for better results
        search_name = f"{product['name']} {product['brand']}"
        
        saved_path, vision_result = search_validate_and_save(
            product_name=search_name,
            sku=product['sku'],
            output_dir=OUTPUT_DIR,
            category=product['category'],
            max_candidates=5,
            use_vision_ai=True
        )
        
        if saved_path:
            print(f"       ✅ Saved: {saved_path.name}")
            if vision_result:
                print(f"       📊 Vision Score: {vision_result.score:.2f}")
                print(f"       🏷️  Labels: {', '.join(vision_result.labels[:4])}")
            results.append({
                "product": product,
                "path": saved_path,
                "score": vision_result.score if vision_result else 0
            })
        else:
            print(f"       ❌ No valid image found")
            results.append({
                "product": product,
                "path": None,
                "score": 0
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    
    success = [r for r in results if r['path']]
    failed = [r for r in results if not r['path']]
    
    print(f"✅ Success: {len(success)}/5")
    print(f"❌ Failed: {len(failed)}/5")
    
    if success:
        avg_score = sum(r['score'] for r in success) / len(success)
        print(f"📊 Average Vision Score: {avg_score:.2f}")
    
    print(f"\n📁 Images saved to: {OUTPUT_DIR.absolute()}")
    
    if failed:
        print("\n❌ Failed products:")
        for r in failed:
            print(f"   - {r['product']['name']}")


if __name__ == "__main__":
    main()
