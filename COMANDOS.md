# 📚 Guia de Comandos - AquaFlora Stock Sync v3.3

> **Referência rápida de todos os comandos**  
> Última atualização: 22 Janeiro 2026 | Nova flag: `--lite-images`

---

## ⚡ Comandos Rápidos (Cheat Sheet)

```powershell
# Setup inicial (Windows)
$env:PYTHONIOENCODING="utf-8"

# Fluxo completo de produção
python scrape_all_images.py --cheap --stock-only --workers 4  # 1. Buscar imagens
python upload_images.py                                        # 2. Upload FTP
python main.py --input data/input/Athos.csv                    # 3. Gerar CSV

# Dashboard
uvicorn dashboard.app:app --reload --port 8000
```

---

## 🖼️ Image Scraper

### Comandos Principais

```powershell
# IMPORTANTE: Definir encoding UTF-8 no Windows
$env:PYTHONIOENCODING="utf-8"

# Scraper completo (prioriza estoque > 0)
python scrape_all_images.py

# Só produtos com estoque
python scrape_all_images.py --stock-only

# Modo barato (DuckDuckGo/Bing, sem Vision/Google)
python scrape_all_images.py --cheap
# ou
python scrape_all_images.py --search-mode cheap

# Paralelismo (mais rápido)
python scrape_all_images.py --cheap --workers 4

# Limitar quantidade (para testes)
python scrape_all_images.py --limit 50

# Recomeçar do zero
python scrape_all_images.py --reset

# Reprocessar apenas falhas
python scrape_all_images.py --only-failed

# Processar apenas SKUs sem imagem local
python scrape_all_images.py --only-missing-images

# Forçar reprocessamento mesmo com imagem local
python scrape_all_images.py --no-skip-existing

# Combinações úteis
python scrape_all_images.py --cheap --stock-only --workers 4
python scrape_all_images.py --only-failed --cheap --workers 2
```

### Opções Disponíveis

| Flag                           | Descrição                             |
| ------------------------------ | ------------------------------------- |
| `--stock-only`                 | Só produtos com estoque > 0           |
| `--limit N`                    | Limitar a N produtos                  |
| `--reset`                      | Recomeçar do zero (limpa progresso)   |
| `--search-mode premium\|cheap` | Define modo de busca                  |
| `--cheap`                      | Atalho para `--search-mode cheap`     |
| `--only-failed`                | Reprocessa apenas SKUs com falha      |
| `--only-missing-images`        | Processa apenas SKUs sem imagem local |
| `--skip-existing`              | Pula SKUs com imagem local (padrão)   |
| `--no-skip-existing`           | Processa mesmo com imagem local       |
| `--workers N`                  | Número de workers em paralelo         |

### Rodar em Background (PowerShell)

```powershell
# Iniciar job em background
Start-Job -ScriptBlock {
    $env:PYTHONIOENCODING="utf-8"
    cd "C:\Users\pedro\OneDrive\Documentos\aquaflora-stock-sync-main"
    python scrape_all_images.py --cheap --stock-only --workers 4 2>&1 |
        Tee-Object -FilePath logs\scraper.log
}

# Ver progresso
Get-Job | Receive-Job -Keep

# Parar
Get-Job | Stop-Job
Get-Job | Remove-Job
```

### Arquivos Gerados

| Arquivo                             | Descrição                   |
| ----------------------------------- | --------------------------- |
| `data/images/{categoria}/{SKU}.jpg` | Imagens 800x800 organizadas |
| `data/scraper_progress.json`        | Progresso (retomável)       |
| `data/vision_cache.json`            | Cache Vision AI             |
| `data/search_cache.json`            | Cache de busca por SKU      |

---

## 📤 Upload de Imagens

### Configuração FTP (.env)

```env
IMAGE_BASE_URL=https://sualoja.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=sualoja.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha
```

### Comandos

```powershell
# Ver o que seria enviado (dry-run)
python upload_images.py --dry-run

# Enviar todas as imagens pendentes
python upload_images.py

# Enviar imagem específica
python upload_images.py --sku 7898242033022

# Forçar reenvio de todas
python upload_images.py --force
```

---

## 📊 Exportação WooCommerce

### Comandos Principais

```powershell
# FULL - Atualiza tudo (nome, descrição, imagens, preço, estoque)
python main.py --input data/input/Athos.csv

# LITE - Só preço e estoque (preserva SEO manual)
python main.py --input data/input/Athos.csv --lite

# LITE+IMAGES - Preço, estoque E imagens (preserva nome/descrição)
python main.py --input data/input/Athos.csv --lite-images

# TESTE - Só PET, PESCA, AQUARISMO (importação rápida)
python main.py --input data/input/Athos.csv --teste

# DRY RUN - Simula sem gerar arquivo
python main.py --input data/input/Athos.csv --dry-run

# Combinações
python main.py --input data/input/Athos.csv --teste --dry-run
python main.py --input data/input/Athos.csv --lite-images --teste
```

### Modos de Exportação

| Modo            | Campos Atualizados                        | Uso                      |
| --------------- | ----------------------------------------- | ------------------------ |
| `--full`        | SKU, preço, estoque, nome, descrição, img | Primeira importação      |
| `--lite`        | SKU, preço, estoque                       | Updates diários (rápido) |
| `--lite-images` | SKU, preço, estoque, imagens              | Update com novas fotos   |

### Opções

| Flag            | Descrição                              |
| --------------- | -------------------------------------- |
| `--input FILE`  | Arquivo CSV do ERP                     |
| `--lite`        | Modo leve (só preço/estoque)           |
| `--lite-images` | Preço/estoque + imagens (preserva SEO) |
| `--teste`       | Só categorias principais               |
| `--dry-run`     | Simula sem gerar arquivo               |
| `--watch`       | Modo contínuo (observa mudanças)       |

### Saída

```
data/output/woocommerce_import_YYYYMMDD_HHMMSS.csv
```

---

## 🖼️ Organização de Imagens

### Organizar Imagens do Scraper

```powershell
# Organiza data/images/ por categoria
python scripts/organize_images.py
```

### Organizar Imagens do WooCommerce

```powershell
# Organiza imagens exportadas do WC
python scripts/organize_woocommerce_images.py
```

### Consolidar Imagens

```powershell
# Unifica WooCommerce + Scraper em data/images/
python scripts/consolidate_images.py
```

### Comparar Pastas

```powershell
# Compara SKUs entre pastas
python scripts/compare_images.py
```

---

## 🌐 Dashboard Web

```powershell
# Iniciar em desenvolvimento
uvicorn dashboard.app:app --reload --port 8000

# Iniciar em produção
uvicorn dashboard.app:app --host 0.0.0.0 --port 8000

# Acessar
# http://localhost:8000
```

---

## 🤖 Bot Discord

```powershell
# Iniciar bot
python bot_control.py
```

### Comandos Discord

| Comando   | Descrição              |
| --------- | ---------------------- |
| `!status` | Status do sistema      |
| `!sync`   | Executar sincronização |
| `!scrape` | Buscar imagens         |
| `!stats`  | Estatísticas           |
| `!help`   | Ajuda                  |

---

## 🐳 Docker

```powershell
# Build
docker compose build

# Iniciar serviços
docker compose up -d

# Ver logs
docker compose logs -f

# Ver logs de serviço específico
docker compose logs -f app
docker compose logs -f dashboard

# Parar
docker compose down

# Rebuild forçado
docker compose build --no-cache
docker compose up -d
```

---

## 🔧 Testes

```powershell
# Rodar todos os testes
pytest

# Testes com verbose
pytest -v

# Teste específico
pytest tests/test_parser.py

# Com cobertura
pytest --cov=src

# Testar scraper em produto específico
python scripts/test_image_scraper.py --sku 7898242033022
```

---

## 📈 Análises

```powershell
# Analisar departamentos do ERP
python scripts/analyze_departments.py

# Analisar produtos sem imagem
python scripts/analyze_missing_images.py

# Analisar departamento Geral Pesca
python scripts/analyze_geral_pesca.py
```

---

## 🗄️ Banco de Dados

```powershell
# Visualizar banco SQLite
sqlite3 products.db ".tables"
sqlite3 products.db "SELECT COUNT(*) FROM products"
sqlite3 products.db "SELECT * FROM products LIMIT 5"

# Backup
copy products.db products_backup.db

# Reset (cuidado!)
del products.db
```

---

## 🔄 Manutenção

### Limpar Cache

```powershell
# Limpar cache de busca
del data\search_cache.json

# Limpar cache Vision
del data\vision_cache.json

# Limpar progresso scraper
del data\scraper_progress.json

# Limpar logs
del logs\*.log
```

### Backup

```powershell
# Backup completo
Compress-Archive -Path data, products.db, .env -DestinationPath backup_$(Get-Date -Format yyyyMMdd).zip
```

---

## 📋 Fluxo Completo de Produção

```powershell
# 1. Preparar ambiente
$env:PYTHONIOENCODING="utf-8"

# 2. Atualizar CSV do ERP
# (copiar novo Athos.csv para data/input/)

# 3. Buscar imagens novas (opcional)
python scrape_all_images.py --cheap --stock-only --workers 4

# 4. Upload imagens para servidor (se houver novas)
python upload_images.py

# 5. Gerar CSV para WooCommerce
python main.py --input data/input/Athos.csv

# 6. Importar no WooCommerce
# - Acessar WooCommerce → Produtos → Importar
# - Selecionar arquivo de data/output/
# - Mapear campos se necessário
# - Executar importação

# 7. Verificar notificações Discord
```
