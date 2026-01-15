"""
AquaFlora Stock Sync - Models Tests
Tests for Pydantic models and data validation.
"""

import pytest
from pathlib import Path
from decimal import Decimal
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    RawProduct, 
    EnrichedProduct, 
    SyncDecision, 
    SyncSummary,
    PriceWarning,
    ProductChange,
    WooPayloadFull,
    WooPayloadFast,
)


class TestRawProduct:
    """Tests for RawProduct model."""
    
    def test_sku_removes_non_digits(self):
        """SKU should only contain digits."""
        product = RawProduct(
            sku="ABC-123-XY",
            name="Test", stock=1, minimum=1,
            price=100, cost=50, department="TEST"
        )
        assert product.sku == "123"
    
    def test_empty_sku_becomes_empty_string(self):
        """Empty SKU should become empty string."""
        product = RawProduct(
            sku="ABCXYZ",  # No digits
            name="Test", stock=1, minimum=1,
            price=100, cost=50, department="TEST"
        )
        assert product.sku == ""


class TestEnrichedProduct:
    """Tests for EnrichedProduct model."""
    
    def test_margin_percent_calculation(self):
        """Margin should be calculated correctly."""
        product = EnrichedProduct(
            sku="123", name="Test", name_original="TEST",
            stock=10, price=Decimal("200"), cost=Decimal("100"),
            minimum=1, category="Test", category_original="TEST",
            short_description="", description="", tags=[]
        )
        # (200-100)/100 * 100 = 100%
        assert product.margin_percent == 100.0
    
    def test_margin_zero_cost(self):
        """Zero cost should return 0% margin."""
        product = EnrichedProduct(
            sku="123", name="Test", name_original="TEST",
            stock=10, price=Decimal("100"), cost=Decimal("0"),
            minimum=1, category="Test", category_original="TEST",
            short_description="", description="", tags=[]
        )
        assert product.margin_percent == 0.0
    
    def test_hash_full_deterministic(self):
        """Same product should have same hash_full."""
        product1 = EnrichedProduct(
            sku="123", name="Test", name_original="TEST",
            stock=10, price=Decimal("100"), cost=Decimal("50"),
            minimum=1, category="Cat", category_original="CAT",
            short_description="short", description="long", tags=["a"]
        )
        product2 = EnrichedProduct(
            sku="123", name="Test", name_original="TEST",
            stock=10, price=Decimal("100"), cost=Decimal("50"),
            minimum=1, category="Cat", category_original="CAT",
            short_description="short", description="long", tags=["a"]
        )
        assert product1.hash_full == product2.hash_full
    
    def test_hash_fast_only_price_stock(self):
        """hash_fast should only consider sku/price/stock."""
        product1 = EnrichedProduct(
            sku="123", name="Name A", name_original="A",
            stock=10, price=Decimal("100"), cost=Decimal("50"),
            minimum=1, category="Cat1", category_original="C1",
            short_description="short1", description="long1", tags=["a"]
        )
        product2 = EnrichedProduct(
            sku="123", name="Name B", name_original="B",  # Different name
            stock=10, price=Decimal("100"), cost=Decimal("50"),
            minimum=1, category="Cat2", category_original="C2",  # Different cat
            short_description="short2", description="long2", tags=["b"]
        )
        # hash_fast should be same (same sku/price/stock)
        assert product1.hash_fast == product2.hash_fast


class TestSyncSummary:
    """Tests for SyncSummary model."""
    
    def test_total_synced(self):
        """Should calculate total synced correctly."""
        summary = SyncSummary(
            new_products=5,
            full_updates=10,
            fast_updates=20,
        )
        assert summary.total_synced == 35
    
    def test_top_price_increases(self):
        """Should return top price increases."""
        summary = SyncSummary()
        summary.product_changes = [
            ProductChange(sku="1", name="A", change_type="updated", 
                         new_price=100, new_stock=1, price_variation=10),
            ProductChange(sku="2", name="B", change_type="updated", 
                         new_price=100, new_stock=1, price_variation=50),
            ProductChange(sku="3", name="C", change_type="updated", 
                         new_price=100, new_stock=1, price_variation=-5),
        ]
        
        increases = summary.top_price_increases
        assert len(increases) == 2
        assert increases[0].price_variation == 50  # Highest first
    
    def test_top_price_decreases(self):
        """Should return top price decreases."""
        summary = SyncSummary()
        summary.product_changes = [
            ProductChange(sku="1", name="A", change_type="updated", 
                         new_price=100, new_stock=1, price_variation=-30),
            ProductChange(sku="2", name="B", change_type="updated", 
                         new_price=100, new_stock=1, price_variation=-10),
            ProductChange(sku="3", name="C", change_type="updated", 
                         new_price=100, new_stock=1, price_variation=5),
        ]
        
        decreases = summary.top_price_decreases
        assert len(decreases) == 2
        assert decreases[0].price_variation == -30  # Biggest decrease first


class TestProductChange:
    """Tests for ProductChange model."""
    
    def test_price_direction_new(self):
        """New product should show 🆕 emoji."""
        change = ProductChange(
            sku="123", name="Test", change_type="new",
            old_price=None, new_price=100, new_stock=1
        )
        assert change.price_direction == "🆕"
    
    def test_price_direction_increase(self):
        """Price increase should show 📈 emoji."""
        change = ProductChange(
            sku="123", name="Test", change_type="updated",
            old_price=100, new_price=150, new_stock=1
        )
        assert change.price_direction == "📈"
    
    def test_price_direction_decrease(self):
        """Price decrease should show 📉 emoji."""
        change = ProductChange(
            sku="123", name="Test", change_type="updated",
            old_price=150, new_price=100, new_stock=1
        )
        assert change.price_direction == "📉"
    
    def test_price_direction_no_change(self):
        """No price change should show ➖ emoji."""
        change = ProductChange(
            sku="123", name="Test", change_type="updated",
            old_price=100, new_price=100, new_stock=1
        )
        assert change.price_direction == "➖"


class TestWooPayloadFull:
    """Tests for WooPayloadFull model."""
    
    def test_from_enriched(self, sample_enriched_product):
        """Should create payload from enriched product."""
        payload = WooPayloadFull.from_enriched(sample_enriched_product)
        
        assert payload.sku == sample_enriched_product.sku
        assert payload.name == sample_enriched_product.name
        assert payload.regular_price == str(sample_enriched_product.price)
        assert payload.stock_quantity == sample_enriched_product.stock
    
    def test_brand_as_attribute(self, sample_enriched_product):
        """Brand should be added as attribute."""
        payload = WooPayloadFull.from_enriched(sample_enriched_product)
        
        # Find Marca attribute
        marca = next((a for a in payload.attributes if a["name"] == "Marca"), None)
        assert marca is not None
        assert sample_enriched_product.brand in marca["options"]


class TestWooPayloadFast:
    """Tests for WooPayloadFast model."""
    
    def test_from_enriched(self, sample_enriched_product):
        """Should create minimal payload."""
        payload = WooPayloadFast.from_enriched(sample_enriched_product)
        
        assert payload.regular_price == str(sample_enriched_product.price)
        assert payload.stock_quantity == sample_enriched_product.stock
