"""Reconcile a legacy WooCommerce catalog with a current Athos export.

The legacy export supplies curated catalog content. The current pet/fishing
export is a protection boundary: those products must never be reintroduced
from the legacy file. Athos is the source of truth for current SKU, price,
and stock.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable, Mapping, Sequence


DEFAULT_PROTECTED_ROOTS = ("Pet", "Pets", "Pesca", "Racao", "Ração")
ATHOS_REQUIRED_COLUMNS = {
    "Codigo", "CodigoBarras", "Descricao", "Preco", "Estoque", "Departamento",
}
WOO_REQUIRED_COLUMNS = {
    "ID", "Tipo", "SKU", "Nome", "Publicado", "Em estoque?", "Estoque", "Categorias",
}


class CatalogReconcileError(ValueError):
    """Raised when an input file is unsafe or structurally incompatible."""


@dataclass
class ReconcileReport:
    athos_rows: int = 0
    current_rows: int = 0
    legacy_rows: int = 0
    protected_by_category: int = 0
    protected_by_current_sku: int = 0
    protected_total: int = 0
    diverse_candidates: int = 0
    exported_rows: int = 0
    unmatched_rows: int = 0
    ambiguous_rows: int = 0
    duplicate_output_skus: int = 0
    departments: dict[str, int] = field(default_factory=dict)
    category_roots: dict[str, int] = field(default_factory=dict)
    unmatched: list[dict[str, str]] = field(default_factory=list)
    ambiguous: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReconcileResult:
    fieldnames: list[str]
    rows: list[dict[str, str]]
    report: ReconcileReport
    rows_by_department: dict[str, list[dict[str, str]]] = field(default_factory=dict)


def normalize_sku(value: object) -> str:
    """Normalize identifiers without ever converting long values to float."""
    text = str(value or "").strip()
    numeric = re.fullmatch(r"(\d+)(?:\.0+)?", text)
    if numeric:
        return numeric.group(1).lstrip("0") or "0"
    return text.upper()


def normalize_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold().strip()


def category_roots(value: str) -> set[str]:
    return {
        category.strip().split(" > ", 1)[0]
        for category in (value or "").split(",")
        if category.strip()
    }


def read_csv_rows(path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            if not reader.fieldnames:
                raise CatalogReconcileError(f"CSV sem cabeçalho: {path}")
            rows = [dict(row) for row in reader]
            return list(reader.fieldnames), rows
    except UnicodeDecodeError as exc:
        raise CatalogReconcileError(f"CSV não está em UTF-8: {path}") from exc


def _require_columns(path: Path, fieldnames: Iterable[str], required: set[str]) -> None:
    missing = sorted(required - set(fieldnames))
    if missing:
        raise CatalogReconcileError(
            f"Colunas obrigatórias ausentes em {path.name}: {', '.join(missing)}"
        )


def _index_rows(rows: Sequence[Mapping[str, str]], column: str) -> dict[str, list[Mapping[str, str]]]:
    index: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        key = normalize_sku(row.get(column, ""))
        if key:
            index[key].append(row)
    return index


def _parse_decimal_br(value: str, *, field_name: str, sku: str) -> Decimal:
    text = (value or "").strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(text or "0")
    except InvalidOperation as exc:
        raise CatalogReconcileError(
            f"{field_name} inválido no Athos para SKU {sku}: {value!r}"
        ) from exc


def _format_price_br(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f").replace(".", ",")


def _stock_as_woo(value: Decimal) -> int:
    rounded = int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(0, rounded)


def _gtin_column(fieldnames: Sequence[str]) -> str | None:
    return next((name for name in fieldnames if name.startswith("GTIN, UPC, EAN,")), None)


def _valid_gtin(value: str) -> str:
    text = (value or "").strip()
    return text if text.isdigit() and len(text) in {8, 12, 13, 14} else ""


def reconcile_diverse_catalog(
    athos_path: Path,
    current_pet_fishing_path: Path,
    legacy_all_path: Path,
    protected_roots: Sequence[str] = DEFAULT_PROTECTED_ROOTS,
) -> ReconcileResult:
    """Return current non-pet/non-fishing legacy products in Woo import shape."""
    athos_fields, athos_rows = read_csv_rows(athos_path, ";")
    current_fields, current_rows = read_csv_rows(current_pet_fishing_path, ",")
    legacy_fields, legacy_rows = read_csv_rows(legacy_all_path, ",")

    _require_columns(Path(athos_path), athos_fields, ATHOS_REQUIRED_COLUMNS)
    _require_columns(Path(current_pet_fishing_path), current_fields, WOO_REQUIRED_COLUMNS)
    _require_columns(Path(legacy_all_path), legacy_fields, WOO_REQUIRED_COLUMNS)

    protected_normalized = {normalize_label(root) for root in protected_roots}
    current_skus = {
        normalize_sku(row.get("SKU", ""))
        for row in current_rows
        if normalize_sku(row.get("SKU", ""))
    }
    barcode_index = _index_rows(athos_rows, "CodigoBarras")
    code_index = _index_rows(athos_rows, "Codigo")
    gtin_column = _gtin_column(legacy_fields)

    report = ReconcileReport(
        athos_rows=len(athos_rows), current_rows=len(current_rows), legacy_rows=len(legacy_rows),
    )
    output_rows: list[dict[str, str]] = []
    rows_by_department: dict[str, list[dict[str, str]]] = defaultdict(list)
    department_counts: Counter[str] = Counter()
    root_counts: Counter[str] = Counter()

    for legacy in legacy_rows:
        sku = normalize_sku(legacy.get("SKU", ""))
        roots = category_roots(legacy.get("Categorias", ""))
        protected_category = any(normalize_label(root) in protected_normalized for root in roots)
        protected_current = bool(sku and sku in current_skus)

        if protected_category:
            report.protected_by_category += 1
        if protected_current:
            report.protected_by_current_sku += 1
        if protected_category or protected_current:
            report.protected_total += 1
            continue

        report.diverse_candidates += 1
        barcode_matches = barcode_index.get(sku, [])
        code_matches = code_index.get(sku, [])
        if len(barcode_matches) == 1:
            matches = barcode_matches
        elif len(code_matches) == 1:
            matches = code_matches
        else:
            matches = barcode_matches or code_matches

        if len(matches) == 0:
            report.unmatched_rows += 1
            report.unmatched.append({
                "SKU": legacy.get("SKU", ""),
                "Nome": legacy.get("Nome", ""),
                "Categorias": legacy.get("Categorias", ""),
            })
            continue
        if len(matches) != 1:
            report.ambiguous_rows += 1
            report.ambiguous.append({
                "SKU": legacy.get("SKU", ""),
                "Nome": legacy.get("Nome", ""),
                "Quantidade de correspondências": str(len(matches)),
            })
            continue

        athos = matches[0]
        price = _parse_decimal_br(athos.get("Preco", ""), field_name="Preço", sku=sku)
        stock_decimal = _parse_decimal_br(athos.get("Estoque", ""), field_name="Estoque", sku=sku)
        if price <= 0:
            raise CatalogReconcileError(f"Preço não positivo no Athos para SKU {sku}: {price}")
        stock = _stock_as_woo(stock_decimal)

        updated = dict(legacy)
        updated["ID"] = ""  # Use the safer WooCommerce update-by-SKU path.
        updated["Preço"] = _format_price_br(price)
        updated["Estoque"] = str(stock)
        updated["Em estoque?"] = "1" if stock > 0 else "0"
        if gtin_column:
            updated[gtin_column] = _valid_gtin(athos.get("CodigoBarras", ""))

        output_rows.append(updated)
        department = (athos.get("Departamento") or "SEM DEPARTAMENTO").strip()
        department_counts[department] += 1
        rows_by_department[department].append(updated)
        root_counts.update(roots)

    output_skus = Counter(normalize_sku(row.get("SKU", "")) for row in output_rows)
    report.duplicate_output_skus = sum(1 for count in output_skus.values() if count > 1)
    if report.duplicate_output_skus:
        raise CatalogReconcileError(
            f"Saída teria {report.duplicate_output_skus} SKU(s) duplicado(s)"
        )

    report.exported_rows = len(output_rows)
    report.departments = dict(sorted(department_counts.items()))
    report.category_roots = dict(sorted(root_counts.items()))
    return ReconcileResult(
        fieldnames=legacy_fields,
        rows=output_rows,
        report=report,
        rows_by_department={
            department: rows_by_department[department]
            for department in sorted(rows_by_department)
        },
    )


def write_woo_csv(result: ReconcileResult, output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=result.fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result.rows)
    return output_path


SPLIT_DEPARTMENT_ORDER = (
    ("CUTELARIA", "01_cutelaria.csv"),
    ("PISCINA", "02_piscina.csv"),
    ("TABACARIA", "03_tabacaria.csv"),
    ("AQUARISMO", "04_aquarismo.csv"),
    ("FARMACIA", "05_farmacia.csv"),
    ("GERAL", "06_geral.csv"),
)


def write_split_woo_csvs(result: ReconcileResult, output_dir: Path) -> dict[str, Path]:
    """Write one import CSV per exact Athos department plus a full review CSV."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for department, filename in SPLIT_DEPARTMENT_ORDER:
        rows = result.rows_by_department.get(department, [])
        if not rows:
            continue
        department_result = ReconcileResult(
            fieldnames=result.fieldnames,
            rows=rows,
            report=result.report,
            rows_by_department={department: rows},
        )
        written[department] = write_woo_csv(department_result, output_dir / filename)

    known_departments = {department for department, _ in SPLIT_DEPARTMENT_ORDER}
    unexpected = sorted(set(result.rows_by_department) - known_departments)
    if unexpected:
        raise CatalogReconcileError(
            "Departamentos sem arquivo definido: " + ", ".join(unexpected)
        )

    written["TODOS"] = write_woo_csv(
        result, output_dir / "99_todos_produtos_diversos.csv"
    )
    return written
