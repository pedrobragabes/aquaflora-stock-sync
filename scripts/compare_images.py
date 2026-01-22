"""
Comparador de Imagens entre WooCommerce e Scraper.

Compara os SKUs de imagens entre:
- data/Images woocommerce/organizado/{categoria}/ (BASE - imagens profissionais)
- data/images/{categoria}/ (Scraper - imagens baixadas)
- CSV do WooCommerce (produtos ativos na loja)

Uso:
    python scripts/compare_images.py racao
    python scripts/compare_images.py pesca
    python scripts/compare_images.py --all
"""

import argparse
import csv
import os
import re
from pathlib import Path
from collections import defaultdict

# Caminhos
BASE_DIR = Path(__file__).parent.parent
WOOCOMMERCE_DIR = BASE_DIR / "data" / "images woocommerce"  # Imagens profissionais organizadas
SCRAPER_DIR = BASE_DIR / "data" / "images scraper"  # Imagens baixadas pelo scraper
CSV_PATH = BASE_DIR / "data" / "input" / "wc-product-export-19-1-2026-1768832406015.csv"


def extract_sku_from_filename(filename: str) -> tuple[str, str]:
    """
    Extrai o SKU e extensão do nome do arquivo.
    
    Exemplos:
        7896108820106.jpg -> ('7896108820106', '.jpg')
        7896108820106_2.png -> ('7896108820106', '.png')
    """
    name = Path(filename).stem  # Remove extensão
    ext = Path(filename).suffix.lower()
    
    # Remove sufixo de imagem múltipla (_2, _3, etc)
    sku = re.sub(r'_\d+$', '', name)
    
    return sku, ext


def get_images_by_sku(folder: Path) -> dict[str, list[str]]:
    """
    Retorna dicionário de SKU -> lista de arquivos.
    
    Exemplo:
        {'7896108820106': ['7896108820106.jpg', '7896108820106_2.jpg']}
    """
    if not folder.exists():
        return {}
    
    result = defaultdict(list)
    
    for file in folder.iterdir():
        if file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif']:
            sku, ext = extract_sku_from_filename(file.name)
            result[sku].append(file.name)
    
    return dict(result)


def load_woocommerce_products() -> dict[str, dict]:
    """
    Carrega produtos do CSV do WooCommerce.
    
    Retorna: {sku: {'nome': ..., 'categoria': ..., 'publicado': ..., 'imagens': ...}}
    """
    products = {}
    
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            sku = row.get('SKU', '').strip()
            if not sku:
                continue
            
            products[sku] = {
                'nome': row.get('Nome', ''),
                'categoria': row.get('Categorias', ''),
                'publicado': row.get('Publicado', '0') == '1',
                'imagens': row.get('Imagens', ''),
                'estoque': row.get('Estoque', '0'),
            }
    
    return products


def normalize_category(category_str: str) -> str:
    """Normaliza categoria para comparação."""
    if not category_str:
        return ''
    
    cat = category_str.split(',')[0].strip().lower()
    
    # Mapeamentos
    mappings = {
        'ração': 'racao',
        'farmácia': 'farmacia',
        'pássaros': 'passaros',
    }
    
    for key, value in mappings.items():
        if key in cat:
            return value
    
    return cat


def compare_category(category: str, wc_products: dict):
    """Compara imagens de uma categoria específica."""
    
    print(f"\n{'='*70}")
    print(f"📂 COMPARAÇÃO: {category.upper()}")
    print(f"{'='*70}")
    
    # Caminhos das pastas
    wc_folder = WOOCOMMERCE_DIR / category
    scraper_folder = SCRAPER_DIR / category
    
    # Obtém imagens por SKU
    wc_images = get_images_by_sku(wc_folder)
    scraper_images = get_images_by_sku(scraper_folder)
    
    # SKUs
    wc_skus = set(wc_images.keys())
    scraper_skus = set(scraper_images.keys())
    
    # Produtos do CSV na categoria
    csv_skus_in_category = {
        sku for sku, info in wc_products.items()
        if normalize_category(info['categoria']) == category
    }
    
    # Análises
    only_in_wc = wc_skus - scraper_skus
    only_in_scraper = scraper_skus - wc_skus
    in_both = wc_skus & scraper_skus
    
    # Novidades do scraper que estão no CSV (produtos ativos)
    scraper_new_active = only_in_scraper & csv_skus_in_category
    scraper_new_not_in_csv = only_in_scraper - csv_skus_in_category
    
    # SKUs no CSV que não tem imagem em nenhum lugar
    csv_without_any_image = csv_skus_in_category - wc_skus - scraper_skus
    
    # Estatísticas
    print(f"\n📊 ESTATÍSTICAS:")
    print(f"   WooCommerce organizado: {len(wc_skus)} SKUs")
    print(f"   Scraper: {len(scraper_skus)} SKUs")
    print(f"   CSV (categoria {category}): {len(csv_skus_in_category)} produtos")
    
    print(f"\n🔍 COMPARAÇÃO:")
    print(f"   ✅ Em ambos (duplicados): {len(in_both)}")
    print(f"   📸 Só no WooCommerce: {len(only_in_wc)}")
    print(f"   🆕 Só no Scraper: {len(only_in_scraper)}")
    
    print(f"\n🎯 AÇÕES SUGERIDAS:")
    print(f"   🆕 Novidades do scraper (produtos ativos): {len(scraper_new_active)}")
    print(f"   ❓ Scraper com SKU não encontrado no CSV: {len(scraper_new_not_in_csv)}")
    print(f"   ⚠️  Produtos no CSV sem nenhuma imagem: {len(csv_without_any_image)}")
    
    # Detalhes das novidades do scraper (para copiar)
    if scraper_new_active:
        print(f"\n{'─'*70}")
        print(f"🆕 NOVIDADES DO SCRAPER (produtos ativos no WooCommerce):")
        print(f"   Copiar de: {scraper_folder}")
        print(f"   Para: {wc_folder}")
        print(f"{'─'*70}")
        
        for sku in sorted(scraper_new_active)[:30]:  # Mostra até 30
            files = scraper_images[sku]
            nome = wc_products.get(sku, {}).get('nome', 'N/A')[:50]
            print(f"   {sku}: {files} -> {nome}")
        
        if len(scraper_new_active) > 30:
            print(f"   ... e mais {len(scraper_new_active) - 30} SKUs")
    
    # Duplicados com extensões diferentes
    print(f"\n{'─'*70}")
    print(f"🔄 DUPLICADOS (mesmos SKUs em ambos):")
    print(f"{'─'*70}")
    
    conflicts = []
    for sku in sorted(in_both)[:20]:  # Mostra até 20
        wc_files = wc_images[sku]
        scraper_files = scraper_images[sku]
        
        # Verifica se tem extensões diferentes
        wc_exts = {Path(f).suffix.lower() for f in wc_files}
        scraper_exts = {Path(f).suffix.lower() for f in scraper_files}
        
        if wc_exts != scraper_exts:
            conflicts.append(sku)
            print(f"   ⚠️  {sku}:")
            print(f"       WC: {wc_files}")
            print(f"       Scraper: {scraper_files}")
        else:
            print(f"   ✅ {sku}: {wc_files}")
    
    if len(in_both) > 20:
        print(f"   ... e mais {len(in_both) - 20} SKUs duplicados")
    
    if conflicts:
        print(f"\n   ⚠️  {len(conflicts)} SKUs com extensões diferentes!")
    
    # Retorna dados para uso posterior
    return {
        'category': category,
        'wc_skus': wc_skus,
        'scraper_skus': scraper_skus,
        'csv_skus': csv_skus_in_category,
        'only_in_scraper': only_in_scraper,
        'only_in_wc': only_in_wc,
        'in_both': in_both,
        'scraper_new_active': scraper_new_active,
        'scraper_new_not_in_csv': scraper_new_not_in_csv,
        'csv_without_image': csv_without_any_image,
        'scraper_images': scraper_images,
        'wc_images': wc_images,
    }


def main():
    parser = argparse.ArgumentParser(description='Compara imagens entre WooCommerce e Scraper')
    parser.add_argument('category', nargs='?', default='racao', 
                        help='Categoria para comparar (ex: racao, pesca, pet)')
    parser.add_argument('--all', action='store_true', 
                        help='Comparar todas as categorias')
    parser.add_argument('--export', action='store_true',
                        help='Exportar lista de novidades para arquivo')
    
    args = parser.parse_args()
    
    print("📥 Carregando produtos do CSV do WooCommerce...")
    wc_products = load_woocommerce_products()
    print(f"   {len(wc_products)} produtos carregados")
    
    if args.all:
        categories = ['racao', 'pesca', 'pet', 'farmacia', 'aquarismo', 
                     'passaros', 'aves', 'piscina', 'cutelaria', 'tabacaria', 'geral']
    else:
        categories = [args.category]
    
    all_results = []
    
    for category in categories:
        result = compare_category(category, wc_products)
        all_results.append(result)
        
        # Exporta lista de novidades se solicitado
        if args.export and result['scraper_new_active']:
            export_path = BASE_DIR / "data" / f"novidades_{category}.txt"
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(f"# Novidades do Scraper para copiar - {category}\n")
                f.write(f"# De: data/images/{category}/\n")
                f.write(f"# Para: data/Images woocommerce/organizado/{category}/\n\n")
                
                for sku in sorted(result['scraper_new_active']):
                    files = result['scraper_images'][sku]
                    nome = wc_products.get(sku, {}).get('nome', '')
                    f.write(f"{sku}\t{files}\t{nome}\n")
            
            print(f"\n📄 Lista exportada para: {export_path}")
    
    # Resumo final
    if len(categories) > 1:
        print(f"\n{'='*70}")
        print("📊 RESUMO GERAL")
        print(f"{'='*70}")
        
        total_novidades = sum(len(r['scraper_new_active']) for r in all_results)
        total_duplicados = sum(len(r['in_both']) for r in all_results)
        total_sem_imagem = sum(len(r['csv_without_image']) for r in all_results)
        
        print(f"   🆕 Total novidades do scraper: {total_novidades}")
        print(f"   🔄 Total duplicados: {total_duplicados}")
        print(f"   ⚠️  Total produtos sem imagem: {total_sem_imagem}")


if __name__ == '__main__':
    main()
