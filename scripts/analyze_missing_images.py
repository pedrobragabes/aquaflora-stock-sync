#!/usr/bin/env python3
"""
Script para analisar produtos sem imagem e gerar relatório completo.
"""
import csv
import os
import json
from pathlib import Path
from datetime import datetime

# Paths
INPUT_FILE = Path("data/input/Athos.csv")
IMAGES_DIR = Path("data/images")
PROGRESS_FILE = Path("data/scraper_progress.json")
OUTPUT_FILE = Path("data/produtos_sem_foto.csv")
REPORT_FILE = Path("data/relatorio_imagens.md")

def main():
    # Load produtos
    with open(INPUT_FILE, encoding='utf-8-sig') as f:
        products = list(csv.DictReader(f, delimiter=';'))
    
    # Load imagens existentes
    images = set(f.replace('.jpg','') for f in os.listdir(IMAGES_DIR) if f.endswith('.jpg'))
    
    # Load progress
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            progress = json.load(f)
    else:
        progress = {"completed": [], "failed": [], "excluded": [], "reused": []}
    
    completed = set(progress.get('completed', []))
    failed = set(progress.get('failed', []))
    excluded = set(progress.get('excluded', []))
    reused = set(progress.get('reused', []))
    
    # Analise
    validos = []
    sem_foto = []
    com_foto = []
    
    for p in products:
        sku = p.get('CodigoBarras', '')
        if not sku or len(sku) < 5:
            continue
        validos.append(p)
        if sku in images:
            com_foto.append(p)
        else:
            sem_foto.append(p)
    
    # Separar por estoque
    def get_stock(p):
        try:
            return float(p.get('Estoque', '0').replace(',', '.') or 0)
        except:
            return 0
    
    sem_foto_com_estoque = [p for p in sem_foto if get_stock(p) > 0]
    sem_foto_sem_estoque = [p for p in sem_foto if get_stock(p) <= 0]
    
    # Por departamento
    dept_stats = {}
    for p in sem_foto:
        dept = p.get('Departamento', 'OUTROS').upper() or 'OUTROS'
        if dept not in dept_stats:
            dept_stats[dept] = {'total': 0, 'com_estoque': 0}
        dept_stats[dept]['total'] += 1
        if get_stock(p) > 0:
            dept_stats[dept]['com_estoque'] += 1
    
    # Exportar CSV de produtos sem foto
    print(f"Exportando {len(sem_foto)} produtos sem foto para {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['CodigoBarras', 'Descricao', 'Marca', 'Departamento', 'Estoque', 'PrecoVenda', 'Status']
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        
        for p in sorted(sem_foto, key=get_stock, reverse=True):
            sku = p.get('CodigoBarras', '')
            status = 'FAILED' if sku in failed else 'EXCLUDED' if sku in excluded else 'PENDENTE'
            writer.writerow({
                'CodigoBarras': sku,
                'Descricao': p.get('Descricao', ''),
                'Marca': p.get('Marca', ''),
                'Departamento': p.get('Departamento', ''),
                'Estoque': p.get('Estoque', '0'),
                'PrecoVenda': p.get('PrecoVenda', '0'),
                'Status': status
            })
    
    # Gerar relatório
    print(f"Gerando relatório em {REPORT_FILE}...")
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("# 📊 Relatório de Imagens de Produtos\n\n")
        f.write(f"**Gerado em:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
        
        f.write("## Sumário Geral\n\n")
        f.write(f"| Métrica | Valor |\n")
        f.write(f"|---------|-------|\n")
        f.write(f"| Total produtos no CSV | {len(products)} |\n")
        f.write(f"| Produtos válidos (SKU >= 5) | {len(validos)} |\n")
        f.write(f"| **COM foto** | {len(com_foto)} ({len(com_foto)*100/len(validos):.1f}%) |\n")
        f.write(f"| **SEM foto** | {len(sem_foto)} ({len(sem_foto)*100/len(validos):.1f}%) |\n")
        f.write(f"| - SEM foto + COM estoque | {len(sem_foto_com_estoque)} |\n")
        f.write(f"| - SEM foto + SEM estoque | {len(sem_foto_sem_estoque)} |\n\n")
        
        f.write("## Status do Scraper\n\n")
        f.write(f"| Status | Quantidade |\n")
        f.write(f"|--------|------------|\n")
        f.write(f"| ✅ Completed | {len(completed)} |\n")
        f.write(f"| 🔄 Reused | {len(reused)} |\n")
        f.write(f"| ❌ Failed | {len(failed)} |\n")
        f.write(f"| ⏭️ Excluded | {len(excluded)} |\n\n")
        
        f.write("## Produtos SEM Foto por Departamento\n\n")
        f.write(f"| Departamento | Sem Foto | Com Estoque |\n")
        f.write(f"|--------------|----------|-------------|\n")
        for dept, stats in sorted(dept_stats.items(), key=lambda x: x[1]['total'], reverse=True):
            f.write(f"| {dept} | {stats['total']} | {stats['com_estoque']} |\n")
        
        f.write("\n## Lista: Produtos SEM FOTO + COM ESTOQUE\n\n")
        f.write("```\n")
        for p in sorted(sem_foto_com_estoque, key=get_stock, reverse=True):
            sku = p.get('CodigoBarras', '')
            name = p.get('Descricao', '')[:60]
            stock = p.get('Estoque', '0')
            dept = p.get('Departamento', '')[:12]
            f.write(f"{sku} | {dept:12} | Est:{stock:>6} | {name}\n")
        f.write("```\n\n")
        
        f.write("## Lista COMPLETA: Produtos SEM FOTO\n\n")
        f.write(f"> Total: {len(sem_foto)} produtos\n\n")
        f.write("```\n")
        for p in sorted(sem_foto, key=get_stock, reverse=True):
            sku = p.get('CodigoBarras', '')
            name = p.get('Descricao', '')[:55]
            stock = p.get('Estoque', '0')
            dept = p.get('Departamento', '')[:12]
            status = 'FAIL' if sku in failed else 'EXCL' if sku in excluded else 'PEND'
            f.write(f"{sku} | {dept:12} | E:{stock:>6} | {status} | {name}\n")
        f.write("```\n")
    
    # Sumário no console
    print("\n" + "="*70)
    print("📊 RELATÓRIO COMPLETO")
    print("="*70)
    print(f"Total produtos CSV:        {len(products)}")
    print(f"Produtos válidos:          {len(validos)}")
    print(f"COM foto:                  {len(com_foto)} ({len(com_foto)*100/len(validos):.1f}%)")
    print(f"SEM foto:                  {len(sem_foto)} ({len(sem_foto)*100/len(validos):.1f}%)")
    print(f"  - COM estoque sem foto:  {len(sem_foto_com_estoque)}")
    print(f"  - SEM estoque sem foto:  {len(sem_foto_sem_estoque)}")
    print("="*70)
    print(f"📄 CSV exportado:   {OUTPUT_FILE}")
    print(f"📋 Relatório:       {REPORT_FILE}")
    print("="*70)

if __name__ == "__main__":
    main()
