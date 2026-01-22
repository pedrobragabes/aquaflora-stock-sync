"""
Script para organizar imagens exportadas do WooCommerce por categoria e renomear para SKU.

Lê o CSV de exportação do WooCommerce e:
1. Extrai o SKU e a categoria de cada produto
2. Encontra a imagem correspondente nas subpastas de mês
3. Copia a imagem para data/Images woocommerce/organizado/{categoria}/{sku}.{ext}
"""

import csv
import os
import shutil
import re
from pathlib import Path
from urllib.parse import urlparse, unquote

# Caminhos
BASE_DIR = Path(__file__).parent.parent
CSV_PATH = BASE_DIR / "data" / "input" / "wc-product-export-19-1-2026-1768832406015.csv"
IMAGES_DIR = BASE_DIR / "data" / "Images woocommerce"
OUTPUT_DIR = IMAGES_DIR / "organizado"

# Mapeamento de categoria para pasta
CATEGORY_MAPPING = {
    'pesca': 'pesca',
    'pet': 'pet',
    'racao': 'racao',
    'ração': 'racao',
    'farmacia': 'farmacia',
    'farmácia': 'farmacia',
    'aquarismo': 'aquarismo',
    'passaros': 'passaros',
    'pássaros': 'passaros',
    'aves': 'aves',
    'piscina': 'piscina',
    'cutelaria': 'cutelaria',
    'ferramentas': 'ferramentas',
    'tabacaria': 'tabacaria',
    'geral': 'geral',
    'insumos': 'insumos',
    'aquário': 'aquarismo',
    'aquario': 'aquarismo',
}


def normalize_category(category_str: str) -> str:
    """Normaliza a categoria para nome de pasta."""
    if not category_str:
        return 'geral'
    
    # Pega a primeira categoria se houver múltiplas
    category = category_str.split(',')[0].strip().lower()
    
    # Tenta encontrar no mapeamento
    for key, value in CATEGORY_MAPPING.items():
        if key in category:
            return value
    
    # Se não encontrou, usa o nome normalizado
    category = re.sub(r'[^a-z0-9]', '_', category)
    return category if category else 'geral'


def extract_filename_from_url(url: str) -> str:
    """Extrai o nome do arquivo da URL."""
    parsed = urlparse(url)
    path = unquote(parsed.path)
    return os.path.basename(path)


def extract_month_from_url(url: str) -> str | None:
    """Extrai o mês da URL do WooCommerce (formato: /uploads/2025/10/...)."""
    match = re.search(r'/uploads/\d{4}/(\d{2})/', url)
    if match:
        return match.group(1)
    return None


def find_image_in_folders(filename: str, month: str | None = None) -> Path | None:
    """Encontra a imagem nas subpastas de mês."""
    # Lista de pastas de mês para procurar
    if month:
        folders_to_search = [month]
    else:
        folders_to_search = ['02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']
    
    for folder in folders_to_search:
        folder_path = IMAGES_DIR / folder
        if folder_path.exists():
            image_path = folder_path / filename
            if image_path.exists():
                return image_path
    
    return None


def get_best_version(filename: str, month: str | None = None) -> Path | None:
    """
    Encontra a melhor versão da imagem (sem sufixo de tamanho).
    
    As imagens do WooCommerce podem ter versões como:
    - imagem.png (original)
    - imagem-100x100.png (thumbnail)
    - imagem-scaled.png (scaled)
    
    Preferimos: original > scaled > maior tamanho
    """
    # Extrai o nome base (sem extensão e sem sufixo de tamanho)
    base_name = filename
    ext = ''
    
    # Separa extensão
    if '.' in filename:
        parts = filename.rsplit('.', 1)
        base_name = parts[0]
        ext = '.' + parts[1]
    
    # Remove sufixo de tamanho (-NNNxNNN) ou -scaled
    base_clean = re.sub(r'-\d+x\d+$', '', base_name)
    base_clean = re.sub(r'-scaled$', '', base_clean)
    
    # Tenta encontrar a imagem original primeiro
    original = find_image_in_folders(base_clean + ext, month)
    if original:
        return original
    
    # Tenta encontrar a versão scaled
    scaled = find_image_in_folders(base_clean + '-scaled' + ext, month)
    if scaled:
        return scaled
    
    # Tenta encontrar a versão que está na URL
    exact = find_image_in_folders(filename, month)
    if exact:
        return exact
    
    return None


def main():
    """Função principal."""
    print(f"📂 Lendo CSV: {CSV_PATH}")
    
    # Cria diretório de saída
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Estatísticas
    stats = {
        'total': 0,
        'found': 0,
        'not_found': 0,
        'copied': 0,
        'skipped': 0,
        'by_category': {}
    }
    
    # Lista de imagens não encontradas
    not_found = []
    
    # Lê o CSV
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            sku = row.get('SKU', '').strip()
            category_str = row.get('Categorias', '').strip()
            images_str = row.get('Imagens', '').strip()
            
            # Pula se não tem SKU ou imagem
            if not sku or not images_str:
                continue
            
            # Pula SKUs numéricos muito pequenos (provavelmente não são SKUs reais)
            if len(sku) < 3:
                continue
            
            stats['total'] += 1
            
            # Normaliza categoria
            category = normalize_category(category_str)
            
            # Cria pasta da categoria
            category_dir = OUTPUT_DIR / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            # Processa cada imagem (pode ter múltiplas separadas por vírgula)
            images = [url.strip() for url in images_str.split(',') if url.strip()]
            
            for idx, image_url in enumerate(images):
                filename = extract_filename_from_url(image_url)
                month = extract_month_from_url(image_url)
                
                # Encontra a melhor versão da imagem
                source_path = get_best_version(filename, month)
                
                if not source_path:
                    stats['not_found'] += 1
                    not_found.append({
                        'sku': sku,
                        'url': image_url,
                        'filename': filename
                    })
                    continue
                
                stats['found'] += 1
                
                # Define nome de destino
                ext = source_path.suffix.lower()
                if idx == 0:
                    dest_name = f"{sku}{ext}"
                else:
                    dest_name = f"{sku}_{idx+1}{ext}"
                
                dest_path = category_dir / dest_name
                
                # Copia se não existe
                if not dest_path.exists():
                    shutil.copy2(source_path, dest_path)
                    stats['copied'] += 1
                    
                    # Atualiza estatísticas por categoria
                    if category not in stats['by_category']:
                        stats['by_category'][category] = 0
                    stats['by_category'][category] += 1
                else:
                    stats['skipped'] += 1
    
    # Relatório
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO DE ORGANIZAÇÃO")
    print("=" * 60)
    print(f"Total de produtos processados: {stats['total']}")
    print(f"Imagens encontradas: {stats['found']}")
    print(f"Imagens não encontradas: {stats['not_found']}")
    print(f"Imagens copiadas: {stats['copied']}")
    print(f"Imagens já existentes (puladas): {stats['skipped']}")
    
    print("\n📁 Por categoria:")
    for cat, count in sorted(stats['by_category'].items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
    
    # Salva lista de não encontradas
    if not_found:
        log_path = OUTPUT_DIR / "nao_encontradas.txt"
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("SKU\tFilename\tURL\n")
            for item in not_found:
                f.write(f"{item['sku']}\t{item['filename']}\t{item['url']}\n")
        print(f"\n⚠️  Lista de imagens não encontradas salva em: {log_path}")
    
    print("\n✅ Concluído!")


if __name__ == '__main__':
    main()
