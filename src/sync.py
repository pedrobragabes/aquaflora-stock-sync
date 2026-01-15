"""
AquaFlora Stock Sync - WooCommerce Sync Manager
Handles synchronization with WooCommerce API, including batch updates and retries.
"""

import logging
import time
from typing import Dict, List, Optional

from woocommerce import API as WooAPI

from .models import (
    EnrichedProduct, 
    SyncDecision, 
    SyncSummary, 
    PriceWarning,
    ProductChange,
    WooPayloadFull,
    WooPayloadFast,
)
from .database import ProductDatabase
from .notifications import NotificationService
from .exceptions import WooCommerceError, SyncError

logger = logging.getLogger(__name__)


class WooSyncManager:
    """
    Manages WooCommerce API synchronization.
    
    Features:
    - Dual hash strategy (full vs fast updates)
    - PriceGuard safety checks
    - Batch updates for performance
    - Retry with exponential backoff
    - Ghost SKU zeroing
    """
    
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds, doubles each retry
    BATCH_SIZE = 100  # WooCommerce API limit
    
    def __init__(
        self,
        woo_url: str,
        consumer_key: str,
        consumer_secret: str,
        dry_run: bool = False,
        price_guard_max_variation: float = 40.0,
        lite_mode: bool = False,
        allow_create: bool = False,
    ):
        """Initialize WooCommerce API client."""
        self.wcapi = WooAPI(
            url=woo_url,
            consumer_key=consumer_key,
            consumer_secret=consumer_secret,
            version="wc/v3",
            timeout=60,
        )
        self.dry_run = dry_run
        self.price_guard_max_variation = price_guard_max_variation
        self.lite_mode = lite_mode
        self.allow_create = allow_create
        
        mode_str = "LITE (Price/Stock only)" if lite_mode else "FULL"
        create_str = "CREATE enabled" if allow_create else "UPDATE only (safe)"
        logger.info(f"WooSyncManager initialized (mode={mode_str}, {create_str}, dry_run={dry_run})")
    
    def sync_products(
        self,
        products: List[EnrichedProduct],
        db: ProductDatabase,
        zero_ghost_stock: bool = False,  # DANGEROUS - only enable if file has ALL products
    ) -> SyncSummary:
        """
        Sync products to WooCommerce.
        
        Args:
            products: List of enriched products to sync
            db: Product database for state tracking
            zero_ghost_stock: Whether to zero stock for missing products
            
        Returns:
            SyncSummary with results
        """
        summary = SyncSummary(total_parsed=len(products))
        
        # Collect products by sync decision
        new_products = []
        full_updates = []
        fast_updates = []
        skipped_not_on_site = 0
        
        current_skus = {p.sku for p in products}
        
        for product in products:
            decision, warning = db.get_sync_decision(
                product, self.price_guard_max_variation
            )
            
            if decision == SyncDecision.NEW:
                # WHITELIST CHECK: Only create if allowed or already on site
                if self.allow_create:
                    new_products.append(product)
                elif db.exists_on_site(product.sku):
                    # Product exists on site (mapped), treat as update
                    full_updates.append(product)
                else:
                    # NOT on site and creation not allowed - SKIP for safety
                    skipped_not_on_site += 1
                    logger.debug(f"SKU {product.sku}: SKIPPED (not on site, creation disabled)")
            elif decision == SyncDecision.FULL_UPDATE:
                full_updates.append(product)
            elif decision == SyncDecision.FAST_UPDATE:
                fast_updates.append(product)
            elif decision == SyncDecision.BLOCKED:
                # Add name to price warning for rich notifications
                warning['name'] = product.name
                summary.price_warnings.append(PriceWarning(**warning))
                # Track as blocked change
                summary.product_changes.append(ProductChange(
                    sku=product.sku,
                    name=product.name,
                    change_type='blocked',
                    old_price=warning.get('old_price'),
                    new_price=warning.get('new_price'),
                    new_stock=product.stock,
                    price_variation=warning.get('variation_percent', 0),
                ))
            # SKIP: do nothing
            else:
                summary.skipped += 1
        
        if skipped_not_on_site > 0:
            logger.warning(
                f"🛡️  SAFETY: Skipped {skipped_not_on_site} products NOT on site (use --allow-create to enable)"
            )
        
        logger.info(
            f"Sync decisions: {len(new_products)} new, {len(full_updates)} full, "
            f"{len(fast_updates)} fast, {summary.skipped} skip, "
            f"{len(summary.price_warnings)} blocked, {skipped_not_on_site} not-on-site"
        )
        
        # In LITE mode, treat all updates as fast updates (price/stock only)
        if self.lite_mode:
            # In lite mode, new products still need full payload, but updates are lite
            logger.info("LITE MODE: Full updates will be treated as price/stock only")
            fast_updates.extend(full_updates)
            full_updates = []
        
        # Process new products (always need full payload for creation)
        for product in new_products:
            woo_id = self._create_product(product)
            if woo_id:
                db.save_sync_result(
                    product.sku, woo_id,
                    product.hash_full, product.hash_fast,
                    float(product.price)
                )
                summary.new_products += 1
                # Track as new product
                summary.product_changes.append(ProductChange(
                    sku=product.sku,
                    name=product.name,
                    change_type='new',
                    old_price=None,
                    new_price=float(product.price),
                    old_stock=None,
                    new_stock=product.stock,
                    price_variation=0,
                ))
            else:
                summary.errors.append(f"Failed to create: {product.sku}")
        
        # Process full updates (skipped in LITE mode)
        for product in full_updates:
            woo_id = db.get_woo_id(product.sku)
            if woo_id and self._update_product_full(woo_id, product):
                db.save_sync_result(
                    product.sku, woo_id,
                    product.hash_full, product.hash_fast,
                    float(product.price)
                )
                summary.full_updates += 1
            else:
                summary.errors.append(f"Failed to update (full): {product.sku}")
        
        # Process fast updates (batch for efficiency)
        if fast_updates:
            self._batch_fast_updates(fast_updates, db, summary)
        
        # Handle ghost SKUs
        if zero_ghost_stock:
            ghost_skus = db.detect_ghost_skus(current_skus)
            if ghost_skus:
                self._zero_ghost_stock(ghost_skus, db, summary)
        
        summary.success = len(summary.errors) == 0
        summary.total_enriched = len(products)
        
        logger.info(
            f"Sync complete: {summary.new_products} created, "
            f"{summary.full_updates} full updates, {summary.fast_updates} fast updates"
        )
        
        return summary
    
    def _create_product(self, product: EnrichedProduct) -> Optional[int]:
        """Create a new product in WooCommerce."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would create product: {product.sku}")
            return 99999  # Fake ID for dry run
        
        payload = WooPayloadFull.from_enriched(product)
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.wcapi.post("products", payload.model_dump())
                
                if response.status_code in (200, 201):
                    woo_id = response.json().get('id')
                    logger.info(f"Created product {product.sku} (ID: {woo_id})")
                    return woo_id
                else:
                    error = WooCommerceError(
                        f"Create failed: {response.text[:100]}",
                        status_code=response.status_code,
                        sku=product.sku
                    )
                    last_error = error
                    
                    # Don't retry client errors (4xx)
                    if error.is_client_error:
                        logger.warning(f"⚠️ {error} (not retrying - client error)")
                        break
                    
                    logger.warning(f"⚠️ {error}")
                    
            except Exception as e:
                last_error = WooCommerceError(str(e), sku=product.sku)
                logger.error(f"❌ Error creating {product.sku}: {e}")
                
            # Retry with backoff (only for retryable errors)
            if attempt < self.MAX_RETRIES - 1:
                if last_error and hasattr(last_error, 'is_retryable') and not last_error.is_retryable:
                    break  # Don't retry non-retryable errors
                delay = self.RETRY_DELAY * (2 ** attempt)
                logger.info(f"🔄 Retrying in {delay}s (attempt {attempt + 2}/{self.MAX_RETRIES})...")
                time.sleep(delay)
        
        return None
    
    def _update_product_full(self, woo_id: int, product: EnrichedProduct) -> bool:
        """Update product with full payload."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would update product (full): {product.sku}")
            return True
        
        payload = WooPayloadFull.from_enriched(product)
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self.wcapi.put(f"products/{woo_id}", payload.model_dump())
                
                if response.status_code == 200:
                    logger.info(f"Updated (full) product {product.sku}")
                    return True
                else:
                    error = WooCommerceError(
                        f"Update failed: {response.status_code}",
                        status_code=response.status_code,
                        sku=product.sku
                    )
                    last_error = error
                    
                    if error.is_client_error:
                        logger.warning(f"⚠️ {error} (not retrying - client error)")
                        break
                    
                    logger.warning(f"⚠️ {error}")
                    
            except Exception as e:
                last_error = WooCommerceError(str(e), sku=product.sku)
                logger.error(f"❌ Error updating {product.sku}: {e}")
            
            if attempt < self.MAX_RETRIES - 1:
                if last_error and hasattr(last_error, 'is_retryable') and not last_error.is_retryable:
                    break
                delay = self.RETRY_DELAY * (2 ** attempt)
                logger.info(f"🔄 Retrying in {delay}s (attempt {attempt + 2}/{self.MAX_RETRIES})...")
                time.sleep(delay)
        
        return False
    
    def _batch_fast_updates(
        self,
        products: List[EnrichedProduct],
        db: ProductDatabase,
        summary: SyncSummary,
    ):
        """Process fast updates in batches for efficiency."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would batch update {len(products)} products")
            summary.fast_updates = len(products)
            return
        
        # Build batch payload - LITE MODE COMPATIBLE
        # Only sends: id, regular_price, stock_quantity, manage_stock, stock_status
        # Does NOT send: name, description, short_description, categories, images, attributes
        batch_data = []
        for product in products:
            woo_id = db.get_woo_id(product.sku)
            if woo_id:
                stock_status = 'instock' if product.stock > 0 else 'outofstock'
                batch_data.append({
                    'id': woo_id,
                    'regular_price': str(product.price),
                    'stock_quantity': product.stock,
                    'manage_stock': True,
                    'stock_status': stock_status,
                })
        
        # Process in chunks of BATCH_SIZE
        for i in range(0, len(batch_data), self.BATCH_SIZE):
            chunk = batch_data[i:i + self.BATCH_SIZE]
            
            try:
                response = self.wcapi.post(
                    "products/batch",
                    {"update": chunk}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    updated = len(result.get('update', []))
                    summary.fast_updates += updated
                    logger.info(f"Batch updated {updated} products")
                else:
                    logger.warning(f"Batch update failed: {response.status_code}")
                    summary.errors.append(f"Batch update failed: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Batch update error: {e}")
                summary.errors.append(f"Batch error: {str(e)}")
        
        # Update hashes in DB for fast updates and track changes
        for product in products:
            woo_id = db.get_woo_id(product.sku)
            if woo_id:
                # Get old price for tracking
                old_price = db.get_last_price(product.sku)
                new_price = float(product.price)
                
                # Calculate variation
                price_variation = 0.0
                if old_price and old_price > 0:
                    price_variation = ((new_price - old_price) / old_price) * 100
                
                # Track the change
                summary.product_changes.append(ProductChange(
                    sku=product.sku,
                    name=product.name,
                    change_type='updated',
                    old_price=old_price,
                    new_price=new_price,
                    old_stock=None,  # Could be added if needed
                    new_stock=product.stock,
                    price_variation=round(price_variation, 2),
                ))
                
                db.save_sync_result(
                    product.sku, woo_id,
                    product.hash_full, product.hash_fast,
                    new_price
                )
    
    def _zero_ghost_stock(
        self,
        ghost_skus: List[str],
        db: ProductDatabase,
        summary: SyncSummary,
    ):
        """Zero stock for products not in current file."""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would zero stock for {len(ghost_skus)} ghost SKUs")
            summary.ghost_skus_zeroed = ghost_skus
            return
        
        batch_data = []
        for sku in ghost_skus:
            woo_id = db.get_woo_id(sku)
            if woo_id:
                batch_data.append({
                    'id': woo_id,
                    'stock_quantity': 0,
                    'status': 'draft',  # Also unpublish
                })
        
        if not batch_data:
            return
        
        # Process in batches
        for i in range(0, len(batch_data), self.BATCH_SIZE):
            chunk = batch_data[i:i + self.BATCH_SIZE]
            
            try:
                response = self.wcapi.post(
                    "products/batch",
                    {"update": chunk}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    zeroed = len(result.get('update', []))
                    summary.ghost_skus_zeroed.extend(
                        ghost_skus[i:i + zeroed]
                    )
                    logger.info(f"Zeroed stock for {zeroed} ghost products")
                    
            except Exception as e:
                logger.error(f"Error zeroing ghost stock: {e}")
    
    def find_product_by_sku(self, sku: str) -> Optional[int]:
        """Find WooCommerce product ID by SKU."""
        try:
            response = self.wcapi.get(f"products?sku={sku}")
            if response.status_code == 200:
                products = response.json()
                if products:
                    return products[0]['id']
        except Exception as e:
            logger.error(f"Error finding product {sku}: {e}")
        
        return None
