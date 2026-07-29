#!/usr/bin/env python3
"""Build a safe WooCommerce import containing only current diverse products."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.catalog_reconcile import (
    reconcile_diverse_catalog,
    write_split_woo_csvs,
    write_woo_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extrai produtos diversos do export Woo antigo, protege pet/pesca do "
            "export atual e atualiza preço/estoque pelo Athos."
        )
    )
    parser.add_argument("--athos", type=Path, required=True)
    parser.add_argument("--current-pet-fishing", type=Path, required=True)
    parser.add_argument("--legacy-all", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--split-dir",
        type=Path,
        help="Gera um CSV por departamento Athos e outro com todos os produtos.",
    )
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = args.report or Path("data/reports") / f"diversos_reconcile_{timestamp}.json"

    result = reconcile_diverse_catalog(
        athos_path=args.athos,
        current_pet_fishing_path=args.current_pet_fishing,
        legacy_all_path=args.legacy_all,
    )
    if args.split_dir:
        written = write_split_woo_csvs(result, args.split_dir)
        output = written["TODOS"]
        for department, path in written.items():
            print(f"{department}: {path.resolve()}")
    else:
        output = args.output or Path("data/output") / f"woocommerce_diversos_atualizado_{timestamp}.csv"
        write_woo_csv(result, output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(result.report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8",
    )

    print(f"CSV consolidado: {output.resolve()}")
    print(f"Relatório: {report_path.resolve()}")
    print(
        f"Exportados: {result.report.exported_rows} | "
        f"Protegidos pet/pesca: {result.report.protected_total} | "
        f"Ausentes no Athos: {result.report.unmatched_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
