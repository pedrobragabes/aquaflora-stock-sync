"""
AquaFlora Stock Sync - Image Curator Service
High-level service for curating product images with prefetch support.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from .database import ProductDatabase
from .image_scraper import (
    download_and_validate,
    process_and_save_image,
    search_and_get_thumbnails,
)

logger = logging.getLogger(__name__)


class ImageCurator:
    """
    Service for curating product images.
    
    Features:
    - Get pending products (without curated images)
    - Search images for a product
    - Save user selection
    - Apply image to product family (same prefix)
    - Prefetch next product for better UX
    """
    
    def __init__(self, db: ProductDatabase, images_dir: Optional[Path] = None):
        """
        Initialize curator service.
        
        Args:
            db: ProductDatabase instance
            images_dir: Directory to save processed images
        """
        self.db = db
        self.images_dir = images_dir or Path("data/images")
        self._prefetch_cache: Dict[str, List[dict]] = {}
        self._executor = ThreadPoolExecutor(max_workers=2)
    
    def get_pending_products(self, limit: int = 50) -> List[Dict]:
        """
        Get products without curated images.
        
        Returns list of dicts with:
        - sku: Product SKU
        - woo_id: WooCommerce ID (if exists)
        """
        return self.db.get_pending_images(limit=limit)
    
    def get_pending_count(self) -> int:
        """Get count of products without curated images."""
        return self.db.get_pending_images_count()
    
    def get_product_info(self, sku: str) -> Optional[Dict]:
        """
        Get product info for display in curator UI.
        
        Returns:
            Dict with sku, woo_id, image_status, or None if not found
        """
        record = self.db.get_record(sku)
        if not record:
            return None
        
        image_status = self.db.get_image_status(sku)
        
        return {
            "sku": record.sku,
            "woo_id": record.woo_id,
            "last_price": record.last_price,
            "image_status": image_status.get("status") if image_status else "pending",
            "image_url": image_status.get("image_url") if image_status else None,
        }
    
    def search_images(
        self,
        sku: str,
        product_name: str,
        ean: str = "",
        category: str = "",
        max_results: int = 6
    ) -> List[dict]:
        """
        Search images for a product.
        
        First checks prefetch cache, then performs search if not cached.
        
        Args:
            sku: Product SKU
            product_name: Product description/name
            ean: EAN/barcode (optional)
            category: Product category (optional)
            max_results: Max images to return
        
        Returns:
            List of image candidates with url, thumbnail, title, source, width, height
        """
        # Check prefetch cache
        if sku in self._prefetch_cache:
            logger.debug(f"Using cached results for SKU {sku}")
            results = self._prefetch_cache.pop(sku)
            return results
        
        # Perform search
        return search_and_get_thumbnails(
            product_name=product_name,
            sku=sku,
            ean=ean,
            category=category,
            max_results=max_results
        )
    
    def prefetch_next(
        self,
        next_sku: str,
        product_name: str,
        ean: str = "",
        category: str = ""
    ):
        """
        Prefetch images for next product in background.
        Improves UX by having results ready when user moves to next product.
        
        Args:
            next_sku: SKU of next product to prefetch
            product_name: Product description/name
            ean: EAN/barcode (optional)
            category: Product category (optional)
        """
        if next_sku in self._prefetch_cache:
            return
        
        def _prefetch():
            try:
                results = search_and_get_thumbnails(
                    product_name=product_name,
                    sku=next_sku,
                    ean=ean,
                    category=category,
                    max_results=6
                )
                self._prefetch_cache[next_sku] = results
                logger.debug(f"Prefetched {len(results)} images for SKU {next_sku}")
            except Exception as e:
                logger.warning(f"Prefetch failed for SKU {next_sku}: {e}")
        
        self._executor.submit(_prefetch)
    
    def save_selection(
        self,
        sku: str,
        image_url: str,
        thumbnail_urls: Optional[List[str]] = None,
        source: str = "duckduckgo",
        download: bool = True
    ) -> bool:
        """
        Save image selection for a product.
        
        Args:
            sku: Product SKU
            image_url: Selected image URL
            thumbnail_urls: All candidate URLs shown (for reference)
            source: Search engine that provided the image
            download: If True, download and process the image
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Download and process if requested
            if download:
                content, w, h = download_and_validate(image_url)
                if content:
                    saved_path = process_and_save_image(
                        content=content,
                        sku=sku,
                        output_dir=self.images_dir
                    )
                    if saved_path:
                        logger.info(f"Downloaded and saved image for SKU {sku}: {saved_path}")
            
            # Save to database
            self.db.save_image_selection(
                sku=sku,
                image_url=image_url,
                thumbnail_urls=thumbnail_urls,
                source=source
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save selection for SKU {sku}: {e}")
            return False
    
    def apply_to_family(self, source_sku: str, prefix_length: int = 7) -> int:
        """
        Apply image from source SKU to all products with same prefix.
        
        Useful for product variants (different sizes, colors) that share
        the same image.
        
        Args:
            source_sku: SKU with the curated image
            prefix_length: Number of characters to match (default 7)
        
        Returns:
            Number of products updated
        """
        return self.db.apply_image_to_family(
            source_sku=source_sku,
            prefix_length=prefix_length
        )
    
    def skip_product(self, sku: str):
        """
        Skip a product (mark as pending with no image).
        Does not save any selection, just removes from prefetch cache.
        """
        if sku in self._prefetch_cache:
            del self._prefetch_cache[sku]
    
    def get_stats(self) -> Dict:
        """
        Get curator statistics.
        
        Returns:
            Dict with pending_count, curated_count, uploaded_count
        """
        pending = self.db.get_pending_images_count()
        
        # Get curated and uploaded counts
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT status, COUNT(*) as count FROM product_images GROUP BY status"
        )
        status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}
        
        return {
            "pending_count": pending,
            "curated_count": status_counts.get("curated", 0),
            "uploaded_count": status_counts.get("uploaded", 0),
        }
    
    def get_curated_for_upload(self, limit: int = 50) -> List[Dict]:
        """
        Get products with curated images ready for upload to WooCommerce.
        """
        return self.db.get_curated_images(limit=limit)
    
    def mark_uploaded(self, sku: str):
        """Mark image as uploaded to WooCommerce."""
        self.db.mark_image_uploaded(sku)
    
    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        self._prefetch_cache.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
