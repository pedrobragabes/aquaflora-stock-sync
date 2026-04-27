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


class TestCleanCsvParser:
    """Tests for the clean (semicolon-separated) Athos export."""

    HEADER = "Codigo;CodigoBarras;Descricao;Unidade;Custo;Preco;Preco2;Estoque;DepartamentoCod;Departamento;MarcaCod;Marca\n"

    def _write(self, tmp_path: Path, body: str) -> Path:
        f = tmp_path / "athos.csv"
        f.write_text(self.HEADER + body, encoding="utf-8")
        return f

    def test_uses_codigobarras_as_sku_when_ean_present(self, tmp_path):
        f = self._write(
            tmp_path,
            "0000007584;7898011974747;ABRACADEIRA;UNID;4,24;10,00;0,00;2,000;0001;GERAL;000754;THOMPSON\n",
        )
        products = AthosParser().parse_file(f)
        assert len(products) == 1
        assert products[0].sku == "7898011974747"
        assert products[0].ean == "7898011974747"
        assert products[0].brand == "THOMPSON"

    def test_falls_back_to_codigo_when_ean_missing(self, tmp_path):
        # CodigoBarras is empty — parser must fall back to Codigo (col 0)
        # with leading zeros stripped.
        f = self._write(
            tmp_path,
            "0000003603;;ABRACADEIRA 13-16;UNID;1,18;2,50;0,00;81,000;0001;GERAL;000001;DIVERSAS\n",
        )
        products = AthosParser().parse_file(f)
        assert len(products) == 1
        assert products[0].sku == "3603"
        # Empty/short codes are NOT treated as valid EANs.
        assert products[0].ean is None

    def test_short_internal_code_is_not_an_ean(self, tmp_path):
        # CodigoBarras = "3603" (4 digits) is the internal code, not a real EAN.
        f = self._write(
            tmp_path,
            "0000003603;3603;ABRACADEIRA 13-16;UNID;1,18;2,50;0,00;81,000;0001;GERAL;000001;DIVERSAS\n",
        )
        products = AthosParser().parse_file(f)
        assert products[0].sku == "3603"
        assert products[0].ean is None  # Only 8/12/13/14-digit codes count as EAN

    def test_brazilian_decimals_for_stock_and_price(self, tmp_path):
        f = self._write(
            tmp_path,
            "0000004235;4235;ACQUA LINE;KG;3,86;8,09;0,00;17,619;0007;INSUMO;000331;SUPRA\n",
        )
        products = AthosParser().parse_file(f)
        assert products[0].stock == 17.619
        assert products[0].price == 8.09
        assert products[0].cost == 3.86


class TestRptRejection:
    """Crystal Reports binary files must be rejected with a clear error."""

    def test_rpt_extension_raises_parser_error(self, tmp_path):
        from src.exceptions import ParserError

        # An empty .rpt is enough — extension check happens before reading.
        rpt = tmp_path / "Athos.rpt"
        rpt.write_bytes(b"\x00\x00")

        parser = AthosParser()
        with pytest.raises(ParserError, match="Crystal Reports"):
            parser.parse_file(rpt)


class TestDeduplication:
    """Duplicate SKUs (e.g. from Excel float-rounding) must be coalesced."""

    HEADER = "Codigo;CodigoBarras;Descricao;Unidade;Custo;Preco;Preco2;Estoque;DepartamentoCod;Departamento;MarcaCod;Marca\n"

    def test_duplicate_skus_are_collapsed_last_wins(self, tmp_path, caplog):
        import logging

        f = tmp_path / "dups.csv"
        f.write_text(
            self.HEADER
            + "0000000001;42127836542536000;FORTMAX 12MG;UNID;1,00;30,00;0,00;1,000;0095;FARMACIA;000898;FORTMAX\n"
            + "0000000002;42127836542536000;FORTMAX 3MG;UNID;1,00;15,00;0,00;8,000;0095;FARMACIA;000898;FORTMAX\n"
            + "0000000003;42127836542536000;FORTMAX 6MG;UNID;1,00;25,00;0,00;5,000;0095;FARMACIA;000898;FORTMAX\n",
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            products = AthosParser().parse_file(f)

        # Three colliding rows collapse into one — last write wins.
        assert len(products) == 1
        assert products[0].name == "FORTMAX 6MG"

        # Operator must be warned both about the dupes AND the float-corrupt SKU.
        warnings = " ".join(r.message for r in caplog.records if r.levelno >= logging.WARNING)
        assert "duplicate" in warnings.lower()
        assert "exceed" in warnings.lower() or "corrupt" in warnings.lower()
