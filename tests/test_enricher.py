"""
AquaFlora Stock Sync - Enricher Tests
Tests for ProductEnricher brand detection, weight extraction, and name formatting.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.enricher import ProductEnricher
from src.models import RawProduct


@pytest.fixture
def enricher():
    """Create a ProductEnricher instance."""
    return ProductEnricher()


class TestBrandDetection:
    """Tests for brand detection functionality."""
    
    def test_detect_royal_canin(self, enricher):
        """Should detect Royal Canin brand."""
        raw = RawProduct(
            sku="123", name="RACAO ROYAL CANIN MINI ADULT",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.brand == "Royal Canin"
    
    def test_detect_brand_case_insensitive(self, enricher):
        """Brand detection should be case-insensitive."""
        raw = RawProduct(
            sku="123", name="racao royal canin adulto",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.brand == "Royal Canin"
    
    def test_detect_nexgard(self, enricher):
        """Should detect NexGard brand."""
        raw = RawProduct(
            sku="123", name="NEXGARD SPECTRA 7 A 15KG",
            stock=1, minimum=1, price=100, cost=50, department="VET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.brand == "NexGard"
    
    def test_detect_bravecto(self, enricher):
        """Should detect Bravecto brand."""
        raw = RawProduct(
            sku="123", name="BRAVECTO CAES 10-20KG",
            stock=1, minimum=1, price=100, cost=50, department="VET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.brand == "Bravecto"
    
    def test_no_brand_detected(self, enricher):
        """Should return None when no brand matches."""
        raw = RawProduct(
            sku="123", name="PRODUTO GENERICO SEM MARCA",
            stock=1, minimum=1, price=100, cost=50, department="GERAL"
        )
        enriched = enricher.enrich(raw)
        assert enriched.brand is None


class TestWeightExtraction:
    """Tests for weight extraction from product names."""
    
    def test_extract_kg(self, enricher):
        """Should extract weight in kg."""
        raw = RawProduct(
            sku="123", name="RACAO CACHORRO 10KG",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_kg == 10.0
    
    def test_extract_kg_decimal(self, enricher):
        """Should extract decimal weight in kg."""
        raw = RawProduct(
            sku="123", name="RACAO GATO 7,5KG",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_kg == 7.5
    
    def test_extract_grams(self, enricher):
        """Should convert grams to kg."""
        raw = RawProduct(
            sku="123", name="SACHE GATO 500G",
            stock=1, minimum=1, price=10, cost=5, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_kg == 0.5

    def test_extract_multiple_units(self, enricher):
        """Should extract total and unit weight for 2x10kg."""
        raw = RawProduct(
            sku="123", name="RACAO PREMIUM 2x10kg",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_total_kg == 20.0
        assert enriched.weight_unit_kg == 10.0
        assert enriched.weight_qty == 2

    def test_extract_c2_pattern(self, enricher):
        """Should extract total and unit weight for 15kg c/2."""
        raw = RawProduct(
            sku="123", name="RACAO 15kg c/2",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_total_kg == 30.0
        assert enriched.weight_unit_kg == 15.0
        assert enriched.weight_qty == 2

    def test_extract_plus_pattern(self, enricher):
        """Should sum weights when name contains plus sign."""
        raw = RawProduct(
            sku="123", name="RACAO 10kg + 2kg",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_total_kg == 12.0
        assert enriched.weight_qty == 2
    
    def test_no_weight_found(self, enricher):
        """Should return None when no weight in name."""
        raw = RawProduct(
            sku="123", name="BRINQUEDO CACHORRO BORRACHA",
            stock=1, minimum=1, price=20, cost=10, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert enriched.weight_kg is None


class TestNameFormatting:
    """Tests for product name formatting."""
    
    def test_title_case(self, enricher):
        """Should convert to title case."""
        raw = RawProduct(
            sku="123", name="RACAO CACHORRO ADULTO",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        # Should be title case, not all caps
        assert enriched.name != "RACAO CACHORRO ADULTO"
        assert enriched.name[0].isupper()
    
    def test_accent_corrections(self, enricher):
        """Should apply accent corrections."""
        raw = RawProduct(
            sku="123", name="RACAO PARA CAES ADULTOS",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        # Should have proper accents
        assert "Ração" in enriched.name or "ração" in enriched.name.lower()

    def test_remove_duplicate_weight_tokens(self, enricher):
        """Should remove duplicated weight tokens in name."""
        raw = RawProduct(
            sku="123", name="RACAO 15KG 15KG",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert "15" in enriched.name
        assert "15Kg 15Kg" not in enriched.name


class TestDescriptionGeneration:
    """Tests for description generation."""
    
    def test_short_description_includes_brand(self, enricher):
        """Short description should include brand."""
        raw = RawProduct(
            sku="123", name="RACAO ROYAL CANIN ADULTO",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert "Royal Canin" in enriched.short_description
    
    def test_short_description_includes_category(self, enricher):
        """Short description should include category."""
        raw = RawProduct(
            sku="123", name="PRODUTO TESTE",
            stock=1, minimum=1, price=100, cost=50, department="PET_RACOES"
        )
        enriched = enricher.enrich(raw)
        assert "Pet" in enriched.short_description or "Rações" in enriched.short_description
    
    def test_html_description_is_html(self, enricher):
        """Description should be valid HTML."""
        raw = RawProduct(
            sku="123", name="PRODUTO TESTE",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        enriched = enricher.enrich(raw)
        assert "<div" in enriched.description
        assert "</div>" in enriched.description


class TestHashing:
    """Tests for product hash generation."""
    
    def test_hash_full_changes_with_name(self, enricher):
        """hash_full should change when name changes."""
        raw1 = RawProduct(
            sku="123", name="PRODUTO A",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        raw2 = RawProduct(
            sku="123", name="PRODUTO B",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        
        enriched1 = enricher.enrich(raw1)
        enriched2 = enricher.enrich(raw2)
        
        assert enriched1.hash_full != enriched2.hash_full
    
    def test_hash_fast_changes_with_price(self, enricher):
        """hash_fast should change when price changes."""
        raw1 = RawProduct(
            sku="123", name="PRODUTO",
            stock=1, minimum=1, price=100, cost=50, department="PET"
        )
        raw2 = RawProduct(
            sku="123", name="PRODUTO",
            stock=1, minimum=1, price=150, cost=50, department="PET"
        )
        
        enriched1 = enricher.enrich(raw1)
        enriched2 = enricher.enrich(raw2)
        
        assert enriched1.hash_fast != enriched2.hash_fast
    
    def test_hash_fast_stable_with_same_data(self, enricher):
        """hash_fast should be same for identical price/stock."""
        raw1 = RawProduct(
            sku="123", name="PRODUTO A",  # Different name
            stock=10, minimum=1, price=100, cost=50, department="PET"
        )
        raw2 = RawProduct(
            sku="123", name="PRODUTO B",  # Different name
            stock=10, minimum=1, price=100, cost=50, department="PET"
        )
        
        enriched1 = enricher.enrich(raw1)
        enriched2 = enricher.enrich(raw2)
        
        # hash_fast only considers sku/price/stock, so should be same
        assert enriched1.hash_fast == enriched2.hash_fast
