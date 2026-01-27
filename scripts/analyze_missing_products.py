#!/usr/bin/env python3
"""
Analyze missing products and generate exclusion recommendations.
"""

import csv
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

# Paths
INPUT_FILE = Path("data/input/Athos.csv")
PROGRESS_FILE = Path("data/scraper_progress.json")
EXCLUSION_FILE = Path("config/exclusion_list.json")
DB_FILE = Path("products.db")
IMAGES_DIR = Path("data/images")

def load_csv_products():
    """Load all products from CSV."""
    products = []
    with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            products.append(row)
    return products

def load_progress():
    """Load scraper progress."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"completed": [], "failed": [], "excluded": [], "reused": []}

def load_exclusions():
    """Load current exclusion list."""
    if EXCLUSION_FILE.exists():
        with open(EXCLUSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"exclude_departments": [], "exclude_keywords": {}}

def find_existing_images():
    """Find all existing image files."""
    existing = set()
    for img_file in IMAGES_DIR.rglob("*.jpg"):
        sku = img_file.stem
        existing.add(sku)
    return existing

def analyze_missing():
    """Analyze products without images."""
    print("=" * 80)
    print("ANÁLISE DE PRODUTOS SEM IMAGENS")
    print("=" * 80)
    
    # Load data
    products = load_csv_products()
    progress = load_progress()
    exclusions = load_exclusions()
    existing_images = find_existing_images()
    
    # SKU sets
    completed = set(progress.get("completed", []))
    failed = set(progress.get("failed", []))
    excluded = set(progress.get("excluded", []))
    reused = set(progress.get("reused", []))
    
    print(f"\n📊 ESTATÍSTICAS GERAIS:")
    print(f"  Total produtos no CSV: {len(products)}")
    print(f"  Imagens encontradas no disco: {len(existing_images)}")
    print(f"  Scraper - Completados: {len(completed)}")
    print(f"  Scraper - Falhados: {len(failed)}")
    print(f"  Scraper - Excluídos: {len(excluded)}")
    print(f"  Scraper - Reutilizados: {len(reused)}")
    
    # Analyze missing
    missing_products = []
    missing_by_dept = defaultdict(list)
    missing_by_brand = defaultdict(list)
    
    for product in products:
        sku = product.get('CodigoBarras', '')
        if not sku or len(sku) < 5:
            continue
            
        # Check if has image
        if sku in existing_images or sku in completed or sku in reused:
            continue
            
        # This product is missing
        dept = product.get('Departamento', 'SEM DEPT').strip() or 'SEM DEPT'
        brand = product.get('Marca', 'SEM MARCA').strip() or 'SEM MARCA'
        name = product.get('Descricao', '')
        
        missing_products.append({
            'sku': sku,
            'name': name,
            'dept': dept,
            'brand': brand,
            'failed': sku in failed,
            'excluded': sku in excluded
        })
        
        missing_by_dept[dept].append(product)
        missing_by_brand[brand].append(product)
    
    print(f"\n❌ PRODUTOS SEM IMAGEM: {len(missing_products)}")
    print(f"  Cobertura atual: {len(existing_images)}/{len(products)} ({len(existing_images)/len(products)*100:.1f}%)")
    
    # Analyze by department
    print(f"\n📦 POR DEPARTAMENTO:")
    sorted_depts = sorted(missing_by_dept.items(), key=lambda x: len(x[1]), reverse=True)
    for dept, prods in sorted_depts[:15]:
        total_dept = sum(1 for p in products if p.get('Departamento', '').strip() == dept)
        missing_count = len(prods)
        coverage = (total_dept - missing_count) / total_dept * 100 if total_dept > 0 else 0
        print(f"  {dept:20s}: {missing_count:4d} faltando / {total_dept:4d} total ({coverage:.1f}% cobertura)")
    
    # Analyze by brand
    print(f"\n🏷️  POR MARCA (Top 20 com mais faltando):")
    sorted_brands = sorted(missing_by_brand.items(), key=lambda x: len(x[1]), reverse=True)
    for brand, prods in sorted_brands[:20]:
        total_brand = sum(1 for p in products if p.get('Marca', '').strip() == brand)
        missing_count = len(prods)
        coverage = (total_brand - missing_count) / total_brand * 100 if total_brand > 0 else 0
        print(f"  {brand:30s}: {missing_count:4d} faltando / {total_brand:4d} total ({coverage:.1f}% cobertura)")
    
    # Analyze failed products
    failed_products = [p for p in missing_products if p['failed']]
    print(f"\n🔴 PRODUTOS QUE FALHARAM NO SCRAPER: {len(failed_products)}")
    
    if failed_products:
        failed_by_dept = defaultdict(int)
        for p in failed_products:
            failed_by_dept[p['dept']] += 1
        
        print(f"  Por departamento:")
        for dept, count in sorted(failed_by_dept.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"    {dept:20s}: {count:4d}")
    
    # Recommendations
    print(f"\n💡 RECOMENDAÇÕES:")
    
    # Departments with very low coverage
    low_coverage_depts = []
    for dept, prods in sorted_depts:
        total_dept = sum(1 for p in products if p.get('Departamento', '').strip() == dept)
        missing_count = len(prods)
        coverage = (total_dept - missing_count) / total_dept * 100 if total_dept > 0 else 0
        
        if coverage < 30 and total_dept > 10:  # Less than 30% coverage and at least 10 products
            low_coverage_depts.append((dept, coverage, total_dept, missing_count))
    
    if low_coverage_depts:
        print(f"\n  ⚠️  Departamentos com cobertura muito baixa (< 30%):")
        for dept, coverage, total, missing in low_coverage_depts:
            print(f"    - {dept}: {coverage:.1f}% ({total-missing}/{total})")
            print(f"      Sugestão: Considere excluir ou melhorar queries de busca")
    
    # Generate exclusion recommendations
    print(f"\n📋 SUGESTÕES DE EXCLUSÃO:")
    
    # Check for generic/problematic product names
    generic_patterns = [
        'kit', 'conjunto', 'pacote', 'lote', 'sortido', 'variado',
        'promocao', 'oferta', 'combo', 'mix'
    ]
    
    generic_products = []
    for p in missing_products:
        name_lower = p['name'].lower()
        if any(pattern in name_lower for pattern in generic_patterns):
            generic_products.append(p)
    
    if generic_products:
        print(f"\n  🎁 Produtos genéricos/kits (difíceis de encontrar imagem): {len(generic_products)}")
        print(f"     Exemplos:")
        for p in generic_products[:5]:
            print(f"       - {p['name'][:60]}")
    
    # Save detailed report
    report_file = Path("data/missing_products_report.json")
    report = {
        "summary": {
            "total_products": len(products),
            "with_images": len(existing_images),
            "missing": len(missing_products),
            "coverage_percent": len(existing_images) / len(products) * 100
        },
        "missing_by_department": {
            dept: len(prods) for dept, prods in missing_by_dept.items()
        },
        "missing_by_brand": {
            brand: len(prods) for brand, prods in missing_by_brand.items()
        },
        "low_coverage_departments": [
            {"dept": dept, "coverage": coverage, "total": total, "missing": missing}
            for dept, coverage, total, missing in low_coverage_depts
        ],
        "failed_products": [
            {"sku": p['sku'], "name": p['name'], "dept": p['dept'], "brand": p['brand']}
            for p in failed_products[:100]  # Limit to first 100
        ]
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Relatório detalhado salvo em: {report_file}")
    
    return missing_products, low_coverage_depts

if __name__ == "__main__":
    analyze_missing()
