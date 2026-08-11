"""Produce a privacy-safe aggregate profile for a clean Athos CSV export.

The profiler never emits product descriptions, identifiers, prices, stock values,
or the input path. Its JSON output is safe to attach to an issue after review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


EXPECTED_COLUMNS = [
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
GTIN_LENGTHS = {8, 12, 13, 14}


def _parse_athos_decimal(value: str) -> Decimal:
    normalized = value.strip()
    if "," in normalized:
        normalized = normalized.replace(".", "").replace(",", ".")
    parsed = Decimal(normalized)
    if not parsed.is_finite():
        raise InvalidOperation
    return parsed


def _has_valid_gtin_check_digit(value: str) -> bool:
    if not value.isdigit() or len(value) not in GTIN_LENGTHS:
        return False

    digits = [int(character) for character in value]
    expected = digits[-1]
    payload = digits[:-1]
    weighted_sum = sum(
        digit * (3 if (len(payload) - index) % 2 == 1 else 1)
        for index, digit in enumerate(payload)
    )
    calculated = (10 - weighted_sum % 10) % 10
    return calculated == expected


def _duplicate_row_count(values: Counter[str]) -> int:
    return sum(count - 1 for count in values.values() if count > 1)


def profile_export(input_path: Path) -> dict[str, Any]:
    raw_bytes = input_path.read_bytes()
    has_bom = raw_bytes.startswith(b"\xef\xbb\xbf")

    codigo_counts: Counter[str] = Counter()
    barcode_counts: Counter[str] = Counter()
    unit_counts: Counter[str] = Counter()
    fractional_by_unit: Counter[str] = Counter()
    departments: set[str] = set()
    brands: set[str] = set()

    row_count = 0
    malformed_rows = 0
    empty_fields = 0
    barcode_absent = 0
    gtin_candidates = 0
    valid_gtin = 0
    invalid_gtin = 0
    stock_positive = 0
    stock_zero = 0
    stock_negative = 0
    stock_fractional = 0
    invalid_stock = 0
    price_positive = 0
    price_zero = 0
    price_negative = 0
    invalid_price = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if reader.fieldnames != EXPECTED_COLUMNS:
            raise ValueError(
                "Unexpected Athos columns. "
                f"Expected {EXPECTED_COLUMNS!r}, received {reader.fieldnames!r}."
            )

        for row in reader:
            row_count += 1
            if (
                None in row
                or set(row) != set(EXPECTED_COLUMNS)
                or any(row[column] is None for column in EXPECTED_COLUMNS)
            ):
                malformed_rows += 1
                continue

            empty_fields += sum(not (row[column] or "").strip() for column in EXPECTED_COLUMNS)

            codigo = row["Codigo"].strip()
            barcode = row["CodigoBarras"].strip()
            unit = row["Unidade"].strip()
            codigo_counts[codigo] += 1
            unit_counts[unit] += 1
            departments.add(row["Departamento"].strip())
            brands.add(row["Marca"].strip())

            if barcode:
                barcode_counts[barcode] += 1
                if barcode.isdigit() and len(barcode) in GTIN_LENGTHS:
                    gtin_candidates += 1
                    if _has_valid_gtin_check_digit(barcode):
                        valid_gtin += 1
                    else:
                        invalid_gtin += 1
            else:
                barcode_absent += 1

            try:
                stock = _parse_athos_decimal(row["Estoque"])
                if stock > 0:
                    stock_positive += 1
                elif stock < 0:
                    stock_negative += 1
                else:
                    stock_zero += 1
                if stock != stock.to_integral_value():
                    stock_fractional += 1
                    fractional_by_unit[unit] += 1
            except InvalidOperation:
                invalid_stock += 1

            try:
                price = _parse_athos_decimal(row["Preco"])
                if price > 0:
                    price_positive += 1
                elif price < 0:
                    price_negative += 1
                else:
                    price_zero += 1
            except InvalidOperation:
                invalid_price += 1

    return {
        "source": {
            "fileName": input_path.name,
            "byteSize": len(raw_bytes),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        },
        "layout": {
            "encoding": "utf-8-sig" if has_bom else "utf-8",
            "hasUtf8Bom": has_bom,
            "delimiter": ";",
            "columns": EXPECTED_COLUMNS,
            "columnCount": len(EXPECTED_COLUMNS),
            "rowCount": row_count,
            "malformedRows": malformed_rows,
            "emptyFields": empty_fields,
        },
        "identifiers": {
            "codigoUniqueCount": len(codigo_counts),
            "codigoDuplicateRows": _duplicate_row_count(codigo_counts),
            "codigoAllTenDigits": bool(codigo_counts)
            and all(len(value) == 10 and value.isdigit() for value in codigo_counts),
            "codigoAllStartWithZero": bool(codigo_counts)
            and all(value.startswith("0") for value in codigo_counts),
            "codigoBarrasUniqueCount": len(barcode_counts),
            "codigoBarrasDuplicateRows": _duplicate_row_count(barcode_counts),
            "codigoBarrasAbsent": barcode_absent,
            "gtinLengthCandidates": gtin_candidates,
            "validGtin": valid_gtin,
            "invalidGtin": invalid_gtin,
        },
        "inventory": {
            "positive": stock_positive,
            "zero": stock_zero,
            "negative": stock_negative,
            "fractional": stock_fractional,
            "invalid": invalid_stock,
            "fractionalByUnit": dict(sorted(fractional_by_unit.items())),
        },
        "price": {
            "positive": price_positive,
            "zero": price_zero,
            "negative": price_negative,
            "invalid": invalid_price,
        },
        "catalog": {
            "unitCounts": dict(sorted(unit_counts.items())),
            "uniqueDepartmentCount": len(departments),
            "uniqueBrandCount": len(brands),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a privacy-safe aggregate profile of an Athos CSV export."
    )
    parser.add_argument("input", type=Path, help="Athos CSV file to profile")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    profile = profile_export(args.input)
    rendered = json.dumps(profile, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
