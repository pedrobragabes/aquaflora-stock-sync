"""
Tests for image_scraper module.
"""

import pytest
from src.image_scraper import clean_product_name, is_bad_image_url


class TestCleanProductName:
    """Tests for clean_product_name function."""
    
    def test_removes_promotional_text(self):
        """Should remove promotional words."""
        assert "vodka absolut" in clean_product_name("VODKA ABSOLUT PROMOÇÃO")
        assert "promoção" not in clean_product_name("VODKA ABSOLUT PROMOÇÃO")
    
    def test_removes_special_characters(self):
        """Should remove special characters like ! @ # $."""
        result = clean_product_name("Produto!!! Especial @#$")
        assert "!" not in result
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
    
    def test_normalizes_whitespace(self):
        """Should normalize multiple spaces to single space."""
        result = clean_product_name("Produto    com    espaços")
        assert "    " not in result
        assert " " in result
    
    def test_lowercase_output(self):
        """Should return lowercase text."""
        result = clean_product_name("PRODUTO MAIÚSCULO")
        assert result == result.lower()
    
    def test_empty_string(self):
        """Should handle empty string."""
        assert clean_product_name("") == ""
    
    def test_none_input(self):
        """Should handle None input."""
        assert clean_product_name(None) == ""
    
    def test_removes_off_percentage(self):
        """Should remove percentage off text."""
        result = clean_product_name("Cerveja 50% off")
        # The pattern removes "50% off" as a unit, so % might not be present
        assert "off" not in result
        # The actual text should remain
        assert "cerveja" in result


class TestIsBadImageUrl:
    """Tests for is_bad_image_url function."""
    
    def test_detects_placeholder(self):
        """Should detect placeholder images."""
        assert is_bad_image_url("https://site.com/placeholder.png") is True
        assert is_bad_image_url("https://site.com/blank.jpg") is True
    
    def test_detects_icons(self):
        """Should detect icon images."""
        assert is_bad_image_url("https://site.com/icon-cart.png") is True
        assert is_bad_image_url("https://site.com/favicon.ico") is True
    
    def test_detects_logos(self):
        """Should detect logo images."""
        assert is_bad_image_url("https://site.com/logo.png") is True
    
    def test_detects_tracking_pixels(self):
        """Should detect 1x1 tracking pixels."""
        assert is_bad_image_url("https://site.com/1x1.gif") is True
        assert is_bad_image_url("https://site.com/pixel.png") is True
    
    def test_accepts_valid_urls(self):
        """Should accept valid product image URLs."""
        assert is_bad_image_url("https://site.com/product-123.jpg") is False
        assert is_bad_image_url("https://cdn.store.com/images/vodka-absolut.png") is False
    
    def test_case_insensitive(self):
        """Should be case insensitive."""
        assert is_bad_image_url("https://site.com/PLACEHOLDER.PNG") is True
        assert is_bad_image_url("https://site.com/Logo.jpg") is True
