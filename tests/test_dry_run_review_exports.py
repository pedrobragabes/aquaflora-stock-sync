from decimal import Decimal
from pathlib import Path
import json

from main import classify_review_group, export_dry_run_review_files
from src.models import EnrichedProduct


def make_product(
    sku: str,
    name: str,
    category_original: str,
    category: str | None = None,
    weight_total_kg: float | None = None,
) -> EnrichedProduct:
    category = category or category_original.title()
    return EnrichedProduct(
        sku=sku,
        ean=None,
        name=name.title(),
        name_original=name,
        stock=3,
        price=Decimal("10.90"),
        cost=Decimal("5.00"),
        minimum=0,
        category=category,
        category_original=category_original,
        brand="Teste",
        weight_kg=None,
        weight_unit_kg=None,
        weight_total_kg=weight_total_kg,
        weight_qty=None,
        short_description="Teste",
        description="<div>Teste</div>",
        tags=[category],
    )


def test_classify_review_group_priority_groups():
    assert classify_review_group(make_product("1", "VARA TELESCOPICA", "PESCA")) == "01_pesca"
    assert classify_review_group(make_product("2", "RACAO GOLDEN CAES", "PET")) == "02_pet_racoes"
    assert classify_review_group(make_product("3", "BOLINHA MACICA PET", "PET")) == "03_pet_brinquedos"
    assert classify_review_group(make_product("4", "SHAMPOO NEUTRO PET", "PET")) == "05_pet_higiene"
    assert classify_review_group(make_product("5", "BRAVECTO ANTIPULGAS", "FARMACIA")) == "11_medicamentos"
    assert classify_review_group(make_product("6", "FILTRO AQUARIO", "AQUARISMO")) == "07_aquarismo"
    assert classify_review_group(make_product("7", "SACHE GOLDEN CAES FRANGO 85G", "PET")) == "02_pet_racoes"


def test_classify_review_group_manual_buckets():
    assert classify_review_group(make_product("8", "PRODUTO SOLTO", "GERAL")) == "12_revisar_sem_categoria"
    assert classify_review_group(make_product("9", "GAIOLA PASSARO", "PASSAROS")) == "99_adicionar_manual"
    assert classify_review_group(make_product("10", "RACAO GOLDEN CAES 10KG", "PET", weight_total_kg=10)) == "99_adicionar_manual"
    assert classify_review_group(make_product("11", "PETISCO BIFINHO CARNE 400G", "PET")) == "04_pet_acessorios"


def test_export_dry_run_review_files(tmp_path: Path):
    products = [
        make_product("1", "VARA TELESCOPICA", "PESCA"),
        make_product("2", "RACAO GOLDEN CAES", "PET"),
        make_product("3", "BRAVECTO ANTIPULGAS", "FARMACIA"),
        make_product("4", "PRODUTO SOLTO", "GERAL"),
    ]

    review_dir = export_dry_run_review_files(products, tmp_path, input_file=Path("Athos.csv"))

    assert (review_dir / "00_grupos_sugeridos.csv").exists()
    assert (review_dir / "01_pesca.csv").exists()
    assert (review_dir / "01_pesca_50_woocommerce.csv").exists()
    assert (review_dir / "02_pet_racoes.csv").exists()
    assert (review_dir / "imagens.md").exists()

    pesca_csv = (review_dir / "01_pesca.csv").read_text(encoding="utf-8-sig")
    assert "VARA TELESCOPICA" in pesca_csv
    assert "grupo_revisao" in pesca_csv

    summary = json.loads((review_dir / "refine_summary.json").read_text(encoding="utf-8"))
    counts = {group["key"]: group["count"] for group in summary["groups"]}
    assert counts["01_pesca"] == 1
    assert counts["02_pet_racoes"] == 1
    assert counts["11_medicamentos"] == 1
    assert counts["12_revisar_sem_categoria"] == 1
