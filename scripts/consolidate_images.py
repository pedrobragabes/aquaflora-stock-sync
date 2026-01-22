"""
Script para consolidar imagens do WooCommerce e Scraper.

1. Copia TODOS os arquivos de 'images woocommerce' para 'images' (base profissional)
2. Copia arquivos de 'images scraper' APENAS se o SKU não existir em 'images'

Resultado: pasta 'images' com todas as imagens profissionais + novidades do scraper
"""

import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

# Caminhos
BASE_DIR = Path(__file__).parent.parent
WOOCOMMERCE_DIR = BASE_DIR / "data" / "images woocommerce"
SCRAPER_DIR = BASE_DIR / "data" / "images scraper"
OUTPUT_DIR = BASE_DIR / "data" / "images"

# Categorias para processar
CATEGORIES = ['racao', 'pesca', 'pet', 'farmacia', 'aquarismo', 
              'passaros', 'aves', 'piscina', 'cutelaria', 'tabacaria', 
              'geral', 'sem_categoria']


def extract_sku_from_filename(filename: str) -> str:
    """
    Extrai o SKU do nome do arquivo.
    
    Exemplos:
        7896108820106.jpg -> '7896108820106'
        7896108820106_2.png -> '7896108820106'
    """
    name = Path(filename).stem  # Remove extensão
    # Remove sufixo de imagem múltipla (_2, _3, etc)
    sku = re.sub(r'_\d+$', '', name)
    return sku


def get_existing_skus(folder: Path) -> set:
    """Retorna conjunto de SKUs que já existem na pasta."""
    skus = set()
    if not folder.exists():
        return skus
    
    for file in folder.iterdir():
        if file.is_file():
            sku = extract_sku_from_filename(file.name)
            skus.add(sku)
    
    return skus


def copy_files(source_dir: Path, dest_dir: Path, skip_skus: set | None = None) -> dict:
    """
    Copia arquivos de source para dest.
    
    Args:
        source_dir: Pasta de origem
        dest_dir: Pasta de destino
        skip_skus: SKUs para pular (já existem)
    
    Returns:
        Estatísticas da cópia
    """
    if skip_skus is None:
        skip_skus = set()
    
    stats = {'copied': 0, 'skipped': 0, 'files': []}
    
    if not source_dir.exists():
        return stats
    
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    for file in source_dir.iterdir():
        if not file.is_file():
            continue
        
        sku = extract_sku_from_filename(file.name)
        
        if sku in skip_skus:
            stats['skipped'] += 1
            continue
        
        dest_path = dest_dir / file.name
        
        # Se já existe arquivo com mesmo nome, pula
        if dest_path.exists():
            stats['skipped'] += 1
            continue
        
        shutil.copy2(file, dest_path)
        stats['copied'] += 1
        stats['files'].append(file.name)
    
    return stats


def main():
    print("=" * 70)
    print("📦 CONSOLIDAÇÃO DE IMAGENS")
    print("=" * 70)
    print(f"\n📂 WooCommerce: {WOOCOMMERCE_DIR}")
    print(f"📂 Scraper: {SCRAPER_DIR}")
    print(f"📂 Destino: {OUTPUT_DIR}")
    
    # Estatísticas globais
    total_wc = {'copied': 0, 'skipped': 0}
    total_scraper = {'copied': 0, 'skipped': 0}
    novidades_por_categoria = defaultdict(list)
    
    for category in CATEGORIES:
        wc_folder = WOOCOMMERCE_DIR / category
        scraper_folder = SCRAPER_DIR / category
        output_folder = OUTPUT_DIR / category
        
        # Verifica se alguma das pastas existe
        if not wc_folder.exists() and not scraper_folder.exists():
            continue
        
        print(f"\n{'─'*70}")
        print(f"📁 {category.upper()}")
        print(f"{'─'*70}")
        
        # PASSO 1: Copia TODOS do WooCommerce (base)
        print(f"\n   1️⃣  Copiando do WooCommerce...")
        wc_stats = copy_files(wc_folder, output_folder)
        total_wc['copied'] += wc_stats['copied']
        total_wc['skipped'] += wc_stats['skipped']
        print(f"      ✅ Copiados: {wc_stats['copied']}")
        
        # PASSO 2: Obtém SKUs que já existem na pasta destino
        existing_skus = get_existing_skus(output_folder)
        print(f"      📊 SKUs na base: {len(existing_skus)}")
        
        # PASSO 3: Copia do Scraper apenas novidades
        print(f"\n   2️⃣  Copiando novidades do Scraper...")
        scraper_stats = copy_files(scraper_folder, output_folder, skip_skus=existing_skus)
        total_scraper['copied'] += scraper_stats['copied']
        total_scraper['skipped'] += scraper_stats['skipped']
        
        if scraper_stats['copied'] > 0:
            print(f"      🆕 Novidades: {scraper_stats['copied']}")
            for f in scraper_stats['files'][:5]:
                print(f"         + {f}")
                novidades_por_categoria[category].append(f)
            if len(scraper_stats['files']) > 5:
                print(f"         ... e mais {len(scraper_stats['files']) - 5}")
                novidades_por_categoria[category].extend(scraper_stats['files'][5:])
        else:
            print(f"      ℹ️  Nenhuma novidade (todos SKUs já existem)")
        
        print(f"      ⏭️  Pulados (já existem): {scraper_stats['skipped']}")
    
    # Resumo final
    print(f"\n{'='*70}")
    print("📊 RESUMO FINAL")
    print(f"{'='*70}")
    print(f"\n   📸 WooCommerce -> images/")
    print(f"      Copiados: {total_wc['copied']} arquivos")
    
    print(f"\n   🆕 Scraper -> images/ (apenas novidades)")
    print(f"      Copiados: {total_scraper['copied']} arquivos")
    print(f"      Pulados (SKU já existe): {total_scraper['skipped']} arquivos")
    
    print(f"\n   📦 TOTAL na pasta images/: {total_wc['copied'] + total_scraper['copied']} arquivos")
    
    # Lista novidades por categoria
    if any(novidades_por_categoria.values()):
        print(f"\n{'─'*70}")
        print("🆕 NOVIDADES DO SCRAPER POR CATEGORIA:")
        print(f"{'─'*70}")
        for cat, files in sorted(novidades_por_categoria.items(), key=lambda x: -len(x[1])):
            if files:
                print(f"   {cat}: {len(files)} novos")
    
    print(f"\n✅ Concluído! Pasta consolidada: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
