"""Regression tests for the privacy-safe current Athos export profile."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.profile_athos_export import profile_export
from src.parser import AthosParser


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "athos"
FIXTURE_PATH = FIXTURE_DIR / "athos-current-synthetic.csv"
EXPECTED_PATH = FIXTURE_DIR / "expected-profile.json"


def test_synthetic_fixture_matches_approved_aggregate_profile() -> None:
    expected = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    assert profile_export(FIXTURE_PATH) == expected


def test_synthetic_fixture_has_bom_and_contains_no_production_identity() -> None:
    raw_bytes = FIXTURE_PATH.read_bytes()
    decoded = raw_bytes.decode("utf-8-sig")

    assert raw_bytes.startswith(b"\xef\xbb\xbf")
    assert "PRODUTO SINTETICO" in decoded
    assert "DEPARTAMENTO SINTETICO" in decoded
    assert "MARCA SINTETICA" in decoded
    assert "AquaFlora Agroshop" not in decoded


def test_existing_parser_reads_the_synthetic_current_layout() -> None:
    products = AthosParser().parse_file(FIXTURE_PATH)

    assert len(products) == 15
    assert any(product.stock < 0 for product in products)
    assert any(not float(product.stock).is_integer() for product in products)
    assert any(product.ean is None for product in products)
    assert any(product.ean is not None for product in products)


def test_aggregate_profile_does_not_expose_product_level_values() -> None:
    rendered = json.dumps(profile_export(FIXTURE_PATH), ensure_ascii=False)

    assert "Descricao" in rendered  # column name is safe and documents the layout
    assert "PRODUTO SINTETICO" not in rendered
    assert "0000000001" not in rendered
    assert "12345670" not in rendered


def test_profiler_rejects_an_unexpected_layout(tmp_path: Path) -> None:
    unexpected = tmp_path / "unexpected.csv"
    unexpected.write_text("Codigo;Descricao\n0000000001;SINTETICO\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unexpected Athos columns"):
        profile_export(unexpected)


def test_short_row_is_counted_as_malformed_instead_of_crashing(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.csv"
    header = ";".join(
        [
            "Codigo",
            "CodigoBarras",
            "Descricao",
            "Unidade",
            "Custo",
            "Preco",
            "Preco2",
            "Estoque",
            "DepartamentoCod",
            "Departamento",
            "MarcaCod",
            "Marca",
        ]
    )
    malformed.write_text(header + "\n0000000001;12345670\n", encoding="utf-8")

    profile = profile_export(malformed)

    assert profile["layout"]["rowCount"] == 1
    assert profile["layout"]["malformedRows"] == 1
    assert profile["identifiers"]["codigoUniqueCount"] == 0
    assert profile["identifiers"]["codigoAllTenDigits"] is False
