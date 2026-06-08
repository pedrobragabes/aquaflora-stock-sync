from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_SOURCE = Path(
    r"data/output/dry_run_refine_20260511_121244/por_categoria_site/01_pets/00_pets_woocommerce_import_reduzido.csv"
)
DEFAULT_OUTPUT_DIR = Path(
    r"data/output/dry_run_refine_20260511_121244/por_categoria_site/01_pets/woocommerce_import_menu_site_20260520"
)

CATEGORY_DOG_FOOD = "Pets > Cães > Rações Cães"
CATEGORY_DOG_TREATS = "Pets > Cães > Petiscos Cães"
CATEGORY_DOG_ACCESSORIES = "Pets > Cães > Acessórios Cães"
CATEGORY_DOG_TOYS = "Pets > Cães > Brinquedos Cães"
CATEGORY_DOG_HYGIENE = "Pets > Cães > Higiene Cães"
CATEGORY_CAT_FOOD = "Pets > Gatos > Rações Gatos"
CATEGORY_CAT_LITTER = "Pets > Gatos > Areias & Higiene"
CATEGORY_CAT_ACCESSORIES_TOYS = "Pets > Gatos > Acessórios & Brinquedos Gatos"
CATEGORY_PHARM_ANTIPARASITIC = "Pets > Farmácia Veterinária > Antipulgas & Vermífugos"
CATEGORY_PHARM_MEDICINE = "Pets > Farmácia Veterinária > Medicamentos & Tratamentos"
CATEGORY_PHARM_SUPPLEMENT = "Pets > Farmácia Veterinária > Suplementos"
CATEGORY_BIRDS_RODENTS = "Pets > Pássaros & Roedores > Gaiolas"

MENU_CATEGORIES = [
    CATEGORY_DOG_FOOD,
    CATEGORY_DOG_TREATS,
    CATEGORY_DOG_ACCESSORIES,
    CATEGORY_DOG_TOYS,
    CATEGORY_DOG_HYGIENE,
    CATEGORY_CAT_FOOD,
    CATEGORY_CAT_LITTER,
    CATEGORY_CAT_ACCESSORIES_TOYS,
    CATEGORY_PHARM_ANTIPARASITIC,
    CATEGORY_PHARM_MEDICINE,
    CATEGORY_PHARM_SUPPLEMENT,
    CATEGORY_BIRDS_RODENTS,
]
ALLOWED_EXISTING_CATEGORIES = set(MENU_CATEGORIES)


def normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text.lower()).strip()


def has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def has_word_any(text: str, terms: tuple[str, ...]) -> bool:
    words = set(re.findall(r"[a-z0-9]+", text))
    return any(term in words for term in terms)


def classify_menu_category(name: str, current_category: str) -> str | None:
    text = normalize(f"{name} {current_category}")
    name_text = normalize(name)
    current = normalize(current_category)

    if "aquarismo" in current or has_any(
        name_text,
        (
            "aquario",
            "canister",
            "dophin",
            "sarlobetter",
            "ocean tech",
            "submersa",
            "filtro externo",
        ),
    ):
        return None

    if "roupas" in current or "cosmeticos" in current:
        return None

    if has_any(
        name_text,
        (
            "glifosato",
            "raticida",
            "mata mato",
            "herbicida",
            "inseticida jardim",
            "inseticida",
            "agro",
            "agulha",
            "seringa",
            "creolina",
            "formicida",
            "pulverizador",
            "bezerro",
            "bovilis",
            "bovino",
            "vaca seca",
            "diazinon",
            "butox",
            "ficam",
            "poderoso",
        ),
    ):
        return None

    if has_word_any(
        name_text,
        ("passaro", "passaros", "ave", "aves", "calopsita", "canario", "periquito", "hamster", "roedor", "coelho"),
    ):
        return CATEGORY_BIRDS_RODENTS

    is_farm_trigger = (
        "farmacia" in current
        or has_any(name_text, ("antipulgas", "vermifugo", "medic", "suplement", "vitamin"))
        or has_word_any(name_text, ("verme", "vermes"))
    )
    if is_farm_trigger:
        if has_any(
            name_text,
            (
                "antipulgas",
                "anti pulgas",
                "pulga",
                "carrapato",
                "vermifugo",
                "vermivet",
                "drontal",
                "endogard",
                "canex",
                "bravecto",
                "nexgard",
                "simparic",
                "frontline",
                "advocate",
                "revolution",
                "capstar",
                "dectomax",
            ),
        ):
            return CATEGORY_PHARM_ANTIPARASITIC
        if has_any(
            name_text,
            (
                "suplement",
                "vitamin",
                "hemolitan",
                "glicopan",
                "organew",
                "probiot",
                "calcio",
                "omega",
                "condro",
                "promun",
                "nutri",
            ),
        ):
            return CATEGORY_PHARM_SUPPLEMENT
        return CATEGORY_PHARM_MEDICINE

    is_cat = has_any(name_text, ("gato", "gatos", "cat", "cats", "felino", "felina", "pipicat", "progato"))
    is_dog = has_any(name_text, ("cao", "caes", "cachorro", "dog", "dogs", "canino", "canina", "puppy"))
    is_treat = has_any(name_text, ("petisco", "bifinho", "biscoito", "snack", "osso", "palito", "agradin"))
    is_food = has_any(name_text, ("racao", "sache", "alimento", "golden", "premier", "special dog", "special cat"))
    is_litter = has_any(
        name_text,
        ("areia", "tapete", "sanitario", "higienico", "granulado", "pipicat", "progato", "maxxi cat", "micro silica"),
    )
    is_toy = has_any(name_text, ("brinquedo", "mordedor", "bolinha", "bola", "arranhador", "ratinho"))
    is_accessory = has_any(
        name_text,
        (
            "comedouro",
            "bebedouro",
            "coleira",
            "guia",
            "peitoral",
            "focinheira",
            "cama",
            "casa",
            "transporte",
            "caixa",
            "bolsa",
            "corrente",
            "colchonete",
            "pote",
            "comed",
        ),
    )
    is_hygiene = has_any(name_text, ("shampoo", "condicionador", "perfume", "banho", "higiene", "eliminador", "limpa", "limpador"))

    if is_cat and (is_food or "racoes" in current):
        return CATEGORY_CAT_FOOD
    if is_cat and (is_litter or is_hygiene):
        return CATEGORY_CAT_LITTER
    if is_cat and (is_toy or is_accessory or "brinquedos" in current or "acessorios" in current):
        return CATEGORY_CAT_ACCESSORIES_TOYS

    if is_litter or "areias" in current:
        return CATEGORY_CAT_LITTER
    if is_treat:
        return CATEGORY_DOG_TREATS
    if is_food or "racoes" in current:
        return CATEGORY_DOG_FOOD
    if is_toy or "brinquedos" in current:
        return CATEGORY_DOG_TOYS
    if is_accessory or "acessorios" in current:
        return CATEGORY_DOG_ACCESSORIES
    if is_hygiene or "higiene" in current:
        return CATEGORY_DOG_HYGIENE

    return None


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parent_sku(row: dict[str, str]) -> str:
    raw = (row.get("Ascendente") or "").strip()
    if raw.lower().startswith("sku:"):
        return raw.split(":", 1)[1].strip()
    return raw


def group_product_rows(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    by_sku = {row.get("SKU", ""): row for row in rows if row.get("SKU")}
    children: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("Tipo") == "variation":
            children[parent_sku(row)].append(row)

    grouped: list[list[dict[str, str]]] = []
    consumed: set[int] = set()
    for row in rows:
        if id(row) in consumed or row.get("Tipo") == "variation":
            continue
        if row.get("Tipo") == "variable":
            group = [row, *children.get(row.get("SKU", ""), [])]
        else:
            group = [row]
        grouped.append(group)
        consumed.update(id(item) for item in group)

    for row in rows:
        if row.get("Tipo") == "variation" and id(row) not in consumed:
            grouped.append([row])

    return grouped


def classify_group(group: list[dict[str, str]]) -> str | None:
    head = group[0]
    names = " ".join(row.get("Nome", "") for row in group)
    current_category = head.get("Categorias", "")
    return classify_menu_category(names, current_category)


def retag_row(row: dict[str, str], category: str) -> dict[str, str]:
    updated = dict(row)
    updated["Categorias"] = category
    tags = [part.strip() for part in category.replace(">", ",").split(",") if part.strip()]
    brand = (updated.get("Marcas") or "").strip()
    if brand:
        tags.append(brand)
    updated["Tags"] = ", ".join(dict.fromkeys(tags))
    return updated


def slug_for_category(category: str) -> str:
    return normalize(category.replace(">", " ")).replace(" ", "_").replace("&", "e")


def build_menu_package(source: Path, output_dir: Path) -> dict[str, int]:
    rows, fieldnames = read_csv(source)
    imported: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    summary = Counter()

    for group in group_product_rows(rows):
        category = classify_group(group)
        if category not in ALLOWED_EXISTING_CATEGORIES:
            category = None
        if category is None:
            for row in group:
                blocked_row = dict(row)
                blocked_row["Motivo bloqueio menu"] = "fora_do_menu_pets_site_ou_revisao_manual"
                blocked.append(blocked_row)
            continue
        for row in group:
            imported.append(retag_row(row, category))
        summary[category] += sum(1 for row in group if row.get("Tipo") in {"simple", "variable"})

    write_csv(output_dir / "00_pets_importar_menu_site.csv", imported, fieldnames)
    write_csv(output_dir / "99_pets_bloqueados_fora_menu_site.csv", blocked, [*fieldnames, "Motivo bloqueio menu"])

    farmacia_categories = {
        CATEGORY_PHARM_ANTIPARASITIC,
        CATEGORY_PHARM_MEDICINE,
        CATEGORY_PHARM_SUPPLEMENT,
    }
    no_farmacia = [row for row in imported if row.get("Categorias") not in farmacia_categories]
    farmacia_manual = [row for row in imported if row.get("Categorias") in farmacia_categories]
    farmacia_manual.extend(row for row in blocked if "farmacia" in normalize(row.get("Categorias", "")))
    write_csv(output_dir / "00_pets_importar_menu_site_sem_farmacia.csv", no_farmacia, fieldnames)
    write_csv(output_dir / "99_farmacia_para_revisar_manual.csv", farmacia_manual, [*fieldnames, "Motivo bloqueio menu"])

    summary_rows = [
        {
            "categoria_menu_site": category,
            "produtos_visiveis": str(summary.get(category, 0)),
            "linhas_woocommerce": str(sum(1 for row in imported if row.get("Categorias") == category)),
        }
        for category in MENU_CATEGORIES
        if summary.get(category, 0)
    ]
    write_csv(output_dir / "00_resumo_menu_site.csv", summary_rows, ["categoria_menu_site", "produtos_visiveis", "linhas_woocommerce"])

    for category in MENU_CATEGORIES:
        category_rows = [row for row in imported if row.get("Categorias") == category]
        if category_rows:
            write_csv(output_dir / "por_menu" / slug_for_category(category) / "woocommerce_import.csv", category_rows, fieldnames)

    removal_rows = [
        row
        for row in blocked
        if "aquarismo" in normalize(row.get("Categorias", "")) or "aquario" in normalize(row.get("Nome", ""))
    ]
    write_csv(output_dir / "99_remover_do_site_aquarismo.csv", removal_rows, [*fieldnames, "Motivo bloqueio menu"])

    blocked_visible = [row for row in blocked if row.get("Tipo") in {"simple", "variable"}]
    removal_fieldnames = ["Acao sugerida", "Tipo", "SKU", "Nome", "Categorias", "Preço", "Estoque", "Motivo bloqueio menu"]
    removal_visible_rows = [
        {
            "Acao sugerida": "remover_do_site",
            "Tipo": row.get("Tipo", ""),
            "SKU": row.get("SKU", ""),
            "Nome": row.get("Nome", ""),
            "Categorias": row.get("Categorias", ""),
            "Preço": row.get("Preço", ""),
            "Estoque": row.get("Estoque", ""),
            "Motivo bloqueio menu": row.get("Motivo bloqueio menu", ""),
        }
        for row in blocked_visible
    ]
    write_csv(output_dir / "99_remover_do_site_nao_pets_menu_produtos_visiveis.csv", removal_visible_rows, removal_fieldnames)

    allowed_rows = [{"categoria_existente_woocommerce": category} for category in MENU_CATEGORIES]
    write_csv(output_dir / "00_categorias_existentes_permitidas.csv", allowed_rows, ["categoria_existente_woocommerce"])

    return {
        "source_rows": len(rows),
        "import_rows": len(imported),
        "blocked_rows": len(blocked),
        "visible_import": sum(1 for row in imported if row.get("Tipo") in {"simple", "variable"}),
        "visible_import_no_farmacia": sum(1 for row in no_farmacia if row.get("Tipo") in {"simple", "variable"}),
        "visible_blocked": sum(1 for row in blocked if row.get("Tipo") in {"simple", "variable"}),
        "categories": len(summary),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refina PETS para o menu real do site.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    stats = build_menu_package(args.source, args.output_dir)
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"output_dir: {args.output_dir}")


if __name__ == "__main__":
    main()
