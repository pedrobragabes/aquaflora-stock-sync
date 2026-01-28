import pandas as pd
import os
import sys
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.image_scraper import search_images, download_image, process_and_save_image

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scrape_correction.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def scrape_row(row, output_dir, category_slug):
    time.sleep(random.uniform(5.0, 10.0)) # Rate limiting (increased to avoid 403)
    try:
        sku = str(row['SKU']).strip()
        name = str(row['Nome']).strip()
        brand = str(row.get('Marcas', '')).strip()
        
        # Skip if necessary info is missing
        if not sku or not name or pd.isna(sku) or pd.isna(name):
            return None

        # Clean SKU for filename
        safe_sku = "".join(c for c in sku if c.isalnum() or c in ('-', '_'))

        # Construct queries - Priority: Name + Brand
        queries = []
        if brand and not pd.isna(brand):
            queries.append(f"{name} {brand}")
            queries.append(f"{name} {brand} {sku}")
        else:
            queries.append(f"{name}")
            queries.append(f"{name} {sku}")
            
        queries.append(f"{name} produto") # Validation helper

        best_candidate = None
        
        # Try searching with fallback queries
        for query in queries:
            candidates = search_images(
                product_name=name,
                sku=sku,
                brand=brand if not pd.isna(brand) else "",
                category=category_slug,
                max_results=5, # Increased to find non-blocked images
                search_mode="cheap"
            )
            
            # Local blocklist for domains that block scrapers
            BLOCKED_DOMAINS = ["petlove.com.br", "petz.com.br", "cobasi.com.br", "magazineluiza.com.br", "amazon.com.br"]
            
            if candidates:
                # Try downloading each candidate until one works
                for candidate in candidates:
                    # Check against local blocklist
                    if any(blocked in candidate.url for blocked in BLOCKED_DOMAINS):
                        logger.debug(f"Skipping blocked domain candidate: {candidate.url}")
                        continue
                        
                    image_content = download_image(candidate.url)
                    if image_content:
                        best_candidate = candidate
                        break # Found a working image!
                    else:
                         logger.warning(f"⚠️ Failed to download candidate for {sku}: {candidate.url}")
            
            if best_candidate:
                break

        if not best_candidate:
            logger.warning(f"❌ No working images found for {sku} - {name}")
            return None

        # valid 'image_content' is already in scope if best_candidate is set


        # Save using project's standard processor (resizes, converts to JPG)
        saved_path = process_and_save_image(
            content=image_content,
            sku=safe_sku,
            output_dir=output_dir
        )
        
        if saved_path:
            # Return new URL
            filename = saved_path.name
            # Construct URL matching the WordPress uploads structure requested
            # uploads > produtos > category > filename
            return f"https://aquafloragroshop.com.br/wp-content/uploads/products/{category_slug}/{filename}"
        
        return None
    except Exception as e:
        logger.error(f"Error processing row {sku}: {e}")
        return None

def main():
    # Configuration
    # Uses absolute paths based on user workspace
    base_path = Path(r"c:\Users\pedro\OneDrive\Documentos\aquaflora-stock-sync-main")
    input_csv = base_path / r"Correção Imagem\Pet.csv"
    output_dir = base_path / r"Correção Imagem\pet"
    category_slug = "pet"
    
    if not input_csv.exists():
        logger.error(f"Input file not found: {input_csv}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"🚀 Starting scraper for {input_csv}")
    logger.info(f"📂 Output directory: {output_dir}")

    # Load CSV
    try:
        df = pd.read_csv(input_csv)
    except Exception as e:
        logger.error(f"Failed to read CSV: {e}")
        return

    if 'Imagens' not in df.columns:
        df['Imagens'] = ""

    # Track progress
    total_items = len(df)
    processed_count = 0
    updated_count = 0

    # Multithreading for speed
    futures = {}
    with ThreadPoolExecutor(max_workers=2) as executor:
        for index, row in df.iterrows():
            future = executor.submit(scrape_row, row, output_dir, category_slug)
            futures[future] = index

        for future in as_completed(futures):
            processed_count += 1
            index = futures[future]
            try:
                new_url = future.result()
                if new_url:
                    df.at[index, 'Imagens'] = new_url
                    sku = df.at[index, 'SKU']
                    logger.info(f"[{processed_count}/{total_items}] ✅ Updated {sku}")
                    updated_count += 1
                else:
                    logger.info(f"[{processed_count}/{total_items}] ⏭️  Skipped/Failed {df.at[index, 'SKU']}")
            except Exception as e:
                logger.error(f"Error in thread: {e}")

    # Save updated CSV
    try:
        df.to_csv(input_csv, index=False)
        logger.info(f"🎉 Validated and updated {updated_count} products in {input_csv}")
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")

if __name__ == "__main__":
    main()
