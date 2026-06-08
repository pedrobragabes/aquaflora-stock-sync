from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, unquote


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
DEFAULT_PUBLIC_BASE_URL = "https://aquafloragroshop.com.br/wp-content/uploads/produtos"
HOSTINGER_UPLOAD_PREFIX = "public_html/wp-content/uploads/produtos"


def normalize_text(value: str) -> str:
    value = unquote(value or "")
    value = value.replace("%20", " ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(value: str) -> set[str]:
    return {part for part in normalize_text(value).split() if len(part) > 1}


def safe_name(value: str, fallback: str = "item") -> str:
    value = normalize_text(value).replace(" ", "-")
    value = re.sub(r"[^a-z0-9._-]+", "-", value).strip("-._")
    return value[:120] or fallback


def safe_relative_path(path: Path) -> Path:
    return Path(*[safe_name(part) for part in path.parts])


def macro_from_categories(categories: str) -> str:
    if "Pesca" in categories:
        return "Pesca"
    if "Pets" in categories:
        return "Pets"
    return "Outro"


def category_bucket(categories: str) -> str:
    first = (categories or "").split(",")[0].strip()
    parts = [part.strip() for part in first.split(">") if part.strip()]
    if len(parts) >= 2:
        return parts[1]
    return parts[0] if parts else "sem_categoria"


def image_macro_from_path(path: Path) -> str:
    normalized_parts = [normalize_text(part) for part in path.parts]
    if "pesca" in normalized_parts:
        return "Pesca"
    if "pet" in normalized_parts or "pets" in normalized_parts or "racao" in normalized_parts:
        return "Pets"
    return "Outro"


def read_wc_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_wc_csv_with_fieldnames(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def iter_images(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def copy_image(src: Path, dest_dir: Path, prefix: str = "") -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    prefix = safe_name(prefix, "") if prefix else ""
    base = f"{prefix}__{safe_name(src.stem)}{src.suffix.lower()}" if prefix else f"{safe_name(src.stem)}{src.suffix.lower()}"
    dest = dest_dir / base
    if dest.exists():
        digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:8]
        dest = dest_dir / f"{dest.stem}__{digest}{dest.suffix}"
    shutil.copy2(src, dest)
    return dest


def public_url(path: Path, upload_root: Path, public_base_url: str) -> str:
    rel = path.relative_to(upload_root).as_posix()
    return f"{public_base_url.rstrip('/')}/{quote(rel)}"


def hostinger_upload_path(path: Path, upload_root: Path) -> str:
    rel = path.relative_to(upload_root).as_posix()
    return f"{HOSTINGER_UPLOAD_PREFIX}/{rel}"


def suggested_upload_file(product: "ProductImageState", extension: str = ".jpg") -> str:
    macro = safe_name(product.macro)
    category = safe_name(product.category)
    product_dir = safe_name(f"{product.sku} {product.name}")
    filename = f"{safe_name(product.sku)}__{safe_name(product.name)}{extension}"
    return f"{macro}/scraper_novo/{category}/{product_dir}/{filename}"


def score_manual_match(product_name: str, category: str, image_path: Path, manual_root: Path) -> float:
    rel = image_path.relative_to(manual_root)
    product_norm = normalize_text(product_name)
    stem_norm = normalize_text(image_path.stem)
    product_tokens = tokens(product_name)
    image_tokens = tokens(image_path.stem)

    sequence_score = SequenceMatcher(None, product_norm, stem_norm).ratio()
    if product_tokens and image_tokens:
        token_score = (2 * len(product_tokens & image_tokens)) / (len(product_tokens) + len(image_tokens))
    else:
        token_score = 0.0
    return max(sequence_score, token_score)


def number_tokens(value: str) -> set[str]:
    return {part for part in re.findall(r"\d+", normalize_text(value))}


def manual_match_allowed(product_name: str, image_path: Path, score: float) -> bool:
    product_tokens = tokens(product_name)
    image_tokens = tokens(image_path.stem)
    shared_tokens = product_tokens & image_tokens
    generic = {
        "anzol",
        "pesca",
        "peixe",
        "marine",
        "sports",
        "carretilha",
        "molinete",
        "vara",
        "boia",
        "boias",
        "barao",
        "linha",
        "com",
    }
    meaningful_shared = shared_tokens - generic
    product_numbers = number_tokens(product_name)
    image_numbers = number_tokens(image_path.stem)
    number_overlap = bool(product_numbers & image_numbers)

    if image_numbers and product_numbers and not number_overlap:
        return False
    if score >= 0.72:
        return True
    return score >= 0.58 and (len(meaningful_shared) >= 2 or number_overlap)


@dataclass
class ProductImageState:
    row: dict[str, str]
    macro: str
    category: str
    children: list[dict[str, str]] = field(default_factory=list)
    current_url: str = ""
    old_exact: list[Path] = field(default_factory=list)
    old_parent_exact: list[Path] = field(default_factory=list)
    old_child_exact: dict[str, list[Path]] = field(default_factory=dict)
    manual_matches: list[tuple[Path, float]] = field(default_factory=list)

    @property
    def sku(self) -> str:
        return self.row.get("SKU", "")

    @property
    def name(self) -> str:
        return self.row.get("Nome", "")

    def status(self) -> str:
        if self.manual_matches:
            return "usar_foto_manual_nova"
        if self.current_url:
            return "usar_imagem_atual_woo"
        if self.old_parent_exact:
            return "reaproveitar_imagem_velha_por_sku_ean"
        if self.old_child_exact:
            return "imagens_velhas_somente_variacoes"
        return "precisa_scraper_imagem"


def build_products(rows: list[dict[str, str]]) -> dict[str, ProductImageState]:
    parents = {
        row.get("SKU", ""): ProductImageState(
            row=row,
            macro=macro_from_categories(row.get("Categorias", "")),
            category=category_bucket(row.get("Categorias", "")),
            current_url=row.get("Imagens", "").strip(),
        )
        for row in rows
        if row.get("Tipo") != "variation" and row.get("SKU")
    }
    for row in rows:
        if row.get("Tipo") != "variation":
            continue
        parent_sku = row.get("Ascendente", "")
        if parent_sku in parents:
            parents[parent_sku].children.append(row)
    return parents


def candidate_codes(row: dict[str, str]) -> set[str]:
    values = {row.get("SKU", "").strip(), row.get("GTIN, UPC, EAN, or ISBN", "").strip()}
    return {value for value in values if value}


def index_exact_images(paths: list[Path]) -> dict[str, list[Path]]:
    exact: dict[str, list[Path]] = defaultdict(list)
    for path in paths:
        stem = path.stem.strip()
        if stem:
            exact[stem].append(path)
            exact[normalize_text(stem).replace(" ", "")].append(path)
    return exact


def attach_old_exact_images(products: dict[str, ProductImageState], exact_index: dict[str, list[Path]]) -> None:
    for product in products.values():
        parent_found: list[Path] = []
        for code in candidate_codes(product.row):
            parent_found.extend(exact_index.get(code, []))
            normalized_code = normalize_text(code).replace(" ", "")
            if normalized_code != code:
                parent_found.extend(exact_index.get(normalized_code, []))
        seen_parent: set[Path] = set()
        product.old_parent_exact = [path for path in parent_found if not (path in seen_parent or seen_parent.add(path))]

        child_found_all: list[Path] = []
        product.old_child_exact = {}
        for row in product.children:
            child_found: list[Path] = []
            for code in candidate_codes(row):
                child_found.extend(exact_index.get(code, []))
                normalized_code = normalize_text(code).replace(" ", "")
                if normalized_code != code:
                    child_found.extend(exact_index.get(normalized_code, []))
            seen_child: set[Path] = set()
            child_unique = [path for path in child_found if not (path in seen_child or seen_child.add(path))]
            if child_unique:
                product.old_child_exact[row.get("SKU", "")] = child_unique
                child_found_all.extend(child_unique)

        seen_all: set[Path] = set()
        product.old_exact = [
            path
            for path in [*product.old_parent_exact, *child_found_all]
            if not (path in seen_all or seen_all.add(path))
        ]


def attach_manual_matches(products: dict[str, ProductImageState], manual_images: list[Path], manual_root: Path) -> dict[Path, tuple[str, float]]:
    relevant_products = [product for product in products.values() if product.macro in {"Pesca", "Pets"}]
    assigned: dict[Path, tuple[str, float]] = {}
    for image in manual_images:
        image_macro = image_macro_from_path(image.relative_to(manual_root))
        candidates = [product for product in relevant_products if image_macro == "Outro" or product.macro == image_macro]
        best_product: ProductImageState | None = None
        best_score = 0.0
        for product in candidates:
            score = score_manual_match(product.name, product.category, image, manual_root)
            if not manual_match_allowed(product.name, image, score):
                continue
            if score > best_score:
                best_score = score
                best_product = product
        if best_product and best_score >= 0.58:
            best_product.manual_matches.append((image, best_score))
            assigned[image] = (best_product.sku, best_score)
    return assigned


def summarize_rows(products: dict[str, ProductImageState], output_root: Path, public_base_url: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    upload_root = output_root / "00_upload_hostinger"
    for product in sorted(products.values(), key=lambda item: (item.macro, item.category, item.name)):
        copied_manual: list[str] = []
        copied_old: list[str] = []
        upload_paths: list[str] = []
        upload_urls: list[str] = []
        product_dir = safe_name(f"{product.sku} {product.name}")

        if product.manual_matches:
            for src, score in product.manual_matches:
                dest = copy_image(
                    src,
                    output_root / "01_usar_agora" / product.macro / "fotos_manuais_novas" / safe_name(product.category) / product_dir,
                    f"{product.sku} score-{score:.2f}",
                )
                copied_manual.append(str(dest))
                upload_dest = copy_image(
                    src,
                    upload_root / safe_name(product.macro) / "fotos_manuais_novas" / safe_name(product.category) / product_dir,
                    f"{product.sku} score-{score:.2f}",
                )
                upload_paths.append(hostinger_upload_path(upload_dest, upload_root))
                upload_urls.append(public_url(upload_dest, upload_root, public_base_url))

        if product.old_parent_exact and not product.manual_matches and not product.current_url:
            for src in product.old_parent_exact:
                dest = copy_image(
                    src,
                    output_root / "01_usar_agora" / product.macro / "imagens_velhas_por_sku_ean" / safe_name(product.category) / product_dir,
                    product.sku,
                )
                copied_old.append(str(dest))
                upload_dest = copy_image(
                    src,
                    upload_root / safe_name(product.macro) / "imagens_velhas_por_sku_ean" / safe_name(product.category) / product_dir,
                    product.sku,
                )
                upload_paths.append(hostinger_upload_path(upload_dest, upload_root))
                upload_urls.append(public_url(upload_dest, upload_root, public_base_url))

        if product.current_url and not upload_urls:
            upload_urls.append(product.current_url)

        scraper_rel = suggested_upload_file(product)
        scraper_hostinger_path = f"{HOSTINGER_UPLOAD_PREFIX}/{scraper_rel}"
        scraper_url = f"{public_base_url.rstrip('/')}/{quote(scraper_rel)}"

        rows.append(
            {
                "status": product.status(),
                "macro": product.macro,
                "categoria": product.category,
                "tipo": product.row.get("Tipo", ""),
                "sku": product.sku,
                "nome": product.name,
                "estoque": product.row.get("Estoque", ""),
                "qtd_variacoes": len(product.children),
                "imagem_atual_woo": product.current_url,
                "qtd_imagens_manuais": len(product.manual_matches),
                "qtd_imagens_velhas_exatas": len(product.old_exact),
                "imagens_manuais_copiadas": " | ".join(copied_manual),
                "imagens_velhas_copiadas": " | ".join(copied_old),
                "upload_hostinger_caminhos": " | ".join(upload_paths),
                "imagem_publica_principal": upload_urls[0] if upload_urls else "",
                "imagens_publicas_hostinger": " | ".join(upload_urls),
                "imagens_woocommerce": ", ".join(upload_urls),
                "scraper_upload_hostinger_sugerido": scraper_hostinger_path if not upload_urls else "",
                "scraper_url_publica_sugerida": scraper_url if not upload_urls else "",
                "categorias": product.row.get("Categorias", ""),
            }
        )
    return rows


def variation_rows(
    products: dict[str, ProductImageState],
    exact_index: dict[str, list[Path]],
    output_root: Path,
    public_base_url: str,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    upload_root = output_root / "00_upload_hostinger"
    for product in products.values():
        for child in product.children:
            exact_matches: list[Path] = []
            for code in candidate_codes(child):
                exact_matches.extend(exact_index.get(code, []))
            exact_matches = list(dict.fromkeys(exact_matches))
            upload_paths: list[str] = []
            upload_urls: list[str] = []
            if exact_matches:
                product_dir = safe_name(f"{product.sku} {product.name}")
                child_dir = safe_name(f"{child.get('SKU', '')} {child.get('Nome', '')}")
                for src in exact_matches:
                    copy_image(
                        src,
                        output_root / "01_usar_agora" / product.macro / "imagens_velhas_variacoes" / safe_name(product.category) / product_dir / child_dir,
                        child.get("SKU", ""),
                    )
                    upload_dest = copy_image(
                        src,
                        upload_root / safe_name(product.macro) / "imagens_velhas_variacoes" / safe_name(product.category) / product_dir / child_dir,
                        child.get("SKU", ""),
                    )
                    upload_paths.append(hostinger_upload_path(upload_dest, upload_root))
                    upload_urls.append(public_url(upload_dest, upload_root, public_base_url))
            output.append(
                {
                    "status": "tem_imagem_velha_exata" if exact_matches else "sem_imagem_exata",
                    "macro": product.macro,
                    "categoria_pai": product.category,
                    "sku_pai": product.sku,
                    "nome_pai": product.name,
                    "sku_variacao": child.get("SKU", ""),
                    "nome_variacao": child.get("Nome", ""),
                    "estoque": child.get("Estoque", ""),
                    "qtd_imagens_velhas_exatas": len(exact_matches),
                    "imagens_velhas_exatas": " | ".join(str(path) for path in exact_matches),
                    "upload_hostinger_caminhos": " | ".join(upload_paths),
                    "imagens_woocommerce": ", ".join(upload_urls[:1]),
                }
            )
    return output


def copy_manual_backlog(
    manual_images: list[Path],
    manual_root: Path,
    assigned: dict[Path, tuple[str, float]],
    output_root: Path,
    public_base_url: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    upload_root = output_root / "00_upload_hostinger"
    for image in sorted(manual_images):
        if image in assigned:
            sku, score = assigned[image]
            rows.append(
                {
                    "status": "vinculada_a_produto_atual",
                    "macro": image_macro_from_path(image.relative_to(manual_root)),
                    "arquivo_original": str(image),
                    "sku_vinculado": sku,
                    "score": f"{score:.3f}",
                    "arquivo_copiado": "",
                    "upload_hostinger_caminho": "",
                    "url_publica_hostinger": "",
                }
            )
            continue

        macro = image_macro_from_path(image.relative_to(manual_root))
        target_root = "03_acervo_manual_sem_vinculo" if macro in {"Pesca", "Pets"} else "04_fora_do_csv_atual"
        rel_parent = safe_relative_path(image.relative_to(manual_root).parent)
        dest = copy_image(image, output_root / target_root / rel_parent)
        upload_dest = copy_image(image, upload_root / target_root / rel_parent)
        rows.append(
            {
                "status": "manual_correta_sem_vinculo_automatico" if macro in {"Pesca", "Pets"} else "manual_fora_do_csv_atual",
                "macro": macro,
                "arquivo_original": str(image),
                "sku_vinculado": "",
                "score": "",
                "arquivo_copiado": str(dest),
                "upload_hostinger_caminho": hostinger_upload_path(upload_dest, upload_root),
                "url_publica_hostinger": public_url(upload_dest, upload_root, public_base_url),
            }
        )
    return rows


def write_readme(output_root: Path, product_rows: list[dict[str, object]], variation_index: list[dict[str, object]], manual_rows: list[dict[str, object]], wc_csv: Path) -> None:
    status_counts = Counter(row["status"] for row in product_rows)
    macro_counts = Counter(row["macro"] for row in product_rows)
    variation_counts = Counter(row["status"] for row in variation_index)
    manual_counts = Counter(row["status"] for row in manual_rows)
    lines = [
        "# Organizacao de imagens WooCommerce",
        "",
        f"Base WooCommerce: `{wc_csv}`",
        "",
        "Esta pasta separa o que ja da para usar do que precisa de novo scraper de imagem. A base de produtos e o CSV atual do WooCommerce; variacoes foram ligadas aos pais pela coluna `Ascendente`.",
        "",
        "## Pastas",
        "",
        "- `01_usar_agora`: imagens copiadas que podem ser reaproveitadas agora, por foto manual nova ou match exato SKU/EAN nas imagens velhas.",
        "- `00_upload_hostinger`: copie o conteudo desta pasta para `public_html/wp-content/uploads/produtos` no Hostinger.",
        "- `02_precisa_scraper`: listas CSV dos produtos e variacoes sem imagem reaproveitavel encontrada.",
        "- `03_acervo_manual_sem_vinculo`: fotos manuais novas de Pesca/Pets que parecem corretas, mas nao tiveram vinculo automatico seguro com um produto do CSV.",
        "- `04_fora_do_csv_atual`: fotos manuais de categorias que nao aparecem no CSV atual de Pesca/Pets.",
        "- `99_relatorios`: indices completos para revisao e proximo passo.",
        "- `woocommerce_import_imagens_hostinger_full_header.csv`: CSV de importacao com o cabecalho completo do WooCommerce export; use este no importador, nao os CSVs de relatorio.",
        "- `woocommerce_import_PRODUTOS_APENAS_uma_imagem_full_header.csv`: importacao mais segura, somente produtos/pais e uma imagem principal por item.",
        "",
        "## Resumo",
        "",
        f"- Produtos/pais no CSV: {len(product_rows)} ({dict(macro_counts)})",
        f"- Status dos produtos: {dict(status_counts)}",
        f"- Variacoes: {len(variation_index)} ({dict(variation_counts)})",
        f"- Fotos manuais: {len(manual_rows)} ({dict(manual_counts)})",
        "",
        "## Como usar",
        "",
        "1. Comece por `99_relatorios/index_produtos.csv` para ver qual produto ficou com imagem manual, imagem atual do Woo, imagem velha exata ou scraper pendente.",
        "2. Suba o conteudo de `00_upload_hostinger` para `public_html/wp-content/uploads/produtos`.",
        "3. Para a proxima tentativa, prefira subir `00_upload_hostinger_PRODUTOS_APENAS/aquaflora-produtos-20260525` para `public_html/wp-content/uploads/produtos` e importar `woocommerce_import_PRODUTOS_APENAS_uma_imagem_full_header.csv`.",
        "4. Depois do upload, valide algumas URLs de `99_relatorios/urls_validar_antes_importar_PRODUTOS_APENAS.csv`; se der 404, ainda nao importe.",
        "5. Use `02_precisa_scraper/produtos_precisam_scraper.csv` como fila do novo scraper; ele ja traz `scraper_url_publica_sugerida` para salvar a futura imagem.",
        "6. Para racoes e outros itens com SKU/EAN em arquivo antigo, veja `01_usar_agora/Pets/imagens_velhas_por_sku_ean` e `99_relatorios/index_variacoes.csv`.",
        "7. Antes de importar no WooCommerce, valide visualmente os matches em lote; esta organizacao nao publica nem altera a loja.",
        "",
    ]
    (output_root / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_woocommerce_import_csv(
    source_rows: list[dict[str, str]],
    fieldnames: list[str],
    product_rows: list[dict[str, object]],
    variation_index: list[dict[str, object]],
    output_root: Path,
) -> None:
    product_images = {
        str(row["sku"]): str(row.get("imagens_woocommerce", ""))
        for row in product_rows
        if row.get("upload_hostinger_caminhos") and row.get("imagens_woocommerce")
    }
    variation_images = {
        str(row["sku_variacao"]): str(row.get("imagens_woocommerce", ""))
        for row in variation_index
        if row.get("upload_hostinger_caminhos") and row.get("imagens_woocommerce")
    }
    output_rows: list[dict[str, str]] = []
    for row in source_rows:
        sku = row.get("SKU", "")
        image = variation_images.get(sku) if row.get("Tipo") == "variation" else product_images.get(sku)
        if not image:
            continue
        updated = dict(row)
        updated["Imagens"] = image
        output_rows.append(updated)

    path = output_root / "woocommerce_import_imagens_hostinger_full_header.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    review_path = output_root / "99_relatorios" / "resumo_import_imagens_hostinger.csv"
    write_csv(
        review_path,
        [
            {
                "linhas_importacao": len(output_rows),
                "produtos_pais_ou_simples_com_imagem": len(product_images),
                "variacoes_com_imagem": len(variation_images),
                "arquivo_importacao": str(path),
            }
        ],
        [
            "linhas_importacao",
            "produtos_pais_ou_simples_com_imagem",
            "variacoes_com_imagem",
            "arquivo_importacao",
        ],
    )


def first_split_value(value: object, separator: str) -> str:
    text = str(value or "")
    return text.split(separator)[0].strip() if text else ""


def write_safe_products_only_import_csv(
    source_rows: list[dict[str, str]],
    fieldnames: list[str],
    product_rows: list[dict[str, object]],
    output_root: Path,
    public_base_url: str,
) -> None:
    flat_root = output_root / "00_upload_hostinger_PRODUTOS_APENAS" / "aquaflora-produtos-20260525"
    flat_root.mkdir(parents=True, exist_ok=True)
    image_by_sku: dict[str, dict[str, str]] = {}

    for row in product_rows:
        if row.get("status") not in {"usar_foto_manual_nova", "reaproveitar_imagem_velha_por_sku_ean"}:
            continue
        local_path = first_split_value(row.get("imagens_manuais_copiadas"), " | ") or first_split_value(row.get("imagens_velhas_copiadas"), " | ")
        if not local_path:
            continue
        src = Path(local_path)
        if not src.exists():
            continue
        sku = str(row.get("sku", ""))
        filename = f"{safe_name(sku)}__{safe_name(str(row.get('nome', '')))}{src.suffix.lower()}"
        dest = flat_root / filename
        if dest.exists():
            digest = hashlib.sha1(str(src).encode("utf-8")).hexdigest()[:8]
            dest = flat_root / f"{dest.stem}__{digest}{dest.suffix}"
        shutil.copy2(src, dest)
        rel = f"aquaflora-produtos-20260525/{dest.name}"
        image_by_sku[sku] = {
            "url": f"{public_base_url.rstrip('/')}/{quote(rel)}",
            "upload": f"{HOSTINGER_UPLOAD_PREFIX}/{rel}",
            "local": str(dest),
        }

    output_rows: list[dict[str, str]] = []
    for row in source_rows:
        if row.get("Tipo") == "variation":
            continue
        sku = row.get("SKU", "")
        image = image_by_sku.get(sku)
        if not image:
            continue
        updated = dict(row)
        updated["Imagens"] = image["url"]
        output_rows.append(updated)

    import_path = output_root / "woocommerce_import_PRODUTOS_APENAS_uma_imagem_full_header.csv"
    with import_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    validation_rows = [
        {
            "sku": sku,
            "url_publica": data["url"],
            "upload_hostinger": data["upload"],
            "arquivo_local": data["local"],
        }
        for sku, data in sorted(image_by_sku.items())
    ]
    write_csv(
        output_root / "99_relatorios" / "urls_validar_antes_importar_PRODUTOS_APENAS.csv",
        validation_rows,
        ["sku", "url_publica", "upload_hostinger", "arquivo_local"],
    )
    write_csv(
        output_root / "99_relatorios" / "resumo_import_produtos_apenas.csv",
        [
            {
                "linhas_importacao": len(output_rows),
                "imagens_para_upload": len(validation_rows),
                "pasta_upload": str(flat_root),
                "arquivo_importacao": str(import_path),
            }
        ],
        ["linhas_importacao", "imagens_para_upload", "pasta_upload", "arquivo_importacao"],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wc-dir", type=Path, default=Path("data/output/Woocommerce"))
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--output-name", default="imagens_organizadas_20260525")
    parser.add_argument("--public-base-url", default=DEFAULT_PUBLIC_BASE_URL)
    args = parser.parse_args()

    wc_dir = args.wc_dir
    wc_csv = args.csv or next(wc_dir.glob("wc-product-export-*.csv"))
    old_root = wc_dir / "IMAGENS VELHAS"
    manual_root = wc_dir / "FOTOS MANUAIS NOVAS"
    output_root = wc_dir / args.output_name
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    rows, fieldnames = read_wc_csv_with_fieldnames(wc_csv)
    products = {
        sku: product
        for sku, product in build_products(rows).items()
        if product.macro in {"Pesca", "Pets"}
    }

    old_images = iter_images(old_root)
    manual_images = iter_images(manual_root)
    old_exact_index = index_exact_images(old_images)

    attach_old_exact_images(products, old_exact_index)
    assigned_manual = attach_manual_matches(products, manual_images, manual_root)

    product_rows = summarize_rows(products, output_root, args.public_base_url)
    variation_index = variation_rows(products, old_exact_index, output_root, args.public_base_url)
    manual_rows = copy_manual_backlog(manual_images, manual_root, assigned_manual, output_root, args.public_base_url)

    reports = output_root / "99_relatorios"
    write_csv(
        reports / "index_produtos.csv",
        product_rows,
        [
            "status",
            "macro",
            "categoria",
            "tipo",
            "sku",
            "nome",
            "estoque",
            "qtd_variacoes",
            "imagem_atual_woo",
            "qtd_imagens_manuais",
            "qtd_imagens_velhas_exatas",
            "imagens_manuais_copiadas",
            "imagens_velhas_copiadas",
            "upload_hostinger_caminhos",
            "imagem_publica_principal",
            "imagens_publicas_hostinger",
            "imagens_woocommerce",
            "scraper_upload_hostinger_sugerido",
            "scraper_url_publica_sugerida",
            "categorias",
        ],
    )
    write_csv(
        reports / "index_variacoes.csv",
        variation_index,
        [
            "status",
            "macro",
            "categoria_pai",
            "sku_pai",
            "nome_pai",
            "sku_variacao",
            "nome_variacao",
            "estoque",
            "qtd_imagens_velhas_exatas",
            "imagens_velhas_exatas",
            "upload_hostinger_caminhos",
            "imagens_woocommerce",
        ],
    )
    write_csv(
        reports / "index_fotos_manuais.csv",
        manual_rows,
        [
            "status",
            "macro",
            "arquivo_original",
            "sku_vinculado",
            "score",
            "arquivo_copiado",
            "upload_hostinger_caminho",
            "url_publica_hostinger",
        ],
    )
    write_csv(
        reports / "produtos_com_imagens_para_woo.csv",
        [row for row in product_rows if row.get("imagens_woocommerce")],
        [
            "sku",
            "nome",
            "tipo",
            "macro",
            "categoria",
            "status",
            "imagens_woocommerce",
            "upload_hostinger_caminhos",
            "categorias",
        ],
    )
    write_csv(
        output_root / "02_precisa_scraper" / "fotos_manuais_vinculos_revisar.csv",
        [
            row
            for row in manual_rows
            if row["status"] == "vinculada_a_produto_atual"
            and row.get("score")
            and float(str(row["score"]).replace(",", ".")) < 0.72
        ],
        [
            "status",
            "macro",
            "arquivo_original",
            "sku_vinculado",
            "score",
            "arquivo_copiado",
            "upload_hostinger_caminho",
            "url_publica_hostinger",
        ],
    )
    write_csv(
        output_root / "02_precisa_scraper" / "produtos_precisam_scraper.csv",
        [row for row in product_rows if row["status"] == "precisa_scraper_imagem"],
        [
            "status",
            "macro",
            "categoria",
            "tipo",
            "sku",
            "nome",
            "estoque",
            "qtd_variacoes",
            "imagem_atual_woo",
            "qtd_imagens_manuais",
            "qtd_imagens_velhas_exatas",
            "scraper_upload_hostinger_sugerido",
            "scraper_url_publica_sugerida",
            "categorias",
        ],
    )
    write_csv(
        output_root / "02_precisa_scraper" / "variacoes_sem_imagem_exata.csv",
        [row for row in variation_index if row["status"] == "sem_imagem_exata"],
        [
            "status",
            "macro",
            "categoria_pai",
            "sku_pai",
            "nome_pai",
            "sku_variacao",
            "nome_variacao",
            "estoque",
            "qtd_imagens_velhas_exatas",
            "imagens_velhas_exatas",
            "upload_hostinger_caminhos",
            "imagens_woocommerce",
        ],
    )
    write_woocommerce_import_csv(rows, fieldnames, product_rows, variation_index, output_root)
    write_safe_products_only_import_csv(rows, fieldnames, product_rows, output_root, args.public_base_url)
    write_readme(output_root, product_rows, variation_index, manual_rows, wc_csv)

    print(f"Output: {output_root}")
    print(f"Products: {len(product_rows)}")
    print(f"Product status: {dict(Counter(row['status'] for row in product_rows))}")
    print(f"Variations: {len(variation_index)}")
    print(f"Variation status: {dict(Counter(row['status'] for row in variation_index))}")
    print(f"Manual images: {len(manual_rows)}")
    print(f"Manual status: {dict(Counter(row['status'] for row in manual_rows))}")


if __name__ == "__main__":
    main()
