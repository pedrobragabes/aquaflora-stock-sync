"""
AquaFlora Stock Sync - Product Database
SQLite handler for product sync state with dual hash tracking.
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from .models import EnrichedProduct, ProductDBRecord, SyncDecision

logger = logging.getLogger(__name__)


class ProductDatabase:
    """
    SQLite database for tracking product sync state.
    
    Uses dual hash strategy:
    - hash_full: All product fields → triggers full update if changed
    - hash_fast: Price + Stock only → triggers fast update if only these change
    
    Whitelist feature:
    - exists_on_site: True if product exists in WooCommerce (mapped via --map-site)
    - Only products with exists_on_site=True will be updated (unless --allow-create)
    """
    
    TABLE_SCHEMA = """
    CREATE TABLE IF NOT EXISTS products (
        sku TEXT PRIMARY KEY,
        woo_id INTEGER,
        last_hash_full TEXT,
        last_hash_fast TEXT,
        last_price REAL,
        last_sync TEXT,
        created_at TEXT,
        exists_on_site INTEGER DEFAULT 0
    )
    """
    
    # Price history table for analytics
    PRICE_HISTORY_SCHEMA = """
    CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        old_price REAL,
        new_price REAL,
        variation_percent REAL,
        recorded_at TEXT,
        sync_type TEXT,
        FOREIGN KEY (sku) REFERENCES products(sku)
    )
    """
    
    INDEX_SCHEMA = """
    CREATE INDEX IF NOT EXISTS idx_woo_id ON products(woo_id);
    CREATE INDEX IF NOT EXISTS idx_last_sync ON products(last_sync);
    CREATE INDEX IF NOT EXISTS idx_exists_on_site ON products(exists_on_site);
    CREATE INDEX IF NOT EXISTS idx_price_history_sku ON price_history(sku);
    CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(recorded_at);
    """
    
    # Product images table for image curation
    PRODUCT_IMAGES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS product_images (
        sku TEXT PRIMARY KEY,
        image_url TEXT,
        thumbnail_urls TEXT,
        status TEXT DEFAULT 'pending',
        source TEXT,
        curated_at TEXT,
        uploaded_at TEXT
    )
    """
    
    PRODUCT_IMAGES_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_product_images_status ON product_images(status);
    """
    
    # Migration for existing databases without exists_on_site column
    MIGRATION_ADD_EXISTS = """
    ALTER TABLE products ADD COLUMN exists_on_site INTEGER DEFAULT 0;
    """
    
    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self._ensure_dir()
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self._run_migrations()
        logger.info(f"Database initialized: {self.db_path}")
    
    def _ensure_dir(self):
        """Ensure database directory exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_schema(self):
        """Initialize database schema."""
        cursor = self.conn.cursor()
        cursor.execute(self.TABLE_SCHEMA)
        cursor.execute(self.PRICE_HISTORY_SCHEMA)
        cursor.execute(self.PRODUCT_IMAGES_SCHEMA)
        self.conn.commit()
    
    def _run_migrations(self):
        """Run database migrations for schema updates."""
        cursor = self.conn.cursor()
        # Check if exists_on_site column exists
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'exists_on_site' not in columns:
            try:
                cursor.execute(self.MIGRATION_ADD_EXISTS)
                self.conn.commit()
                logger.info("Migration: Added 'exists_on_site' column to products table")
            except sqlite3.OperationalError:
                pass  # Column already exists
        
        # Ensure price_history table exists (for existing databases)
        try:
            cursor.execute(self.PRICE_HISTORY_SCHEMA)
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        except sqlite3.OperationalError as e:
            logger.debug(f"Index creation note: {e}")
    
    # =========================================================================
    # WHITELIST METHODS (for --map-site feature)
    # =========================================================================
    
    def save_from_woocommerce(self, sku: str, woo_id: int):
        """
        Save a product mapping from WooCommerce.
        Marks the product as existing on site (whitelist).
        """
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute(
            """
            INSERT INTO products (sku, woo_id, exists_on_site, created_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(sku) DO UPDATE SET
                woo_id = ?,
                exists_on_site = 1
            """,
            (sku, woo_id, now, woo_id)
        )
        self.conn.commit()
    
    def exists_on_site(self, sku: str) -> bool:
        """Check if a SKU exists on the WooCommerce site (whitelisted)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT exists_on_site, woo_id FROM products WHERE sku = ?",
            (sku,)
        )
        row = cursor.fetchone()
        if not row:
            return False
        # Consider existing if explicitly marked OR has a valid woo_id
        return bool(row['exists_on_site']) or bool(row['woo_id'])
    
    def get_site_products_count(self) -> int:
        """Get count of products that exist on site."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE exists_on_site = 1 OR woo_id IS NOT NULL")
        return cursor.fetchone()['count']
    
    def clear_whitelist(self):
        """Clear the whitelist (reset exists_on_site for all products)."""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE products SET exists_on_site = 0")
        self.conn.commit()
        logger.info("Whitelist cleared")
    
    def get_sync_decision(
        self, 
        product: EnrichedProduct,
        price_guard_max_variation: float = 40.0
    ) -> tuple[SyncDecision, Optional[Dict]]:
        """
        Determine what type of sync is needed for a product.
        
        Returns:
            Tuple of (SyncDecision, price_warning_dict or None)
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE sku = ?",
            (product.sku,)
        )
        row = cursor.fetchone()
        
        if not row:
            # New product
            logger.debug(f"SKU {product.sku}: NEW (not in database)")
            return SyncDecision.NEW, None
        
        # Check price guard
        old_price = row['last_price'] or 0
        new_price = float(product.price)
        
        if old_price > 0:
            variation = abs(new_price - old_price) / old_price * 100
            if variation > price_guard_max_variation:
                logger.warning(
                    f"SKU {product.sku}: BLOCKED by PriceGuard "
                    f"({old_price:.2f} → {new_price:.2f}, {variation:.1f}%)"
                )
                return SyncDecision.BLOCKED, {
                    'sku': product.sku,
                    'old_price': old_price,
                    'new_price': new_price,
                    'variation_percent': variation,
                }
        
        # Compare hashes
        old_hash_full = row['last_hash_full']
        old_hash_fast = row['last_hash_fast']
        
        if product.hash_full != old_hash_full:
            logger.debug(f"SKU {product.sku}: FULL_UPDATE (hash_full changed)")
            return SyncDecision.FULL_UPDATE, None
        
        if product.hash_fast != old_hash_fast:
            logger.debug(f"SKU {product.sku}: FAST_UPDATE (price/stock changed)")
            return SyncDecision.FAST_UPDATE, None
        
        logger.debug(f"SKU {product.sku}: SKIP (no changes)")
        return SyncDecision.SKIP, None
    
    def save_sync_result(
        self,
        sku: str,
        woo_id: Optional[int],
        hash_full: str,
        hash_fast: str,
        price: float,
    ):
        """Save sync result to database."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        cursor.execute(
            """
            INSERT INTO products (sku, woo_id, last_hash_full, last_hash_fast, last_price, last_sync, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                woo_id = COALESCE(?, woo_id),
                last_hash_full = ?,
                last_hash_fast = ?,
                last_price = ?,
                last_sync = ?
            """,
            (sku, woo_id, hash_full, hash_fast, price, now, now,
             woo_id, hash_full, hash_fast, price, now)
        )
        self.conn.commit()
    
    def get_woo_id(self, sku: str) -> Optional[int]:
        """Get WooCommerce product ID for a SKU."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT woo_id FROM products WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        return row['woo_id'] if row else None
    
    def get_last_price(self, sku: str) -> Optional[float]:
        """Get the last recorded price for a SKU."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT last_price FROM products WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        return row['last_price'] if row else None
    
    def get_all_skus(self) -> Set[str]:
        """Get all SKUs in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT sku FROM products")
        return {row['sku'] for row in cursor.fetchall()}
    
    def detect_ghost_skus(self, current_skus: Set[str]) -> List[str]:
        """
        Find SKUs in database that are NOT in current file.
        These are "ghost" products that should have stock zeroed.
        """
        db_skus = self.get_all_skus()
        ghost_skus = list(db_skus - current_skus)
        
        if ghost_skus:
            logger.warning(f"Detected {len(ghost_skus)} ghost SKUs not in current file")
        
        return ghost_skus
    
    def get_record(self, sku: str) -> Optional[ProductDBRecord]:
        """Get full record for a SKU."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products WHERE sku = ?", (sku,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return ProductDBRecord(
            sku=row['sku'],
            woo_id=row['woo_id'],
            last_hash_full=row['last_hash_full'],
            last_hash_fast=row['last_hash_fast'],
            last_price=row['last_price'],
            last_sync=datetime.fromisoformat(row['last_sync']) if row['last_sync'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else datetime.now(),
        )
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM products")
        total = cursor.fetchone()['total']
        
        cursor.execute("SELECT COUNT(*) as with_woo FROM products WHERE woo_id IS NOT NULL")
        with_woo = cursor.fetchone()['with_woo']
        
        return {
            'total_products': total,
            'synced_to_woo': with_woo,
            'pending_sync': total - with_woo,
        }
    
    # =========================================================================
    # PRICE HISTORY METHODS
    # =========================================================================
    
    def save_price_history(
        self,
        sku: str,
        old_price: Optional[float],
        new_price: float,
        sync_type: str = "UPDATE"
    ):
        """Save a price change to history for analytics."""
        if old_price is None:
            variation = 0.0
        else:
            variation = ((new_price - old_price) / old_price * 100) if old_price > 0 else 0.0
        
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO price_history (sku, old_price, new_price, variation_percent, recorded_at, sync_type)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (sku, old_price, new_price, round(variation, 2), datetime.now().isoformat(), sync_type)
        )
        self.conn.commit()
    
    def get_price_history(self, sku: str, limit: int = 10) -> List[Dict]:
        """Get price history for a specific SKU."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT old_price, new_price, variation_percent, recorded_at, sync_type
            FROM price_history
            WHERE sku = ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (sku, limit)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_recent_price_changes(self, limit: int = 20) -> List[Dict]:
        """Get recent price changes across all products."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT ph.sku, p.woo_id, ph.old_price, ph.new_price, 
                   ph.variation_percent, ph.recorded_at, ph.sync_type
            FROM price_history ph
            LEFT JOIN products p ON ph.sku = p.sku
            WHERE ph.variation_percent != 0
            ORDER BY ph.recorded_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    # =========================================================================
    # PRODUCT IMAGES METHODS (for image curation)
    # =========================================================================
    
    def get_pending_images(self, limit: int = 50) -> List[Dict]:
        """
        Get products without curated images.
        Returns products from main table that don't have a curated image.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT p.sku, p.woo_id
            FROM products p
            LEFT JOIN product_images pi ON p.sku = pi.sku
            WHERE pi.sku IS NULL OR pi.status = 'pending'
            ORDER BY p.last_sync DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_pending_images_count(self) -> int:
        """Get count of products without curated images."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM products p
            LEFT JOIN product_images pi ON p.sku = pi.sku
            WHERE pi.sku IS NULL OR pi.status = 'pending'
            """
        )
        return cursor.fetchone()['count']
    
    def save_image_selection(
        self,
        sku: str,
        image_url: str,
        thumbnail_urls: Optional[List[str]] = None,
        source: str = "duckduckgo"
    ):
        """Save image selection for a product."""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        thumbnails_json = json.dumps(thumbnail_urls) if thumbnail_urls else None
        
        cursor.execute(
            """
            INSERT INTO product_images (sku, image_url, thumbnail_urls, status, source, curated_at)
            VALUES (?, ?, ?, 'curated', ?, ?)
            ON CONFLICT(sku) DO UPDATE SET
                image_url = ?,
                thumbnail_urls = ?,
                status = 'curated',
                source = ?,
                curated_at = ?
            """,
            (sku, image_url, thumbnails_json, source, now,
             image_url, thumbnails_json, source, now)
        )
        self.conn.commit()
        logger.info(f"Saved image selection for SKU {sku}")
    
    def get_image_status(self, sku: str) -> Optional[Dict]:
        """Get image status for a SKU."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM product_images WHERE sku = ?",
            (sku,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        
        result = dict(row)
        if result.get('thumbnail_urls'):
            result['thumbnail_urls'] = json.loads(result['thumbnail_urls'])
        return result
    
    def apply_image_to_family(self, source_sku: str, prefix_length: int = 7) -> int:
        """
        Apply image from source SKU to all SKUs with same prefix.
        Returns count of affected products.
        """
        # Get the source image
        source_image = self.get_image_status(source_sku)
        if not source_image or not source_image.get('image_url'):
            return 0
        
        prefix = source_sku[:prefix_length]
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        # Find all products with same prefix that don't have curated images
        cursor.execute(
            """
            SELECT p.sku FROM products p
            LEFT JOIN product_images pi ON p.sku = pi.sku
            WHERE p.sku LIKE ? || '%'
            AND p.sku != ?
            AND (pi.sku IS NULL OR pi.status = 'pending')
            """,
            (prefix, source_sku)
        )
        
        family_skus = [row['sku'] for row in cursor.fetchall()]
        
        for family_sku in family_skus:
            cursor.execute(
                """
                INSERT INTO product_images (sku, image_url, status, source, curated_at)
                VALUES (?, ?, 'curated', 'family', ?)
                ON CONFLICT(sku) DO UPDATE SET
                    image_url = ?,
                    status = 'curated',
                    source = 'family',
                    curated_at = ?
                """,
                (family_sku, source_image['image_url'], now,
                 source_image['image_url'], now)
            )
        
        self.conn.commit()
        logger.info(f"Applied image from {source_sku} to {len(family_skus)} family products")
        return len(family_skus)
    
    def mark_image_uploaded(self, sku: str):
        """Mark image as uploaded to WooCommerce."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE product_images
            SET status = 'uploaded', uploaded_at = ?
            WHERE sku = ?
            """,
            (datetime.now().isoformat(), sku)
        )
        self.conn.commit()
    
    def get_curated_images(self, limit: int = 50) -> List[Dict]:
        """Get products with curated but not uploaded images."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT pi.*, p.woo_id
            FROM product_images pi
            JOIN products p ON pi.sku = p.sku
            WHERE pi.status = 'curated'
            ORDER BY pi.curated_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection."""
        self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
