#!/usr/bin/env python3
"""
AquaFlora Stock Sync - Main Entry Point
Sync Athos ERP data with WooCommerce.

Usage:
    python main.py --input data/input/estoque.csv
    python main.py --input data/input/estoque.csv --dry-run
    python main.py --input data/input/estoque.csv --lite  # Price/Stock only
    python main.py --map-site                              # Build whitelist from WooCommerce
    python main.py --input data/input/estoque.csv --allow-create  # Allow creating new products
    python main.py --watch  # Daemon mode (watches input folder)
"""

import argparse
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from src.parser import AthosParser
from src.enricher import ProductEnricher
from src.database import ProductDatabase
from src.sync import WooSyncManager
from src.notifications import NotificationService
from src.models import SyncSummary


def setup_logging(log_level: str = "INFO", log_dir: Path = Path("./logs")):
    """Configure logging with console and rotating file handlers."""
    import os
    
    # Check if running in Docker (stdout preferred)
    log_to_stdout = os.environ.get("LOG_TO_STDOUT", "false").lower() == "true"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Console handler (use stdout for Docker compatibility)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if log_to_stdout else logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(console)
    
    # File handler with rotation (skip if stdout-only mode)
    if not log_to_stdout:
        log_file = log_dir / f"sync_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=settings.log_rotation_mb * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
        ))
        logger.addHandler(file_handler)
    
    return logger


def process_file(input_file: Path, dry_run: bool = False, lite_mode: bool = False, allow_create: bool = False) -> SyncSummary:
    """
    Process a single input file.
    
    Args:
        input_file: Path to the Athos ERP export file
        dry_run: If True, don't actually sync to WooCommerce
        lite_mode: If True, only update price and stock (preserves SEO edits)
        allow_create: If True, allow creating new products (default: False for safety)
        
    Returns:
        SyncSummary with results
    """
    logger = logging.getLogger(__name__)
    logger.info(f"{'='*60}")
    
    if lite_mode:
        logger.info("🚀 Starting Sync in LITE MODE (Price & Stock only)")
        logger.info("⚠️  Content fields (name, description, images) will NOT be updated")
    else:
        logger.info(f"Starting AquaFlora Stock Sync (FULL MODE)")
    
    if not allow_create:
        logger.info("🛡️  Safety: New products will NOT be created (use --allow-create to enable)")
    
    logger.info(f"Input: {input_file}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info(f"{'='*60}")
    
    # 1. Parse input file
    logger.info("📖 Parsing input file...")
    parser = AthosParser()
    raw_products = parser.parse_file(input_file)
    logger.info(f"✅ Parsed {len(raw_products)} raw products")
    
    if not raw_products:
        logger.warning("No products parsed from file!")
        return SyncSummary(total_parsed=0, success=False, errors=["No products in file"])
    
    # 2. Enrich products
    logger.info("🔧 Enriching products...")
    enricher = ProductEnricher()
    enriched_products = []
    
    for raw in raw_products:
        try:
            enriched = enricher.enrich(raw)
            enriched_products.append(enriched)
        except Exception as e:
            logger.warning(f"Failed to enrich {raw.sku}: {e}")
    
    logger.info(f"✅ Enriched {len(enriched_products)} products")
    
    # Show sample
    if enriched_products:
        sample = enriched_products[0]
        logger.info(f"   Sample: {sample.sku} | {sample.name} | {sample.brand or 'No brand'} | {sample.weight_kg or 'No weight'}kg")
    
    # 3. Initialize database
    logger.info("💾 Initializing database...")
    db = ProductDatabase(settings.db_path)
    stats = db.get_stats()
    logger.info(f"   Database: {stats['total_products']} products, {stats['synced_to_woo']} synced")
    
    # 4. Sync to WooCommerce (if enabled)
    summary = SyncSummary(total_parsed=len(raw_products), total_enriched=len(enriched_products))
    
    if settings.sync_enabled and settings.woo_configured:
        logger.info("🔄 Syncing to WooCommerce...")
        
        # Show whitelist status
        site_products = db.get_site_products_count()
        if site_products > 0:
            logger.info(f"🛡️  Whitelist: {site_products} products mapped from site")
        elif not allow_create:
            logger.warning("⚠️  No products mapped! Run --map-site first or use --allow-create")
        
        syncer = WooSyncManager(
            woo_url=settings.woo_url,
            consumer_key=settings.woo_consumer_key,
            consumer_secret=settings.woo_consumer_secret,
            dry_run=dry_run or settings.dry_run,
            price_guard_max_variation=settings.price_guard_max_variation,
            lite_mode=lite_mode,
            allow_create=allow_create,
        )
        
        summary = syncer.sync_products(
            enriched_products,
            db,
            zero_ghost_stock=settings.zero_ghost_stock,
        )
    else:
        if not settings.woo_configured:
            logger.warning("⚠️ WooCommerce credentials not configured - skipping sync")
        if not settings.sync_enabled:
            logger.info("ℹ️ Sync disabled in settings")
        
        # Just update summary with enriched count
        summary.success = True
    
    # 5. Export to CSV (always)
    logger.info("📤 Exporting to CSV...")
    if lite_mode:
        output_file = export_to_csv_lite(enriched_products, settings.output_dir)
    else:
        output_file = export_to_csv_full(enriched_products, settings.output_dir)
    logger.info(f"✅ Exported to: {output_file}")
    
    # 6. Send notifications
    if settings.discord_webhook_configured:
        logger.info("📨 Sending notifications...")
        notifier = NotificationService(
            discord_webhook_url=settings.discord_webhook_url,
            telegram_webhook_url=settings.telegram_webhook_url,
        )
        notifier.send_report(summary)
        notifier.close()
    
    # 7. Save last run stats for bot commands
    summary.to_json_file("last_run_stats.json")
    logger.debug("📊 Saved last_run_stats.json for bot commands")
    
    # 8. Run backup if enabled
    if settings.backup_configured and summary.success:
        from src.backup import run_backup
        logger.info("☁️ Running backup to cloud storage...")
        try:
            backup_success = run_backup(
                db_path=settings.db_path,
                stats_path=Path("last_run_stats.json"),
                rclone_remote=settings.backup_rclone_remote,
                retention_days=settings.backup_retention_days,
            )
            if backup_success:
                logger.info("✅ Backup completed")
            else:
                logger.warning("⚠️ Backup failed - check rclone configuration")
        except Exception as e:
            logger.error(f"❌ Backup error: {e}")
    
    # 9. Print final report
    print_report(summary)
    
    db.close()
    return summary


def export_to_csv_lite(products, output_dir: Path) -> Path:
    """
    Export products to CSV for LITE mode (WooCommerce import).
    Contains ONLY fields needed for price/stock update - 100% WooCommerce compatible.
    """
    import csv
    
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"woocommerce_LITE_{timestamp}.csv"
    
    if not products:
        return output_file
    
    # Minimal columns for WooCommerce import (update by SKU)
    columns = ['SKU', 'Regular price', 'Stock', 'In stock?']
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        
        for p in products:
            row = [
                p.sku,
                str(p.price),
                p.stock,
                1 if p.stock > 0 else 0,
            ]
            writer.writerow(row)
    
    return output_file


def export_to_csv_full(products, output_dir: Path) -> Path:
    """Export enriched products to CSV (full mode)."""
    import csv
    
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"woocommerce_import_{timestamp}.csv"
    
    if not products:
        return output_file
    
    # Define CSV columns
    columns = [
        'SKU', 'Name', 'Published', 'Is featured?', 'Visibility in catalog',
        'Short description', 'Description', 'Tax status', 'Tax class',
        'In stock?', 'Stock', 'Backorders allowed?', 'Sold individually?',
        'Weight (kg)', 'Regular price', 'Sale price', 'Categories', 'Tags',
        'Attribute 1 name', 'Attribute 1 value(s)', 'Attribute 1 visible',
        'Attribute 1 global', 'Allow customer reviews?',
        'Meta: _custo', 'Meta: _estoque_minimo', 'Meta: _margem',
        'Meta: _categoria_original', 'Meta: _nome_original', 'Meta: _marca',
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        
        for p in products:
            row = [
                p.sku,
                p.name,
                1 if p.published and p.stock > 0 else 0,
                0,  # Is featured
                'visible',
                p.short_description,
                p.description,
                'taxable',
                '',  # Tax class
                1 if p.stock > 0 else 0,
                p.stock,
                0,  # Backorders
                0,  # Sold individually
                p.weight_kg or '',
                str(p.price),
                '',  # Sale price
                p.category,
                ', '.join(p.tags),
                'Marca' if p.brand else '',
                p.brand or '',
                1 if p.brand else 0,
                1,  # Global attribute
                1,  # Allow reviews
                str(p.cost),
                p.minimum,
                f"{p.margin_percent:.2f}",
                p.category_original,
                p.name_original,
                p.brand or '',
            ]
            writer.writerow(row)
    
    return output_file


def print_report(summary: SyncSummary):
    """Print final sync report to console."""
    print("\n" + "="*60)
    print("📊 RELATÓRIO FINAL")
    print("="*60)
    
    status = "✅ SUCESSO" if summary.success else "❌ ERROS ENCONTRADOS"
    print(f"Status: {status}")
    print(f"Horário: {summary.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    print(f"📄 Produtos parseados: {summary.total_parsed}")
    print(f"🔧 Produtos enriquecidos: {summary.total_enriched}")
    print()
    
    print(f"✨ Novos criados: {summary.new_products}")
    print(f"🔄 Atualizações completas: {summary.full_updates}")
    print(f"⚡ Atualizações rápidas: {summary.fast_updates}")
    print(f"⏭️  Ignorados (sem mudanças): {summary.skipped}")
    print()
    
    if summary.price_warnings:
        print(f"🚫 Bloqueados pelo PriceGuard: {len(summary.price_warnings)}")
        for w in summary.price_warnings[:5]:
            print(f"   • {w.sku}: R${w.old_price:.2f} → R${w.new_price:.2f} ({w.variation_percent:.1f}%)")
        print()
    
    if summary.ghost_skus_zeroed:
        print(f"👻 SKUs fantasma zerados: {len(summary.ghost_skus_zeroed)}")
        print()
    
    if summary.errors:
        print(f"❌ Erros: {len(summary.errors)}")
        for e in summary.errors[:5]:
            print(f"   • {e}")
        print()
    
    print("="*60)


def map_site_products():
    """
    Fetch ALL products from WooCommerce and build local whitelist.
    This should be run BEFORE regular sync to map existing products.
    """
    logger = logging.getLogger(__name__)
    logger.info("="*60)
    logger.info("🗺️  MAPPING PRODUCTS FROM WOOCOMMERCE")
    logger.info("="*60)
    
    if not settings.woo_configured:
        logger.error("❌ WooCommerce credentials not configured!")
        logger.error("   Configure WOO_URL, WOO_CONSUMER_KEY, WOO_CONSUMER_SECRET in .env")
        return
    
    from woocommerce import API as WooAPI
    
    wcapi = WooAPI(
        url=settings.woo_url,
        consumer_key=settings.woo_consumer_key,
        consumer_secret=settings.woo_consumer_secret,
        version="wc/v3",
        timeout=60,
    )
    
    db = ProductDatabase(settings.db_path)
    
    # Clear existing whitelist to rebuild fresh
    logger.info("🔄 Clearing existing whitelist...")
    db.clear_whitelist()
    
    page = 1
    per_page = 100
    total_mapped = 0
    total_without_sku = 0
    
    logger.info("📥 Fetching products from WooCommerce (this may take a while)...")
    
    while True:
        try:
            response = wcapi.get("products", params={
                "page": page,
                "per_page": per_page,
                "status": "any",  # Include drafts and published
            })
            
            if response.status_code != 200:
                logger.error(f"API Error: {response.status_code}")
                break
            
            products = response.json()
            
            if not products:
                break  # No more products
            
            for p in products:
                sku = p.get("sku", "").strip()
                woo_id = p.get("id")
                name = p.get("name", "")[:50]
                
                if sku and woo_id:
                    db.save_from_woocommerce(sku, woo_id)
                    total_mapped += 1
                    logger.debug(f"   Mapped: {sku} → WooID {woo_id} ({name})")
                else:
                    total_without_sku += 1
                    logger.debug(f"   Skipped: WooID {woo_id} (no SKU) - {name}")
            
            logger.info(f"   Page {page}: Found {len(products)} products...")
            page += 1
            
        except Exception as e:
            logger.error(f"Error fetching page {page}: {e}")
            break
    
    db.close()
    
    print("\n" + "="*60)
    print("📊 MAPEAMENTO CONCLUÍDO")
    print("="*60)
    print(f"✅ Produtos mapeados (com SKU): {total_mapped}")
    print(f"⚠️  Produtos sem SKU (ignorados): {total_without_sku}")
    print(f"\n🛡️  Whitelist salva em: {settings.db_path}")
    print("   Agora você pode rodar sync com segurança!")
    print("="*60)


def watch_mode():
    """Run in daemon mode, watching input folder for new files."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("❌ watchdog not installed. Run: pip install watchdog")
        sys.exit(1)
    
    logger = logging.getLogger(__name__)
    
    class NewFileHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            
            filepath = Path(event.src_path)
            if filepath.suffix.lower() in ('.csv', '.txt'):
                logger.info(f"📁 New file detected: {filepath.name}")
                try:
                    process_file(filepath, dry_run=settings.dry_run)
                except Exception as e:
                    logger.error(f"Error processing {filepath}: {e}")
    
    input_dir = settings.input_dir
    input_dir.mkdir(parents=True, exist_ok=True)
    
    handler = NewFileHandler()
    observer = Observer()
    observer.schedule(handler, str(input_dir), recursive=False)
    observer.start()
    
    logger.info(f"👁️ Watching for new files in: {input_dir}")
    logger.info("Press Ctrl+C to stop...")
    
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AquaFlora Stock Sync - Sync Athos ERP with WooCommerce"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Path to input CSV file from Athos ERP",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without actually syncing to WooCommerce",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run in daemon mode, watching input folder",
    )
    parser.add_argument(
        "--lite", "--sync-only",
        action="store_true",
        dest="lite",
        help="Lite mode: update ONLY price and stock (preserves manual SEO edits)",
    )
    parser.add_argument(
        "--map-site",
        action="store_true",
        dest="map_site",
        help="Fetch ALL products from WooCommerce and build local whitelist (run this first!)",
    )
    parser.add_argument(
        "--allow-create",
        action="store_true",
        dest="allow_create",
        help="Allow creating NEW products (default: False for safety - only updates existing)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    if args.map_site:
        map_site_products()
    elif args.watch:
        watch_mode()
    elif args.input:
        if not args.input.exists():
            print(f"❌ File not found: {args.input}")
            sys.exit(1)
        process_file(args.input, dry_run=args.dry_run, lite_mode=args.lite, allow_create=args.allow_create)
    else:
        parser.print_help()
        print("\n❌ Please provide --input, --map-site, or --watch")
        sys.exit(1)


if __name__ == "__main__":
    main()
