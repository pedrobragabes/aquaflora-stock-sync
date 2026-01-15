"""
AquaFlora Stock Sync - Parser Tests
Tests for AthosParser CSV parsing functionality.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parser import AthosParser, parse_brazilian_number
from src.models import RawProduct


class TestParseBrazilianNumber:
    """Tests for the parse_brazilian_number utility function."""
    
    def test_brazilian_format_with_thousands(self):
        """1.234,56 should become 1234.56"""
        result = parse_brazilian_number("1.234,56")
        assert result == 1234.56
    
    def test_brazilian_format_simple(self):
        """100,00 should become 100.0"""
        result = parse_brazilian_number("100,00")
        assert result == 100.0
    
    def test_american_format(self):
        """1000.50 should stay 1000.50"""
        result = parse_brazilian_number("1000.50")
        assert result == 1000.50
    
    def test_integer_string(self):
        """1000 should become 1000.0"""
        result = parse_brazilian_number("1000")
        assert result == 1000.0
    
    def test_empty_string(self):
        """Empty string should return 0.0"""
        result = parse_brazilian_number("")
        assert result == 0.0
    
    def test_none_value(self):
        """None should return 0.0"""
        result = parse_brazilian_number(None)
        assert result == 0.0
    
    def test_already_float(self):
        """Float value should pass through"""
        result = parse_brazilian_number(99.90)
        assert result == 99.90
    
    def test_integer(self):
        """Integer value should become float"""
        result = parse_brazilian_number(100)
        assert result == 100.0


class TestAthosParser:
    """Tests for the AthosParser class."""
    
    def test_parser_initialization(self):
        """Parser should initialize without errors."""
        parser = AthosParser()
        assert parser is not None
    
    def test_parse_valid_file(self, sample_csv_file):
        """Parser should extract products from valid CSV file."""
        parser = AthosParser()
        products = parser.parse_file(sample_csv_file)
        
        # Should find products
        assert len(products) >= 1
        
        # Products should be RawProduct instances
        assert all(isinstance(p, RawProduct) for p in products)
    
    def test_parse_extracts_sku(self, sample_csv_file):
        """Parser should extract SKU correctly."""
        parser = AthosParser()
        products = parser.parse_file(sample_csv_file)
        
        skus = [p.sku for p in products]
        assert "12345" in skus or "67890" in skus
    
    def test_garbage_lines_ignored(self, sample_csv_file):
        """Parser should ignore garbage lines like totals and headers."""
        parser = AthosParser()
        products = parser.parse_file(sample_csv_file)
        
        # Should not include "Total" or pagination as products
        for p in products:
            assert "Total" not in p.name
            assert "Página" not in p.name
            assert "CNPJ" not in p.name
    
    def test_parse_empty_file(self, tmp_path):
        """Parser should handle empty file gracefully."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("", encoding="utf-8")
        
        parser = AthosParser()
        products = parser.parse_file(empty_file)
        
        assert products == []
    
    def test_parse_garbage_only_file(self, tmp_path):
        """Parser should return empty list for file with only garbage."""
        garbage_file = tmp_path / "garbage.csv"
        garbage_file.write_text(
            '"Total Venda:","1000,00"\n"Página 1 de 1"\n',
            encoding="utf-8"
        )
        
        parser = AthosParser()
        products = parser.parse_file(garbage_file)
        
        assert products == []


class TestRawProductValidation:
    """Tests for RawProduct model validation."""
    
    def test_sku_cleaning(self):
        """SKU should only contain digits."""
        product = RawProduct(
            sku="ABC12345XY",
            name="Test Product",
            stock=10,
            minimum=1,
            price=100.0,
            cost=50.0,
            department="TEST",
        )
        assert product.sku == "12345"
    
    def test_brazilian_price_parsing(self):
        """Brazilian format prices should be parsed correctly."""
        product = RawProduct(
            sku="123",
            name="Test",
            stock=1,
            minimum=1,
            price="1.234,56",  # Brazilian format
            cost="800,00",
            department="TEST",
        )
        assert product.price == 1234.56
        assert product.cost == 800.00
    
    def test_american_price_parsing(self):
        """American format prices should be parsed correctly."""
        product = RawProduct(
            sku="123",
            name="Test",
            stock=1,
            minimum=1,
            price="1,234.56",  # American format
            cost="800.00",
            department="TEST",
        )
        assert product.price == 1234.56
        assert product.cost == 800.00
