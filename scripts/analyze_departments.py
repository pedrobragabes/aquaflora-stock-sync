#!/usr/bin/env python3
"""Analyze departments and products for exclusion."""

import csv
from collections import Counter

with open('data/input/Athos.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f, delimiter=';')
    rows = list(reader)

print('=' * 70)
print('ANÁLISE DE DEPARTAMENTOS - ATHOS.CSV')
print('=' * 70)
print(f'Total produtos: {len(rows)}')
print()

# Contar departamentos
deps = Counter(r['Departamento'] for r in rows)
print('=== TODOS OS DEPARTAMENTOS ===')
for dep, count in deps.most_common():
    # Marcar os problemáticos
    problematico = ""
    dep_lower = dep.lower()
    if any(x in dep_lower for x in ['tabacaria', 'ferramenta', 'insumo']):
        problematico = "⚠️  CONSIDERAR EXCLUIR"
    print(f'  {dep}: {count} produtos {problematico}')
print()

# Análise detalhada por departamento
print('=== ANÁLISE DETALHADA ===')
print()

# FERRAMENTAS
print('🔧 FERRAMENTAS (122 produtos):')
ferramentas = [r for r in rows if r['Departamento'] == 'FERRAMENTAS']
for r in ferramentas[:10]:
    peso_estimado = "PESADO" if any(x in r['Descricao'].lower() for x in ['kg', 'saco', 'bomba', 'motor']) else ""
    print(f"   {r['Descricao'][:50]} - R${r['Preco']} {peso_estimado}")
print()

# INSUMO
print('🌱 INSUMO (72 produtos):')
insumos = [r for r in rows if r['Departamento'] == 'INSUMO']
for r in insumos[:10]:
    print(f"   {r['Descricao'][:50]} - R${r['Preco']}")
print()

# GERAL - pode ter coisas problemáticas
print('📦 GERAL - Amostra (531 produtos):')
geral = [r for r in rows if r['Departamento'] == 'GERAL']
# Mostrar alguns variados
import random
random.seed(42)
for r in random.sample(geral, min(10, len(geral))):
    print(f"   {r['Descricao'][:50]} - R${r['Preco']}")
print()

# Verificar produtos duplicados (mesmo nome, EAN diferente)
print('=== PRODUTOS DUPLICADOS (mesmo nome, EAN diferente) ===')
from collections import defaultdict
by_name = defaultdict(list)
for r in rows:
    by_name[r['Descricao']].append(r)

duplicates = [(name, prods) for name, prods in by_name.items() if len(prods) > 1]
print(f'Total: {len(duplicates)} nomes com múltiplos EANs')
for name, prods in duplicates[:10]:
    print(f'  "{name[:50]}":')
    for p in prods:
        print(f"    - EAN: {p['CodigoBarras']} | Marca: {p['Marca']}")
print()

# Sugestões de exclusão
print('=' * 70)
print('📋 SUGESTÕES DE EXCLUSÃO')
print('=' * 70)
print('''
DEPARTAMENTOS PARA EXCLUIR:
  1. TABACARIA (88) - Já excluído ✅
  2. FERRAMENTAS (122) - Pesado, frete caro
  3. INSUMO (72) - Adubos, sacos pesados

KEYWORDS ADICIONAIS:
  - "motor" - equipamentos grandes
  - "bomba" - equipamentos grandes  
  - "saco" - sacos pesados
  - "arame" - difícil embalar
  - "cano" - difícil embalar
  - "barra" - difícil embalar

TOTAL A EXCLUIR: ~282 produtos
RESTAM: ~4070 produtos
''')
