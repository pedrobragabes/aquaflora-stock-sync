import csv
from pathlib import Path

from src.catalog_reconcile import (
    ReconcileReport,
    ReconcileResult,
    normalize_sku,
    reconcile_diverse_catalog,
    write_split_woo_csvs,
    write_woo_csv,
)


WOO_HEADERS = [
    "ID", "Tipo", "SKU", "GTIN, UPC, EAN, or ISBN", "Nome", "Publicado",
    "Em estoque?", "Estoque", "Preço", "Categorias", "Imagens",
]
ATHOS_HEADERS = [
    "Codigo", "CodigoBarras", "Descricao", "Unidade", "Custo", "Preco",
    "Preco2", "Estoque", "DepartamentoCod", "Departamento", "MarcaCod", "Marca",
]


def _write_csv(path: Path, headers, rows, delimiter=","):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def test_reconcile_protects_current_catalog_and_updates_only_diverse(tmp_path):
    athos = tmp_path / "athos.csv"
    current = tmp_path / "current.csv"
    legacy = tmp_path / "legacy.csv"
    output = tmp_path / "output.csv"

    _write_csv(athos, ATHOS_HEADERS, [
        {"Codigo": "0001", "CodigoBarras": "7890000000001", "Descricao": "Adubo", "Preco": "19,90", "Estoque": "4,600", "Departamento": "GERAL"},
        {"Codigo": "0002", "CodigoBarras": "7890000000002", "Descricao": "Ração", "Preco": "30,00", "Estoque": "2,000", "Departamento": "PET"},
    ], delimiter=";")
    _write_csv(current, WOO_HEADERS, [
        {"ID": "20", "Tipo": "simple", "SKU": "7890000000002", "Nome": "Ração corrigida", "Publicado": "1", "Em estoque?": "1", "Estoque": "2", "Preço": "30,00", "Categorias": "Pets", "Imagens": "nova.jpg"},
    ])
    _write_csv(legacy, WOO_HEADERS, [
        {"ID": "10", "Tipo": "simple", "SKU": "7890000000001", "Nome": "Adubo curado", "Publicado": "1", "Em estoque?": "0", "Estoque": "0", "Preço": "10,00", "Categorias": "Agro & Campo", "Imagens": "adubo.jpg"},
        {"ID": "11", "Tipo": "simple", "SKU": "7890000000002", "Nome": "Ração antiga", "Publicado": "1", "Em estoque?": "1", "Estoque": "1", "Preço": "20,00", "Categorias": "Pets, Racao", "Imagens": "antiga.jpg"},
        {"ID": "12", "Tipo": "simple", "SKU": "999", "Nome": "Descontinuado", "Publicado": "1", "Em estoque?": "1", "Estoque": "1", "Preço": "5,00", "Categorias": "Geral", "Imagens": "velho.jpg"},
    ])

    result = reconcile_diverse_catalog(athos, current, legacy)
    write_woo_csv(result, output)

    assert result.report.exported_rows == 1
    assert result.report.protected_total == 1
    assert result.report.unmatched_rows == 1
    row = result.rows[0]
    assert row["ID"] == ""
    assert row["SKU"] == "7890000000001"
    assert row["Nome"] == "Adubo curado"
    assert row["Categorias"] == "Agro & Campo"
    assert row["Imagens"] == "adubo.jpg"
    assert row["Preço"] == "19,90"
    assert row["Estoque"] == "5"
    assert row["Em estoque?"] == "1"

    with output.open(encoding="utf-8-sig", newline="") as handle:
        saved = list(csv.DictReader(handle))
    assert saved == result.rows


def test_normalize_sku_never_rounds_long_numeric_identifiers():
    assert normalize_sku("42127836542535992") == "42127836542535992"
    assert normalize_sku("0000003603") == "3603"
    assert normalize_sku("3603.0") == "3603"


def test_split_csvs_keep_departments_isolated_and_include_all(tmp_path):
    cutelaria = {header: "" for header in WOO_HEADERS}
    cutelaria.update({"Tipo": "simple", "SKU": "100", "Nome": "Faca", "Categorias": "Lifestyle & Lazer"})
    geral = {header: "" for header in WOO_HEADERS}
    geral.update({"Tipo": "simple", "SKU": "200", "Nome": "Adubo", "Categorias": "Agro & Campo"})
    result = ReconcileResult(
        fieldnames=WOO_HEADERS,
        rows=[cutelaria, geral],
        report=ReconcileReport(exported_rows=2),
        rows_by_department={"CUTELARIA": [cutelaria], "GERAL": [geral]},
    )

    written = write_split_woo_csvs(result, tmp_path)

    assert set(written) == {"CUTELARIA", "GERAL", "TODOS"}
    assert written["CUTELARIA"].name == "01_cutelaria.csv"
    with written["CUTELARIA"].open(encoding="utf-8-sig", newline="") as handle:
        cutelaria_rows = list(csv.DictReader(handle))
    with written["TODOS"].open(encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))

    assert len(cutelaria_rows) == 1
    assert {row["SKU"] for row in cutelaria_rows} == {"100"}
    assert len(all_rows) == 2
    assert sum(len(rows) for rows in result.rows_by_department.values()) == len(all_rows)
