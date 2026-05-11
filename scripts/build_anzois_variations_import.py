#!/usr/bin/env python3
"""
Build WooCommerce import CSVs for hook groups/variations.

Input is the cleaned review CSV produced from:
  por_categoria_site/02_pesca/anzois/01_anzois_limpo.csv

The output reuses the header from an existing WooCommerce FULL export generated
by main.py, so WooCommerce maps the columns the same way as the validated full.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


NORMALIZED_COLUMNS = {
    "tipo": "tipo",
    "sku": "sku",
    "gtin": "gtin upc ean ou isbn",
    "nome": "nome",
    "publicado": "publicado",
    "destaque": "em destaque",
    "visibilidade": "visibilidade no catalogo",
    "desc_curta": "descricao curta",
    "descricao": "descricao",
    "imposto": "status do imposto",
    "em_estoque": "em estoque",
    "estoque": "estoque",
    "encomendas": "sao permitidas encomendas",
    "vendido_ind": "vendido individualmente",
    "avaliacoes": "permitir avaliacoes de clientes",
    "preco": "preco",
    "categorias": "categorias",
    "tags": "tags",
    "ascendente": "ascendente",
    "posicao": "posicao",
    "marcas": "marcas",
    "attr1_nome": "nome do atributo 1",
    "attr1_valores": "valores do atributo 1",
    "attr1_vis": "visibilidade do atributo 1",
    "attr1_global": "atributo global 1",
}


def normalize_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:60]


def parent_sku(parent: str) -> str:
    return f"P-{slug(parent)}".upper()


def price_br(value: object) -> str:
    try:
        return f"{float(str(value).replace(',', '.')):.2f}".replace(".", ",")
    except Exception:
        return str(value or "")


def stock_int(value: object) -> int:
    try:
        return int(float(str(value).replace(",", ".")))
    except Exception:
        return 0


def title_from_parent(parent: str) -> str:
    return parent.title().replace("Jws", "JWS")


def variant_value(item: dict[str, str]) -> str:
    value = (item.get("variacao") or "").strip()
    detail = (item.get("detalhe") or "").strip()
    if detail and value:
        return f"{value} {detail}"
    return value or detail or "Unico"


def find_latest_full_template(output_dir: Path) -> Path:
    candidates = sorted(output_dir.glob("woocommerce_import_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No woocommerce_import_*.csv template found in {output_dir}"
        )
    return candidates[-1]


def load_template_columns(template: Path) -> list[str]:
    with template.open("r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def build_index(columns: list[str]) -> dict[str, int]:
    normalized = {normalize_key(column): index for index, column in enumerate(columns)}
    missing = [name for name in NORMALIZED_COLUMNS.values() if name not in normalized]
    if missing:
        raise ValueError(f"Template is missing expected columns: {missing}")
    return {
        alias: normalized[normalized_name]
        for alias, normalized_name in NORMALIZED_COLUMNS.items()
    }


def set_value(row: list[object], index: dict[str, int], alias: str, value: object) -> None:
    row[index[alias]] = value


def blank_row(columns: list[str]) -> list[object]:
    return ["" for _ in columns]


def build_rows(
    source: Path,
    columns: list[str],
    index: dict[str, int],
) -> tuple[list[list[object]], list[list[object]]]:
    with source.open("r", encoding="utf-8-sig", newline="") as f:
        items = list(csv.DictReader(f, delimiter=";"))

    by_parent: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        by_parent[item["grupo_pai"]].append(item)

    parents: list[list[object]] = []
    children: list[list[object]] = []

    for position, (parent, group_items) in enumerate(sorted(by_parent.items()), start=1):
        psku = parent_sku(parent)
        parent_name = title_from_parent(parent)
        values: list[str] = []
        for item in group_items:
            value = variant_value(item)
            if value not in values:
                values.append(value)

        total_stock = sum(stock_int(item.get("estoque")) for item in group_items)
        prices = []
        for item in group_items:
            try:
                prices.append(float(str(item.get("preco") or "0").replace(",", ".")))
            except Exception:
                pass
        min_price = min(prices) if prices else 0

        parent_row = blank_row(columns)
        for alias, value in [
            ("tipo", "variable"),
            ("sku", psku),
            ("nome", parent_name),
            ("publicado", 1),
            ("destaque", 0),
            ("visibilidade", "visible"),
            ("desc_curta", f"{parent_name} com variacoes por numero."),
            ("descricao", f"<p>{parent_name} com variacoes por numero. Produto da categoria Pesca.</p>"),
            ("imposto", "taxable"),
            ("em_estoque", 1 if total_stock > 0 else 0),
            ("encomendas", 0),
            ("vendido_ind", 0),
            ("avaliacoes", 1),
            ("preco", price_br(min_price) if min_price else ""),
            ("categorias", "Pesca > Anzois"),
            ("tags", "Pesca, Anzol"),
            ("posicao", position),
            ("marcas", group_items[0].get("marca", "")),
            ("attr1_nome", "Numero"),
            ("attr1_valores", ", ".join(values)),
            ("attr1_vis", 1),
            ("attr1_global", 0),
        ]:
            set_value(parent_row, index, alias, value)
        parents.append(parent_row)

        for child_position, item in enumerate(group_items, start=1):
            value = variant_value(item)
            stock = stock_int(item.get("estoque"))
            child = blank_row(columns)
            for alias, field_value in [
                ("tipo", "variation"),
                ("sku", item.get("sku", "")),
                ("gtin", item.get("ean", "")),
                ("nome", item.get("nome_limpo", "")),
                ("publicado", 1),
                ("destaque", 0),
                ("visibilidade", "visible"),
                ("desc_curta", f"{item.get('nome_limpo', '')} | Variacao: {value}"),
                ("descricao", f"<p>{item.get('nome_limpo', '')} da categoria Pesca.</p>"),
                ("imposto", "taxable"),
                ("em_estoque", 1 if stock > 0 else 0),
                ("estoque", stock),
                ("encomendas", 0),
                ("vendido_ind", 0),
                ("avaliacoes", 1),
                ("preco", price_br(item.get("preco"))),
                ("categorias", "Pesca > Anzois"),
                ("tags", "Pesca, Anzol"),
                ("ascendente", psku),
                ("posicao", child_position),
                ("marcas", item.get("marca", "")),
                ("attr1_nome", "Numero"),
                ("attr1_valores", value),
                ("attr1_vis", 1),
                ("attr1_global", 0),
            ]:
                set_value(child, index, alias, field_value)
            children.append(child)

    return parents, children


def write_csv(path: Path, columns: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build WooCommerce hook variation CSVs")
    parser.add_argument("--source", type=Path, required=True, help="Clean hook CSV")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output folder")
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="WooCommerce FULL CSV template. Defaults to latest data/output/woocommerce_import_*.csv",
    )
    parser.add_argument(
        "--full-output-dir",
        type=Path,
        default=Path("data/output"),
        help="Folder used to find the latest FULL CSV template",
    )
    args = parser.parse_args()

    template = args.template or find_latest_full_template(args.full_output_dir)
    columns = load_template_columns(template)
    index = build_index(columns)
    parents, children = build_rows(args.source, columns, index)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "01_anzois_pais_woocommerce_full.csv", columns, parents)
    write_csv(args.output_dir / "02_anzois_variacoes_woocommerce_full.csv", columns, children)
    write_csv(
        args.output_dir / "00_anzois_pais_e_variacoes_woocommerce_full.csv",
        columns,
        parents + children,
    )

    readme = f"""# Importacao WooCommerce - Anzois variaveis

Estes CSVs usam o mesmo cabecalho do export FULL do WooCommerce e delimitador virgula.

Ordem recomendada:

1. Importe `01_anzois_pais_woocommerce_full.csv` para criar os produtos pais (`Tipo=variable`).
2. Depois importe `02_anzois_variacoes_woocommerce_full.csv` para criar os filhos (`Tipo=variation`).
3. Se quiser testar tudo junto, use `00_anzois_pais_e_variacoes_woocommerce_full.csv`.

Observacoes:

- `Ascendente` nas variacoes recebe o SKU do pai.
- O atributo usado para variar e `Numero`.
- A categoria enviada e `Pesca > Anzois`.
- Total de pais: {len(parents)}.
- Total de variacoes: {len(children)}.
"""
    (args.output_dir / "README_IMPORTAR_ANZOIS.md").write_text(readme, encoding="utf-8")

    print(f"Template: {template}")
    print(f"Pais: {len(parents)}")
    print(f"Variacoes: {len(children)}")
    print(f"Output: {args.output_dir}")


if __name__ == "__main__":
    main()
