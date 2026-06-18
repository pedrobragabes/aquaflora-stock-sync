"""Build a WooCommerce import CSV from the pharmacy products photographed on 2026-06-17."""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATHOS = ROOT / "data" / "input" / "Athos.csv"
TEMPLATE = (
    ROOT
    / "data"
    / "output"
    / "dry_run_refine_20260511_121244"
    / "por_categoria_site"
    / "01_pets"
    / "farmacia_pet"
    / "02_farmacia_pet_woocommerce_import.csv"
)
OUTPUT_DIR = ROOT / "data" / "output" / "produtos_fotos_farmacia_20260617"


FARMACIA_ANTIPULGAS = "Pets > Farmácia Veterinária > Antipulgas & Vermífugos"
FARMACIA_TRATAMENTOS = "Pets > Farmácia Veterinária > Medicamentos & Tratamentos"


@dataclass(frozen=True)
class PhotoProduct:
    ean: str
    photo_name: str
    import_name: str
    brand: str
    category: str
    tags: str
    group: str | None
    variation: str
    photo_file: str
    note: str = ""


PRODUCTS = [
    PhotoProduct(
        "5420036978923",
        "Credeli Gatos 0,9 a 2,0 kg 12 mg",
        "Credeli Gatos 0,9 a 2,0 kg 12 mg - Elanco",
        "Elanco",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, gatos, Elanco",
        "Credeli Gatos",
        "0,9 a 2,0 kg / 12 mg",
        "WhatsApp Image 2026-06-17 at 12.00.53.jpeg",
    ),
    PhotoProduct(
        "5420036978916",
        "Credeli Gatos 2,1 a 8,0 kg 48 mg",
        "Credeli Gatos 2,1 a 8,0 kg 48 mg - Elanco",
        "Elanco",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, gatos, Elanco",
        "Credeli Gatos",
        "2,1 a 8,0 kg / 48 mg",
        "WhatsApp Image 2026-06-17 at 12.00.53.jpeg",
    ),
    PhotoProduct(
        "7891126002329",
        "Coleira Vaponex para cães 64 cm 20 g",
        "Coleira Vaponex Antipulgas e Carrapatos para Cães 64 cm - Coveli",
        "Coveli",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, coleira antipulgas, cães, Coveli",
        None,
        "",
        "WhatsApp Image 2026-06-17 at 12.00.59.jpeg",
    ),
    PhotoProduct(
        "7791432014132",
        "Coleira TEA Gatos 13 g 33 cm",
        "Coleira TEA Antipulgas e Carrapatos para Gatos 33 cm - König",
        "König",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, coleira antipulgas, gatos, König",
        None,
        "",
        "WhatsApp Image 2026-06-17 at 12.01.12.jpeg",
    ),
    PhotoProduct(
        "7897515655664",
        "Effipro Spray 100 ml",
        "Effipro Spray Antiparasitário 100 ml - Virbac",
        "Virbac",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, spray, Virbac",
        None,
        "",
        "WhatsApp Image 2026-06-17 at 12.01.34.jpeg",
        "Incluido por estar nas fotos; o filtro antigo removia sprays.",
    ),
    PhotoProduct(
        "7898019862565",
        "WellPet Cães 2 a 4,5 kg 45 mg",
        "WellPet Cães 2 a 4,5 kg 45 mg - Ourofino",
        "Ourofino",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Ourofino",
        "WellPet Cães",
        "2 a 4,5 kg / 45 mg",
        "WhatsApp Image 2026-06-17 at 12.02.28.jpeg",
    ),
    PhotoProduct(
        "7898019862572",
        "WellPet Cães 4,6 a 10 kg 100 mg",
        "WellPet Cães 4,6 a 10 kg 100 mg - Ourofino",
        "Ourofino",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Ourofino",
        "WellPet Cães",
        "4,6 a 10 kg / 100 mg",
        "WhatsApp Image 2026-06-17 at 12.02.28.jpeg",
    ),
    PhotoProduct(
        "7898019862589",
        "WellPet Cães 10,1 a 20 kg 200 mg",
        "WellPet Cães 10,1 a 20 kg 200 mg - Ourofino",
        "Ourofino",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Ourofino",
        "WellPet Cães",
        "10,1 a 20 kg / 200 mg",
        "WhatsApp Image 2026-06-17 at 12.02.28.jpeg",
    ),
    PhotoProduct(
        "7898019862596",
        "WellPet Cães 20,1 a 40 kg 400 mg",
        "WellPet Cães 20,1 a 40 kg 400 mg - Ourofino",
        "Ourofino",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Ourofino",
        "WellPet Cães",
        "20,1 a 40 kg / 400 mg",
        "WhatsApp Image 2026-06-17 at 12.02.28.jpeg",
    ),
    PhotoProduct(
        "7898019862602",
        "WellPet Cães 40,1 a 56 kg 560 mg",
        "WellPet Cães 40,1 a 56 kg 560 mg - Ourofino",
        "Ourofino",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Ourofino",
        "WellPet Cães",
        "40,1 a 56 kg / 560 mg",
        "WhatsApp Image 2026-06-17 at 12.02.28.jpeg",
    ),
    PhotoProduct(
        "7898053772905",
        "Frontline Plus Gatos 0,5 ml",
        "Frontline Plus Gatos 0,5 ml - Merial",
        "Merial",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, gatos, Merial",
        None,
        "",
        "WhatsApp Image 2026-06-17 at 12.03.08.jpeg",
    ),
    PhotoProduct(
        "7898053772868",
        "Frontline Plus Cães até 10 kg",
        "Frontline Plus Cães até 10 kg - Merial",
        "Merial",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Merial",
        "Frontline Plus Cães",
        "Até 10 kg / 0,67 ml",
        "WhatsApp Image 2026-06-17 at 12.03.26.jpeg",
    ),
    PhotoProduct(
        "7898053772875",
        "Frontline Plus Cães 10 a 20 kg",
        "Frontline Plus Cães 10 a 20 kg - Merial",
        "Merial",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Merial",
        "Frontline Plus Cães",
        "10 a 20 kg / 1,34 ml",
        "WhatsApp Image 2026-06-17 at 12.03.41.jpeg",
    ),
    PhotoProduct(
        "7898053772882",
        "Frontline Plus Cães 20 a 40 kg",
        "Frontline Plus Cães 20 a 40 kg - Merial",
        "Merial",
        FARMACIA_ANTIPULGAS,
        "Farmácia Veterinária, antipulgas e carrapatos, cães, Merial",
        "Frontline Plus Cães",
        "20 a 40 kg / 2,68 ml",
        "WhatsApp Image 2026-06-17 at 12.03.46.jpeg",
    ),
    PhotoProduct(
        "7896006263609",
        "Oraldia Spray 120 ml Tutti Frutti",
        "Oraldia Spray Bucal 120 ml Tutti Frutti - Agener União",
        "Agener União",
        FARMACIA_TRATAMENTOS,
        "Farmácia Veterinária, saúde oral, cães e gatos, Agener União",
        None,
        "",
        "WhatsApp Image 2026-06-17 at 12.07.17.jpeg",
        "Foto mostra Oraldia; Athos encontrou o mesmo SKU como ORALCLIN SPRAY 120ML.",
    ),
    PhotoProduct(
        "7896006263593",
        "Oraldia Gel 25 g Tutti Frutti",
        "Oraldia Gel Bucal 25 g Tutti Frutti - Agener União",
        "Agener União",
        FARMACIA_TRATAMENTOS,
        "Farmácia Veterinária, saúde oral, cães e gatos, Agener União",
        None,
        "",
        "WhatsApp Image 2026-06-17 at 12.07.38.jpeg",
        "Foto mostra Oraldia; Athos encontrou o mesmo SKU como ORALCLIN GEL 25G.",
    ),
]


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return text.encode("ascii", "ignore").decode("ascii").upper()


def decimal_br(value: str) -> Decimal:
    return Decimal((value or "0").replace(".", "").replace(",", "."))


def stock_int(value: str) -> int:
    return max(0, int(decimal_br(value)))


def price_br(value: Decimal | str) -> str:
    if value == "":
        return ""
    return f"{Decimal(value):.2f}".replace(".", ",")


def slug(value: str) -> str:
    normalized = normalize(value)
    return re.sub(r"[^A-Z0-9]+", "-", normalized).strip("-")


def read_header() -> list[str]:
    with TEMPLATE.open("r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def load_athos() -> dict[str, dict[str, str]]:
    with ATHOS.open("r", encoding="utf-8-sig", newline="") as f:
        return {row["CodigoBarras"].strip(): row for row in csv.DictReader(f, delimiter=";")}


def row_base(columns: list[str]) -> dict[str, str]:
    return {column: "" for column in columns}


def description(name: str, brand: str, category_text: str) -> str:
    return (
        f'<div class="product-description"><h2>{name}</h2>'
        f"<p>Produto da marca {brand} selecionado para a vitrine {category_text} da AquaFlora Agroshop.</p>"
        "<p>Produto de uso veterinario. Confira a apresentacao correta e siga a orientacao de um medico-veterinario.</p>"
        "</div>"
    )


def simple_or_variation_row(
    columns: list[str],
    product: PhotoProduct,
    athos_row: dict[str, str],
    kind: str,
    parent_sku: str = "",
    position: int = 0,
) -> dict[str, str]:
    row = row_base(columns)
    stock = stock_int(athos_row["Estoque"])
    in_stock = "1" if stock > 0 else "0"
    attr_name = "Opcao" if kind == "variation" else "Marca"
    attr_value = product.variation if kind == "variation" else product.brand
    row.update(
        {
            "Tipo": kind,
            "SKU": product.ean,
            "GTIN, UPC, EAN, ou ISBN": product.ean,
            "Nome": product.import_name,
            "Publicado": "1",
            "Em destaque?": "0",
            "Visibilidade no catalogo": "visible",
            "Visibilidade no catálogo": "visible",
            "Descricao curta": f"{product.import_name} | AquaFlora Agroshop",
            "Descrição curta": f"{product.import_name} | AquaFlora Agroshop",
            "Descricao": description(product.import_name, product.brand, product.category),
            "Descrição": description(product.import_name, product.brand, product.category),
            "Status do imposto": "taxable",
            "Em estoque?": in_stock,
            "Estoque": str(stock),
            "Sao permitidas encomendas?": "0",
            "São permitidas encomendas?": "0",
            "Vendido individualmente?": "0",
            "Permitir avaliacoes de clientes?": "1",
            "Permitir avaliações de clientes?": "1",
            "Preco": price_br(decimal_br(athos_row["Preco"])),
            "Preço": price_br(decimal_br(athos_row["Preco"])),
            "Categorias": product.category,
            "Tags": product.tags,
            "Ascendente": parent_sku,
            "Posicao": str(position),
            "Posição": str(position),
            "Marcas": product.brand,
            "Nome do atributo 1": attr_name,
            "Valores do atributo 1": attr_value,
            "Visibilidade do atributo 1": "1",
            "Atributo global 1": "0" if kind == "variation" else "1",
        }
    )
    return {column: row.get(column, "") for column in columns}


def parent_row(columns: list[str], group_name: str, items: list[PhotoProduct], athos: dict[str, dict[str, str]]) -> dict[str, str]:
    row = row_base(columns)
    parent_sku = f"P-FARMACIA-PET-{slug(group_name)}"
    total_stock = sum(stock_int(athos[item.ean]["Estoque"]) for item in items)
    min_price = min(decimal_br(athos[item.ean]["Preco"]) for item in items)
    first = items[0]
    row.update(
        {
            "Tipo": "variable",
            "SKU": parent_sku,
            "Nome": group_name,
            "Publicado": "1",
            "Em destaque?": "0",
            "Visibilidade no catalogo": "visible",
            "Visibilidade no catálogo": "visible",
            "Descricao curta": f"{group_name} com opcoes de apresentacao | AquaFlora Agroshop",
            "Descrição curta": f"{group_name} com opcoes de apresentacao | AquaFlora Agroshop",
            "Descricao": description(group_name, first.brand, first.category),
            "Descrição": description(group_name, first.brand, first.category),
            "Status do imposto": "taxable",
            "Em estoque?": "1" if total_stock > 0 else "0",
            "Estoque": str(total_stock),
            "Sao permitidas encomendas?": "0",
            "São permitidas encomendas?": "0",
            "Vendido individualmente?": "0",
            "Permitir avaliacoes de clientes?": "1",
            "Permitir avaliações de clientes?": "1",
            "Preco": price_br(min_price),
            "Preço": price_br(min_price),
            "Categorias": first.category,
            "Tags": first.tags,
            "Posicao": "0",
            "Posição": "0",
            "Marcas": first.brand,
            "Nome do atributo 1": "Opcao",
            "Valores do atributo 1": ", ".join(item.variation for item in items),
            "Visibilidade do atributo 1": "1",
            "Atributo global 1": "0",
        }
    )
    return {column: row.get(column, "") for column in columns}


def build_rows(columns: list[str], athos: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[PhotoProduct]] = {}
    simple_items: list[PhotoProduct] = []

    for product in PRODUCTS:
        if product.ean not in athos:
            raise SystemExit(f"EAN not found in Athos.csv: {product.ean} - {product.photo_name}")
        if product.group:
            grouped.setdefault(product.group, []).append(product)
        else:
            simple_items.append(product)

    rows: list[dict[str, str]] = []
    for group_name in ["Credeli Gatos", "WellPet Cães", "Frontline Plus Cães"]:
        items = grouped[group_name]
        parent = parent_row(columns, group_name, items, athos)
        rows.append(parent)
        for position, item in enumerate(items, start=1):
            rows.append(simple_or_variation_row(columns, item, athos[item.ean], "variation", parent["SKU"], position))

    for item in simple_items:
        rows.append(simple_or_variation_row(columns, item, athos[item.ean], "simple"))

    return rows


def validate(rows: list[dict[str, str]]) -> None:
    skus = [row["SKU"] for row in rows if row["SKU"]]
    duplicates = sorted({sku for sku in skus if skus.count(sku) > 1})
    if duplicates:
        raise SystemExit(f"Duplicate SKUs in import: {duplicates}")

    parents = {row["SKU"] for row in rows if row["Tipo"] == "variable"}
    orphan_variations = [
        row["SKU"]
        for row in rows
        if row["Tipo"] == "variation" and row["Ascendente"] not in parents
    ]
    if orphan_variations:
        raise SystemExit(f"Variation rows without parent: {orphan_variations}")

    missing = [
        row["SKU"]
        for row in rows
        if not row["Nome"] or not row["Categorias"] or not (row.get("Preco") or row.get("Preço"))
    ]
    if missing:
        raise SystemExit(f"Rows missing required values: {missing}")


def write_outputs(columns: list[str], rows: list[dict[str, str]], athos: dict[str, dict[str, str]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    import_path = OUTPUT_DIR / "00_produtos_fotos_farmacia_woocommerce_import.csv"
    review_path = OUTPUT_DIR / "01_produtos_fotos_farmacia_revisao.csv"
    readme_path = OUTPUT_DIR / "README_PRODUTOS_FOTOS_FARMACIA.md"

    with import_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "ean",
            "nome_foto",
            "nome_importacao",
            "cadastro_athos",
            "marca_importacao",
            "preco",
            "estoque",
            "categoria",
            "tipo",
            "familia",
            "variacao",
            "foto_origem",
            "observacao",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for product in PRODUCTS:
            source = athos[product.ean]
            writer.writerow(
                {
                    "ean": product.ean,
                    "nome_foto": product.photo_name,
                    "nome_importacao": product.import_name,
                    "cadastro_athos": f"{source['Descricao']} - {source['Marca']}",
                    "marca_importacao": product.brand,
                    "preco": source["Preco"],
                    "estoque": str(stock_int(source["Estoque"])),
                    "categoria": product.category,
                    "tipo": "variacao" if product.group else "simples",
                    "familia": product.group or "",
                    "variacao": product.variation,
                    "foto_origem": product.photo_file,
                    "observacao": product.note or "Imagem ainda precisa virar URL publica antes do import com foto.",
                }
            )

    simple_count = sum(1 for row in rows if row["Tipo"] == "simple")
    variation_count = sum(1 for row in rows if row["Tipo"] == "variation")
    parent_count = sum(1 for row in rows if row["Tipo"] == "variable")
    readme_path.write_text(
        "\n".join(
            [
                "# Produtos das fotos - Farmacia Pet",
                "",
                "CSV de importacao WooCommerce gerado a partir das fotos enviadas em 2026-06-17.",
                "",
                f"- Itens das fotos conferidos no Athos: {len(PRODUCTS)}",
                f"- Linhas no import: {len(rows)} ({parent_count} pais, {variation_count} variacoes, {simple_count} simples)",
                "- Fonte de preco/estoque/SKU: data/input/Athos.csv",
                "- Imagens: nao foram preenchidas no import, porque o WooCommerce precisa de URL publica; use as fotos indicadas no arquivo de revisao.",
                "- Oraldia: o cadastro Athos esta como ORALCLIN para os mesmos EANs encontrados.",
                "- Effipro Spray: incluido porque aparece na foto, apesar de ter sido excluido do lote antigo de medicamentos por ser spray.",
                "",
                "Arquivos:",
                "",
                "- 00_produtos_fotos_farmacia_woocommerce_import.csv",
                "- 01_produtos_fotos_farmacia_revisao.csv",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    columns = read_header()
    athos = load_athos()
    rows = build_rows(columns, athos)
    validate(rows)
    write_outputs(columns, rows, athos)
    print(f"Photo products: {len(PRODUCTS)}")
    print(f"Import rows: {len(rows)}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
