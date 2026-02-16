# 📚 Guia de Comandos - AquaFlora Stock Sync v4.0

> **Referência rápida de todos os comandos**
> Última atualização: 16 Fevereiro 2026

---

## ⚡ Comandos Rápidos

```powershell
$env:PYTHONIOENCODING="utf-8"

# Sync LITE (uso diário — só preço e estoque)
python main.py --input data/input/Athos.csv --lite

# Sync FULL (tudo)
python main.py --input data/input/Athos.csv

# Dry run (simula)
python main.py --input data/input/Athos.csv --dry-run

# Dashboard
uvicorn dashboard.app:app --reload --port 8000
```

---

## 📊 Exportação WooCommerce

```powershell
# FULL — nome, descrição, imagens, preço, estoque
python main.py --input data/input/Athos.csv

# LITE — só preço e estoque (preserva SEO manual)
python main.py --input data/input/Athos.csv --lite

# LITE+IMAGES — preço, estoque e imagens
python main.py --input data/input/Athos.csv --lite-images

# TESTE — só PET, PESCA, AQUARISMO
python main.py --input data/input/Athos.csv --teste

# DRY RUN — simula sem gerar arquivo
python main.py --input data/input/Athos.csv --dry-run
```

| Flag | Descrição |
|------|-----------|
| `--input FILE` | Arquivo CSV do ERP |
| `--lite` | Só preço/estoque |
| `--lite-images` | Preço/estoque + imagens |
| `--teste` | Só categorias principais |
| `--dry-run` | Simula sem gerar |
| `--watch` | Modo contínuo |

**Saída:** `data/output/woocommerce_*.csv`

---

## 🖼️ Image Scraper

```powershell
$env:PYTHONIOENCODING="utf-8"

# Buscar imagens faltantes (uso recomendado)
python scrape_all_images.py --only-missing-images --cheap --workers 4

# Modo barato (DuckDuckGo/Bing)
python scrape_all_images.py --cheap --workers 4

# Só com estoque
python scrape_all_images.py --stock-only --cheap

# Limitar quantidade
python scrape_all_images.py --limit 50 --cheap

# Reprocessar falhas
python scrape_all_images.py --only-failed --cheap

# Recomeçar do zero
python scrape_all_images.py --reset
```

| Flag | Descrição |
|------|-----------|
| `--stock-only` | Só com estoque > 0 |
| `--limit N` | Limitar a N produtos |
| `--reset` | Recomeçar (limpa progresso) |
| `--cheap` | DuckDuckGo/Bing |
| `--only-failed` | Só SKUs com falha |
| `--only-missing-images` | Só SKUs sem imagem |
| `--workers N` | Paralelismo |

---

## 📤 Upload de Imagens

```powershell
# Dry run
python upload_images.py --dry-run

# Enviar pendentes
python upload_images.py

# Forçar reenvio
python upload_images.py --force
```

---

## 📊 Análise de Cobertura

```powershell
python scripts/analyze_missing_products.py
```

---

## 🌐 Dashboard Web

```powershell
uvicorn dashboard.app:app --reload --port 8000
# http://localhost:8000
```

---

## 🤖 Bot Discord

```powershell
python bot_control.py
```

Comandos: `!status`, `!sync`, `!scrape`, `!stats`, `!help`

---

## 🐳 Docker

```powershell
docker compose build
docker compose up -d
docker compose logs -f
docker compose down
```

---

## 🔧 Testes

```powershell
pytest
pytest -v
pytest tests/test_parser.py
pytest --cov=src
```

---

## 🔄 Manutenção

```powershell
# Limpar caches
del data\search_cache.json
del data\vision_cache.json
del data\scraper_progress.json
del logs\*.log

# Backup
Compress-Archive -Path data, products.db, .env -DestinationPath backup_$(Get-Date -Format yyyyMMdd).zip
```

---

## 📋 Fluxo Completo

```powershell
$env:PYTHONIOENCODING="utf-8"

# 1. Copiar Athos.csv para data/input/
# 2. Analisar gaps (opcional)
python scripts/analyze_missing_products.py

# 3. Buscar imagens novas (opcional)
python scrape_all_images.py --only-missing-images --cheap --workers 4

# 4. Upload imagens (se houver novas)
python upload_images.py

# 5. Gerar CSV
python main.py --input data/input/Athos.csv --lite

# 6. Importar no WooCommerce
```
