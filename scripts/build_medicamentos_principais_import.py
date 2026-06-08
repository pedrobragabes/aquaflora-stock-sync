"""Build a curated WooCommerce import for main pet pharmacy products.

This intentionally does not mirror the whole FARMACIA department. The output is
for storefront curation: known pet medication/care lines with stock, excluding
hospital supplies, vaccines, herbicides, rural injectables, and low-fit items.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "input" / "Athos.csv"
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
OUTPUT_DIR = (
    ROOT
    / "data"
    / "output"
    / "dry_run_refine_20260511_121244"
    / "por_categoria_site"
    / "01_pets"
    / "farmacia_pet"
    / "medicamentos_principais_20260601"
)


@dataclass(frozen=True)
class Product:
    sku: str
    ean: str
    original_name: str
    name: str
    brand: str
    price: Decimal
    stock: int
    family: str
    variation: str
    reason: str


FAMILY_RULES: list[tuple[str, str, str]] = [
    (r"\bNEXGARD SPECTRA\b", "NexGard Spectra", "antipulgas e carrapatos"),
    (r"\bNEXGARD GATO\b", "NexGard Gatos", "antipulgas e carrapatos"),
    (r"\bNEXGARD\b", "NexGard Caes", "antipulgas e carrapatos"),
    (r"\bBRAVECTO\b", "Bravecto", "antipulgas e carrapatos"),
    (r"\bFRONTLINE\b", "Frontline", "antipulgas e carrapatos"),
    (r"\bCREDELI\b", "Credeli", "antipulgas e carrapatos"),
    (r"\bCAPSTAR\b", "Capstar", "antipulgas"),
    (r"\bBOLFO\b", "Bolfo", "antipulgas"),
    (r"\bVAPONEX\b", "Coleira Vaponex", "coleira antipulgas"),
    (r"\bDRONTAL PLUS\b", "Drontal Plus", "vermifugo"),
    (r"\bDRONTAL GATOS\b", "Drontal Gatos", "vermifugo"),
    (r"\bDRONTAL PUPPY\b", "Drontal Puppy", "vermifugo"),
    (r"\bMILBEMAX CAES\b", "Milbemax Caes", "vermifugo"),
    (r"\bMILBEMAX GATOS\b", "Milbemax Gatos", "vermifugo"),
    (r"\bVERMIVET\b", "Vermivet", "vermifugo"),
    (r"\bPROVERM", "Proverme", "vermifugo"),
    (r"\bSTOMORGYL\b", "Stomorgyl", "medicamento pet"),
    (r"\bBAYTRIL FLAVOUR\b", "Baytril Flavour", "medicamento pet"),
    (r"\bAGEMOXI CL\b", "Agemoxi CL", "medicamento pet"),
    (r"\bDOXITRAT\b", "Doxitrat", "medicamento pet"),
    (r"\bDOXITABS\b", "Doxitabs Hosp", "medicamento pet"),
    (r"\bBIOFLOXACIN\b", "Biofloxacin Hosp", "medicamento pet"),
    (r"\bGAVIZ V\b", "Gaviz V", "medicamento pet"),
    (r"\bCRONIDOR\b", "Cronidor", "medicamento pet"),
    (r"\bFLAMAVET\b", "Flamavet Gatos", "medicamento pet"),
    (r"\bSEC LAC\b", "Sec Lac", "medicamento pet"),
    (r"\bAURITOP\b", "Auritop", "ouvido"),
    (r"\bOTOCALM\b", "Otocalm", "ouvido"),
    (r"\bSUROSOLVE\b", "Surosolve", "ouvido"),
    (r"\bZELOTRIL OTO\b", "Zelotril Oto", "ouvido"),
    (r"\bORALCLIN\b", "Oralclin", "saude oral"),
    (r"\bCOLIRIO\b|\bTOBRAMICINA.*COLIRIO\b", "Colirios Veterinarios", "olhos"),
    (r"\bGLICOPAN\b", "Glicopan", "suplemento"),
    (r"\bHEMOLITAN\b", "Hemolitan", "suplemento"),
    (r"\bAVITRIN\b", "Avitrin", "suplemento"),
    (r"\bLEVUFLORA\b", "Levuflora", "suplemento"),
    (r"\bPET MILK\b", "Pet Milk", "suplemento"),
    (r"\bCALMAVET\b", "Calmavet", "calmante"),
    (r"\bBACTROVET\b", "Bactrovet Prata", "cicatrizante"),
    (r"\bMATABICHEIRA\b", "Matabicheira Forte", "cicatrizante"),
    (r"\bTERRA CORTRIL\b", "Terra-Cortril Spray", "cicatrizante"),
    (r"\bTETISARNOL\b", "Tetisarnol Spray", "cicatrizante"),
    (r"\bGANADOL\b", "Ganadol", "cicatrizante"),
    (r"\bCALMINEX\b", "Calminex", "pomada"),
    (r"\bCLORESTEN\b", "Cloresten", "dermatologico"),
    (r"\bSHAMPOO.*ANTI ?PULGAS\b", "Shampoo Antipulgas", "antipulgas"),
    (r"\bTALCO ANTIPULGAS\b", "Talco Antipulgas", "antipulgas"),
]

# Short storefront assortment. Keep this intentionally small: NexGard plus
# high-fit/high-stock lines for online sales, not the whole pharmacy counter.
SHOWCASE_FAMILIES = {
    "NexGard Caes",
    "NexGard Gatos",
    "NexGard Spectra",
    "Bravecto",
    "Frontline",
    "Credeli",
    "Capstar",
    "Drontal Plus",
    "Drontal Gatos",
    "Drontal Puppy",
    "Milbemax Gatos",
    "Proverme",
    "Vermivet",
    "Stomorgyl",
    "Sec Lac",
    "Doxitabs Hosp",
    "Glicopan",
    "Levuflora",
    "Bactrovet Prata",
    "Terra-Cortril Spray",
    "Matabicheira Forte",
}

SITE_CATEGORY_BY_REASON = {
    "antipulgas": "Pets > Farmácia Veterinária > Antipulgas & Vermífugos",
    "antipulgas e carrapatos": "Pets > Farmácia Veterinária > Antipulgas & Vermífugos",
    "vermifugo": "Pets > Farmácia Veterinária > Antipulgas & Vermífugos",
    "medicamento pet": "Pets > Farmácia Veterinária > Medicamentos & Tratamentos",
    "cicatrizante": "Pets > Farmácia Veterinária > Medicamentos & Tratamentos",
    "suplemento": "Pets > Farmácia Veterinária > Suplementos",
}

CLOSED_PACKAGE_PATTERNS = [
    r"\bCX\b",
    r"\bCAIXA\b",
    r"\bCARTELA\b",
    r"\bSACHE\b",
    r"\bSACHE\b",
    r"\bCOMP\b",
    r"\bCOMPRIM",
    r"\b\d+\s*CP\b",
]

PACKAGED_BY_LINE_FAMILIES = {
    "NexGard Caes",
    "NexGard Gatos",
    "NexGard Spectra",
    "Bravecto",
    "Credeli",
    "Frontline",
}

UNIT_OR_FRACTION_PATTERNS = [
    r"\bUN\b",
    r"\bUNI\b",
    r"\bUNI\.",
    r"\bSPRAY\b",
    r"\bML\b$",
]

EXCLUDE_PATTERNS = [
    r"\bAGULHA\b",
    r"\bSERINGA\b",
    r"\bBRINCO\b",
    r"\bGLIFOSATO\b",
    r"\bCREOLINA\b",
    r"\bRATICIDA\b",
    r"\bFICAM\b",
    r"\bPODEROSO\b",
    r"\bDIAZINON\b",
    r"\bVACINA\b",
    r"\bBOVILIS\b",
    r"\bABORVAC\b",
    r"\bINJETAVEL\b",
    r"\bINJ\.\b",
    r"\bINJ\b",
    r"\bOVINO\b",
    r"\bBOVINO\b",
    r"\bVACA\b",
]

BRAND_FIXES = {
    "AGENER UNIÃO": "Agener Uniao",
    "LK KONIG": "LK Konig",
    "UCB VET": "UCB Vet",
    "J.A SAUDE ANIMAL": "J.A Saude Animal",
    "MSD": "MSD",
}


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return text.encode("ascii", "ignore").decode("ascii").upper()


def decimal_br(value: str) -> Decimal:
    try:
        return Decimal((value or "0").replace(".", "").replace(",", "."))
    except InvalidOperation:
        return Decimal("0")


def stock_int(value: str) -> int:
    return max(0, int(decimal_br(value)))


def title_pt(value: str) -> str:
    words = []
    keep_upper = {"MSD", "UCB", "LK", "CL", "ML", "MG", "KG", "CP", "S/O"}
    for raw in re.sub(r"\s+", " ", value.strip()).split(" "):
        upper = raw.upper()
        if upper in keep_upper:
            words.append(upper)
        elif re.fullmatch(r"\d+[,.]?\d*(ML|MG|KG|G|CP|%)?", upper):
            words.append(upper.replace(",", "."))
        else:
            words.append(raw[:1].upper() + raw[1:].lower())
    return " ".join(words).replace(" A ", " a ").replace(" De ", " de ")


def brand_name(value: str) -> str:
    clean = re.sub(r"\s+", " ", (value or "").strip().upper())
    return BRAND_FIXES.get(clean, title_pt(clean))


def family_for(name_norm: str) -> tuple[str, str] | None:
    if any(re.search(pattern, name_norm) for pattern in EXCLUDE_PATTERNS):
        return None
    for pattern, family, reason in FAMILY_RULES:
        if re.search(pattern, name_norm):
            return family, reason
    return None


def is_closed_package(product_name_norm: str, family: str) -> bool:
    if family in PACKAGED_BY_LINE_FAMILIES:
        return True
    if any(re.search(pattern, product_name_norm) for pattern in CLOSED_PACKAGE_PATTERNS):
        return True
    return False


def is_unit_or_fraction(product_name_norm: str, family: str) -> bool:
    if re.search(r"\bSPRAY\b", product_name_norm):
        return True
    if is_closed_package(product_name_norm, family):
        return False
    return any(re.search(pattern, product_name_norm) for pattern in UNIT_OR_FRACTION_PATTERNS)


def variation_value(original_name: str, family: str, brand: str) -> str:
    cleaned = title_pt(original_name)
    for token in [family, brand, "Merial", "Elanco", "Agener Uniao", "Vetnil"]:
        cleaned = re.sub(re.escape(token), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+-\s*$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    return cleaned or title_pt(original_name)


def parent_sku(family: str) -> str:
    slug = normalize(family)
    slug = re.sub(r"[^A-Z0-9]+", "-", slug).strip("-")
    return f"P-FARMACIA-PET-{slug}"


def load_products() -> list[Product]:
    products: list[Product] = []
    with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            stock = stock_int(row.get("Estoque", ""))
            if stock <= 0:
                continue

            original = row.get("Descricao", "").strip()
            dept = normalize(row.get("Departamento", ""))
            name_norm = normalize(original)
            family_match = family_for(name_norm)
            if not family_match:
                continue
            if dept not in {"FARMACIA", "PET"}:
                continue

            family, reason = family_match
            if family not in SHOWCASE_FAMILIES:
                continue
            if not is_closed_package(name_norm, family) or is_unit_or_fraction(name_norm, family):
                continue
            brand = brand_name(row.get("Marca", ""))
            sku = (row.get("CodigoBarras") or "").strip() or str(int(row["Codigo"]))
            ean = sku if sku.isdigit() and len(sku) in {8, 12, 13, 14} else ""
            name = f"{title_pt(original)} - {brand}" if brand and brand not in title_pt(original) else title_pt(original)
            products.append(
                Product(
                    sku=sku,
                    ean=ean,
                    original_name=original,
                    name=name,
                    brand=brand,
                    price=decimal_br(row.get("Preco", "")),
                    stock=stock,
                    family=family,
                    variation=variation_value(original, family, brand),
                    reason=reason,
                )
            )
    return sorted(products, key=lambda p: (p.family, p.name, p.sku))


def read_header() -> list[str]:
    with TEMPLATE.open("r", encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def price_br(value: Decimal | str) -> str:
    if value == "":
        return ""
    return f"{Decimal(value):.2f}".replace(".", ",")


def row_base(columns: list[str]) -> dict[str, str]:
    return {column: "" for column in columns}


def description(name: str, brand: str, reason: str) -> str:
    brand_text = f" da marca {brand}" if brand else ""
    return (
        f"<p>{name}{brand_text}, selecionado para a categoria Farmacia Pet da "
        "AquaFlora Agroshop.</p>"
        f"<p>Linha principal de {reason}. Confira a apresentacao correta antes "
        "da compra e siga a orientacao de um medico-veterinario.</p>"
    )


def site_category(reason: str) -> str:
    return SITE_CATEGORY_BY_REASON[reason]


def effective_variations(items: list[Product]) -> dict[str, str]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        counts[item.variation] += 1
    return {
        item.sku: (
            f"{item.variation} / SKU {item.sku}"
            if counts[item.variation] > 1
            else item.variation
        )
        for item in items
    }


def product_row(
    columns: list[str],
    p: Product,
    tipo: str,
    ascendente: str = "",
    variation_override: str | None = None,
) -> dict[str, str]:
    row = row_base(columns)
    row.update(
        {
            "Tipo": tipo,
            "SKU": p.sku,
            "GTIN, UPC, EAN, ou ISBN": p.ean,
            "Nome": p.name,
            "Publicado": "1",
            "Em destaque?": "0",
            "Visibilidade no catálogo": "visible",
            "Descrição curta": f"{p.name} | Farmacia Pet | AquaFlora Agroshop",
            "Descrição": description(p.name, p.brand, p.reason),
            "Status do imposto": "taxable",
            "Em estoque?": "1",
            "Estoque": str(p.stock),
            "São permitidas encomendas?": "0",
            "Vendido individualmente?": "0",
            "Permitir avaliações de clientes?": "1",
            "Preço": price_br(p.price),
            "Categorias": site_category(p.reason),
            "Tags": ", ".join(filter(None, ["Farmácia Veterinária", p.reason, p.brand])),
            "Ascendente": ascendente,
            "Posição": "0",
            "Marcas": p.brand,
            "Nome do atributo 1": "Opcao" if tipo == "variation" else ("Marca" if p.brand else ""),
            "Valores do atributo 1": variation_override if tipo == "variation" else p.brand,
            "Visibilidade do atributo 1": "1" if (tipo == "variation" or p.brand) else "",
            "Atributo global 1": "0" if tipo == "variation" else ("1" if p.brand else ""),
        }
    )
    return row


def parent_row(columns: list[str], family: str, items: list[Product]) -> dict[str, str]:
    first = items[0]
    row = row_base(columns)
    variations_by_sku = effective_variations(items)
    variations = [variations_by_sku[item.sku] for item in items]

    row.update(
        {
            "Tipo": "variable",
            "SKU": parent_sku(family),
            "Nome": family,
            "Publicado": "1",
            "Em destaque?": "0",
            "Visibilidade no catálogo": "visible",
            "Descrição curta": f"{family} | Farmacia Pet | AquaFlora Agroshop",
            "Descrição": description(family, "", first.reason),
            "Status do imposto": "taxable",
            "Em estoque?": "1",
            "Estoque": str(sum(item.stock for item in items)),
            "São permitidas encomendas?": "0",
            "Vendido individualmente?": "0",
            "Permitir avaliações de clientes?": "1",
            "Preço": price_br(min(item.price for item in items)),
            "Categorias": site_category(first.reason),
            "Tags": f"Farmácia Veterinária, {first.reason}",
            "Posição": "0",
            "Nome do atributo 1": "Opcao",
            "Valores do atributo 1": ", ".join(variations),
            "Visibilidade do atributo 1": "1",
            "Atributo global 1": "0",
        }
    )
    return row


def build_rows(columns: list[str], products: list[Product]) -> list[dict[str, str]]:
    grouped: dict[str, list[Product]] = defaultdict(list)
    for product in products:
        grouped[product.family].append(product)

    rows: list[dict[str, str]] = []
    for family in sorted(grouped):
        items = grouped[family]
        if len(items) == 1:
            rows.append(product_row(columns, items[0], "simple"))
            continue
        parent = parent_row(columns, family, items)
        rows.append(parent)
        p_sku = parent["SKU"]
        variations_by_sku = effective_variations(items)
        for item in items:
            rows.append(
                product_row(
                    columns,
                    item,
                    "variation",
                    p_sku,
                    variations_by_sku[item.sku],
                )
            )
    return rows


def write_outputs(products: list[Product], rows: list[dict[str, str]], columns: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    import_path = OUTPUT_DIR / "00_medicamentos_principais_woocommerce_import.csv"
    review_path = OUTPUT_DIR / "01_medicamentos_principais_revisao.csv"
    readme_path = OUTPUT_DIR / "README_MEDICAMENTOS_PRINCIPAIS.md"

    with import_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    with review_path.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "tipo",
            "sku",
            "nome",
            "familia",
            "variacao",
            "marca",
            "preco",
            "estoque",
            "motivo",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for product in products:
            writer.writerow(
                {
                    "tipo": "selecionado",
                    "sku": product.sku,
                    "nome": product.name,
                    "familia": product.family,
                    "variacao": product.variation,
                    "marca": product.brand,
                    "preco": price_br(product.price),
                    "estoque": product.stock,
                    "motivo": product.reason,
                }
            )

    families = len({product.family for product in products})
    variations = sum(1 for row in rows if row["Tipo"] == "variation")
    simples = sum(1 for row in rows if row["Tipo"] == "simple")
    parents = sum(1 for row in rows if row["Tipo"] == "variable")
    readme_path.write_text(
        "\n".join(
            [
                "# Medicamentos principais - Farmacia Pet",
                "",
                "Arquivo separado para importacao no WooCommerce.",
                "",
                f"- SKUs selecionados: {len(products)}",
                f"- Familias comerciais: {families}",
                f"- Linhas no import: {len(rows)} ({parents} pais, {variations} variacoes, {simples} simples)",
                "- Fonte: data/input/Athos.csv",
                "- Categorias WooCommerce: Pets > Farmácia Veterinária > Antipulgas & Vermífugos, Medicamentos & Tratamentos, ou Suplementos.",
                "- Criterio: vitrine curta de Farmacia Pet com estoque, priorizando NexGard, antipulgas/carrapatos, vermifugos e linhas de maior giro aparente.",
                "- Regra de embalagem: manter caixa/cartela/comprimidos/CP e linhas de embalagem comercial como NexGard, Bravecto, Credeli e Frontline.",
                "- Excluidos de proposito: unidades, fracionados, frascos/sprays soltos, itens de menor prioridade comercial, agulhas, seringas, vacinas, herbicidas, raticidas, creolina, brinco, injetaveis rurais e itens sem estoque.",
                "",
                "Importe primeiro este CSV em ambiente de teste/revisao visual:",
                "",
                "`00_medicamentos_principais_woocommerce_import.csv`",
                "",
                "Use `01_medicamentos_principais_revisao.csv` para conferencia humana.",
            ]
        ),
        encoding="utf-8",
    )


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

    missing_required = [
        row["SKU"]
        for row in rows
        if not row["Nome"] or not row["Categorias"] or not row["Tipo"]
    ]
    if missing_required:
        raise SystemExit(f"Rows missing required fields: {missing_required}")


def main() -> None:
    columns = read_header()
    products = load_products()
    rows = build_rows(columns, products)
    validate(rows)
    write_outputs(products, rows, columns)
    print(f"Selected SKUs: {len(products)}")
    print(f"Import rows: {len(rows)}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
