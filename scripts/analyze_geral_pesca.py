#!/usr/bin/env python3
"""
Análise refinada: Identifica produtos GERAL e PESCA que precisam de fotos,
excluindo os que já estão no WooCommerce com imagem.
"""
import csv
import os
from pathlib import Path
from datetime import datetime

# Paths
ATHOS_FILE = Path("data/input/Athos.csv")
WC_EXPORT = Path("data/input/wc-product-export-19-1-2026-1768832406015.csv")
IMAGES_DIR = Path("data/images")
OUTPUT_FILE = Path("data/produtos_geral_pesca_sem_foto.csv")
REPORT_FILE = Path("data/relatorio_geral_pesca.md")

def get_stock(p):
    try:
        return float(p.get('Estoque', '0').replace(',', '.') or 0)
    except:
        return 0

def main():
    print("=" * 70)
    print("🔍 Análise Refinada: GERAL e PESCA sem foto")
    print("=" * 70)
    
    # 1. Carregar WooCommerce export - SKUs com imagem
    wc_with_image = set()
    wc_all = set()
    
    with open(WC_EXPORT, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sku = row.get('SKU', '').strip()
            images = row.get('Imagens', '').strip()
            if sku:
                wc_all.add(sku)
                if images and 'aquafloragroshop.com.br' in images:
                    wc_with_image.add(sku)
    
    print(f"📦 WooCommerce total: {len(wc_all)} produtos")
    print(f"✅ WooCommerce com imagem: {len(wc_with_image)} produtos")
    
    # 2. Carregar imagens locais
    local_images = set(f.replace('.jpg', '') for f in os.listdir(IMAGES_DIR) if f.endswith('.jpg'))
    print(f"🖼️  Imagens locais: {len(local_images)} arquivos")
    
    # 3. Carregar Athos.csv - filtrar GERAL e PESCA
    with open(ATHOS_FILE, encoding='utf-8-sig') as f:
        products = list(csv.DictReader(f, delimiter=';'))
    
    # Filtrar apenas GERAL e PESCA
    geral_pesca = []
    for p in products:
        sku = p.get('CodigoBarras', '')
        dept = (p.get('Departamento', '') or '').upper()
        if not sku or len(sku) < 5:
            continue
        if dept in ['GERAL', 'PESCA']:
            geral_pesca.append(p)
    
    print(f"📋 Athos GERAL+PESCA: {len(geral_pesca)} produtos")
    
    # 4. Identificar produtos que PRECISAM de foto
    # - Não está no WooCommerce com imagem
    # - Não tem imagem local
    precisa_foto = []
    ja_tem_foto = []
    
    for p in geral_pesca:
        sku = p.get('CodigoBarras', '')
        
        # Já tem no WooCommerce com imagem?
        if sku in wc_with_image:
            ja_tem_foto.append(p)
            continue
        
        # Já tem imagem local?
        if sku in local_images:
            ja_tem_foto.append(p)
            continue
        
        precisa_foto.append(p)
    
    # Separar por estoque
    precisa_com_estoque = [p for p in precisa_foto if get_stock(p) > 0]
    precisa_sem_estoque = [p for p in precisa_foto if get_stock(p) <= 0]
    
    print()
    print("=" * 70)
    print("📊 RESULTADO:")
    print("=" * 70)
    print(f"✅ GERAL+PESCA já com foto:        {len(ja_tem_foto)}")
    print(f"❌ GERAL+PESCA PRECISAM de foto:   {len(precisa_foto)}")
    print(f"   - COM estoque (prioridade!):   {len(precisa_com_estoque)}")
    print(f"   - SEM estoque:                 {len(precisa_sem_estoque)}")
    print("=" * 70)
    
    # 5. Por departamento
    stats_dept = {'GERAL': {'total': 0, 'com_estoque': 0}, 'PESCA': {'total': 0, 'com_estoque': 0}}
    for p in precisa_foto:
        dept = (p.get('Departamento', '') or '').upper()
        if dept in stats_dept:
            stats_dept[dept]['total'] += 1
            if get_stock(p) > 0:
                stats_dept[dept]['com_estoque'] += 1
    
    print("\nPor Departamento:")
    for dept, stats in stats_dept.items():
        print(f"  {dept}: {stats['total']} sem foto ({stats['com_estoque']} com estoque)")
    
    # 6. Exportar CSV
    print(f"\n📄 Exportando para {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['CodigoBarras', 'Descricao', 'Marca', 'Departamento', 'Estoque', 'PrecoVenda', 'NoWooCommerce']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        
        for p in sorted(precisa_foto, key=lambda x: (0 if get_stock(x) > 0 else 1, -get_stock(x))):
            sku = p.get('CodigoBarras', '')
            writer.writerow({
                'CodigoBarras': sku,
                'Descricao': p.get('Descricao', ''),
                'Marca': p.get('Marca', ''),
                'Departamento': p.get('Departamento', ''),
                'Estoque': p.get('Estoque', '0'),
                'PrecoVenda': p.get('PrecoVenda', '0'),
                'NoWooCommerce': 'SIM' if sku in wc_all else 'NAO'
            })
    
    # 7. Gerar relatório markdown
    print(f"📋 Gerando relatório em {REPORT_FILE}...")
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 📊 Relatório: Produtos GERAL e PESCA sem Foto\n\n")
        f.write(f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        
        f.write("## Resumo\n\n")
        f.write(f"| Métrica | Valor |\n")
        f.write(f"|---------|-------|\n")
        f.write(f"| Total GERAL+PESCA no Athos | {len(geral_pesca)} |\n")
        f.write(f"| ✅ Já com foto (WC ou local) | {len(ja_tem_foto)} |\n")
        f.write(f"| ❌ **PRECISAM de foto** | **{len(precisa_foto)}** |\n")
        f.write(f"| - COM estoque (prioridade!) | **{len(precisa_com_estoque)}** |\n")
        f.write(f"| - Sem estoque | {len(precisa_sem_estoque)} |\n\n")
        
        f.write("## Por Departamento\n\n")
        f.write("| Departamento | Sem Foto | COM Estoque |\n")
        f.write("|--------------|----------|-------------|\n")
        for dept, stats in stats_dept.items():
            f.write(f"| {dept} | {stats['total']} | {stats['com_estoque']} |\n")
        
        f.write("\n## Lista: Produtos que PRECISAM de Foto + COM Estoque\n\n")
        f.write("> Prioridade máxima - produtos ativos sem imagem\n\n")
        f.write("```\n")
        for p in sorted(precisa_com_estoque, key=get_stock, reverse=True)[:100]:
            sku = p.get('CodigoBarras', '')
            name = p.get('Descricao', '')[:55]
            stock = p.get('Estoque', '0')
            dept = p.get('Departamento', '')[:12]
            wc = "WC" if sku in wc_all else "--"
            f.write(f"{sku} | {dept:7} | Est:{stock:>6} | {wc} | {name}\n")
        if len(precisa_com_estoque) > 100:
            f.write(f"... e mais {len(precisa_com_estoque) - 100} produtos\n")
        f.write("```\n\n")
        
        f.write("## Exportado\n\n")
        f.write(f"Lista completa exportada para: `{OUTPUT_FILE}`\n")
    
    print("\n✅ Concluído!")
    print(f"📄 CSV: {OUTPUT_FILE}")
    print(f"📋 Relatório: {REPORT_FILE}")

if __name__ == "__main__":
    main()
