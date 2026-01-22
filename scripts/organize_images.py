"""
Organiza imagens por categoria/departamento baseado no SKU.
Lê o CSV do Athos e move cada imagem para sua pasta correspondente.
"""

import csv
import os
import shutil
from pathlib import Path
from collections import defaultdict

# Diretórios
BASE_DIR = Path(__file__).parent.parent
IMAGES_DIR = BASE_DIR / "data" / "images"
INPUT_CSV = BASE_DIR / "data" / "input" / "Athos.csv"


def normalize_category(dept: str) -> str:
    """Normaliza nome de departamento para nome de pasta."""
    if not dept:
        return "geral"
    
    # Mapeamento de departamentos para pastas
    mapping = {
        "pesca": "pesca",
        "pet": "pet",
        "racao": "racao",
        "ração": "racao",
        "farmacia": "farmacia",
        "farmácia": "farmacia",
        "aquarismo": "aquarismo",
        "aquario": "aquarismo",
        "aquário": "aquarismo",
        "passaros": "passaros",
        "pássaros": "passaros",
        "aves": "aves",
        "piscina": "piscina",
        "cutelaria": "cutelaria",
        "ferramentas": "ferramentas",
        "tabacaria": "tabacaria",
        "geral": "geral",
        "insumo": "insumos",
        "insumos": "insumos",
    }
    
    dept_lower = dept.lower().strip()
    
    # Busca correspondência direta
    if dept_lower in mapping:
        return mapping[dept_lower]
    
    # Busca parcial
    for key, folder in mapping.items():
        if key in dept_lower:
            return folder
    
    return "geral"


def load_sku_categories() -> dict:
    """Carrega mapeamento SKU -> Categoria do CSV."""
    sku_map = {}
    
    if not INPUT_CSV.exists():
        print(f"❌ CSV não encontrado: {INPUT_CSV}")
        return sku_map
    
    # Tenta diferentes encodings
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            with open(INPUT_CSV, encoding=encoding, newline="") as f:
                # Detecta delimitador
                sample = f.read(2048)
                f.seek(0)
                delimiter = ";" if ";" in sample else ","
                
                reader = csv.DictReader(f, delimiter=delimiter)
                
                for row in reader:
                    # Usa CodigoBarras como SKU primário (é o que está no nome da imagem)
                    sku = (
                        row.get("CodigoBarras") or
                        row.get("Codigo") or
                        row.get("Código") or
                        row.get("codigo") or
                        row.get("SKU") or
                        row.get("sku") or
                        ""
                    ).strip()
                    
                    # Tenta diferentes nomes de coluna para departamento
                    dept = (
                        row.get("Departamento") or
                        row.get("departamento") or
                        row.get("Categoria") or
                        row.get("categoria") or
                        ""
                    ).strip()
                    
                    if sku:
                        sku_map[sku] = normalize_category(dept)
                
                print(f"✅ Carregados {len(sku_map)} SKUs do CSV")
                return sku_map
                
        except Exception as e:
            continue
    
    print(f"❌ Erro ao ler CSV")
    return sku_map


def organize_images():
    """Move imagens para suas pastas de categoria."""
    print("=" * 60)
    print("🗂️  ORGANIZADOR DE IMAGENS POR CATEGORIA")
    print("=" * 60)
    
    # Carrega mapeamento
    sku_categories = load_sku_categories()
    
    if not sku_categories:
        print("❌ Nenhum SKU carregado. Abortando.")
        return
    
    # Lista imagens soltas na raiz
    images = list(IMAGES_DIR.glob("*.jpg"))
    print(f"📷 Imagens soltas na raiz: {len(images)}")
    
    if not images:
        print("✅ Nenhuma imagem para organizar!")
        return
    
    # Contadores
    stats = defaultdict(int)
    moved = 0
    not_found = 0
    errors = 0
    
    for img_path in images:
        sku = img_path.stem  # Nome sem extensão
        
        # Busca categoria
        category = sku_categories.get(sku)
        
        if not category:
            # Tenta sem zeros à esquerda
            sku_stripped = sku.lstrip("0")
            category = sku_categories.get(sku_stripped)
        
        if not category:
            not_found += 1
            # Move para "geral" como fallback
            category = "geral"
        
        # Cria pasta se não existir
        dest_folder = IMAGES_DIR / category
        dest_folder.mkdir(exist_ok=True)
        
        # Move arquivo
        dest_path = dest_folder / img_path.name
        
        try:
            if dest_path.exists():
                # Se já existe, remove o antigo e move o novo
                dest_path.unlink()
            
            shutil.move(str(img_path), str(dest_path))
            stats[category] += 1
            moved += 1
            
        except Exception as e:
            print(f"   ❌ Erro ao mover {img_path.name}: {e}")
            errors += 1
    
    # Relatório
    print()
    print("=" * 60)
    print("📊 RESULTADO")
    print("=" * 60)
    print(f"✅ Movidas: {moved}")
    print(f"⚠️  SKU não encontrado (→ geral): {not_found}")
    print(f"❌ Erros: {errors}")
    print()
    print("📁 Por categoria:")
    for cat, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count}")
    
    # Conta total por pasta
    print()
    print("📊 Total por pasta:")
    for folder in sorted(IMAGES_DIR.iterdir()):
        if folder.is_dir():
            count = len(list(folder.glob("*.jpg")))
            if count > 0:
                print(f"   {folder.name}: {count}")


if __name__ == "__main__":
    organize_images()
