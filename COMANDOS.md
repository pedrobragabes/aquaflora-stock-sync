# 📚 Guia de Comandos - AquaFlora Stock Sync v3.1

> **Referência rápida de todos os comandos**  
> Última atualização: 21 Janeiro 2026

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

# Limitar quantidade (para testes)
python scrape_all_images.py --limit 50

# Recomeçar do zero
python scrape_all_images.py --reset

# Combinações
python scrape_all_images.py --stock-only --limit 100
```

### Rodar em Background (PowerShell)

```powershell
# Iniciar job em background
Start-Job -ScriptBlock {
    $env:PYTHONIOENCODING="utf-8"
    cd "C:\Users\pedro\OneDrive\Documentos\aquaflora-stock-sync-main"
    python scrape_all_images.py --stock-only 2>&1 |
        Tee-Object -FilePath logs\scraper.log
}

# Ver progresso
Get-Job | Receive-Job -Keep

# Parar
Get-Job | Stop-Job
```

### Arquivos Gerados

| Arquivo                      | Descrição             |
| ---------------------------- | --------------------- |
| `data/images/*.jpg`          | Imagens 800x800       |
| `data/scraper_progress.json` | Progresso (retomável) |
| `data/vision_cache.json`     | Cache Vision AI       |
| `logs/scraper_full.log`      | Log detalhado         |

### 📤 Upload de Imagens para o Servidor

**IMPORTANTE:** O WooCommerce não consegue acessar imagens do seu PC!  
As imagens precisam estar em uma URL pública.

```powershell
# 1. Configurar credenciais FTP no .env:
#    IMAGE_BASE_URL=https://aquafloragroshop.com.br/wp-content/uploads/produtos/
#    IMAGE_FTP_HOST=aquafloragroshop.com.br
#    IMAGE_FTP_USER=usuario
#    IMAGE_FTP_PASSWORD=senha

# 2. Ver o que seria enviado (dry-run)
python upload_images.py --dry-run

# 3. Enviar todas as imagens pendentes
python upload_images.py

# 4. Enviar imagem específica
python upload_images.py --sku 7898586130210

# 5. Verificar se imagens estão acessíveis
python upload_images.py --verify

# 6. Reenviar todas (mesmo já enviadas)
python upload_images.py --all --force
```

**Fluxo completo:**

1. `python scrape_all_images.py` - Baixar imagens
2. `python upload_images.py` - Enviar para servidor
3. `python main.py --input ...` - Gerar CSV com URLs

---

## 🔄 Sincronização (main.py)

### Modos de Execução

```powershell
# FULL MODE - Atualiza tudo (nome, descrição, preço, estoque)
python main.py --input data/input/Athos.csv

# LITE MODE - Só preço e estoque (preserva SEO manual)
python main.py --input data/input/Athos.csv --lite

# MODO TESTE - Apenas PET, PESCA e AQUARISMO (importação rápida)
python main.py --input data/input/Athos.csv --teste

# DRY RUN - Simula sem alterar WooCommerce
python main.py --input data/input/Athos.csv --dry-run

# Permitir criação de novos produtos
python main.py --input data/input/Athos.csv --allow-create

# COMBINAR flags (teste + dry-run)
python main.py --input data/input/Athos.csv --teste --dry-run
```

### Mapeamento de Produtos

```powershell
# Mapear produtos existentes do WooCommerce (FAZER PRIMEIRO!)
python main.py --map-site

# Isso cria a whitelist para saber quais SKUs já existem
```

### Modo Watch (Daemon)

```powershell
# Monitora pasta e sincroniza automaticamente
python main.py --watch
```

---

## 🖥️ Dashboard Web

### Iniciar

```powershell
# Desenvolvimento
python -m uvicorn dashboard.app:app --host localhost --port 8080 --reload

# Produção
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```

### Endpoints API

| Método | Endpoint                       | Descrição             |
| ------ | ------------------------------ | --------------------- |
| GET    | `/`                            | Dashboard principal   |
| GET    | `/images`                      | Curadoria de imagens  |
| GET    | `/api/status`                  | Status do sistema     |
| POST   | `/api/sync`                    | Iniciar sincronização |
| POST   | `/api/upload`                  | Upload de CSV         |
| GET    | `/api/products`                | Listar produtos       |
| GET    | `/api/images/missing`          | Produtos sem imagem   |
| GET    | `/api/images/scraper-progress` | Status do scraper     |
| GET    | `/api/images/stats`            | Estatísticas imagens  |
| GET    | `/metrics`                     | Métricas Prometheus   |
| GET    | `/docs`                        | Swagger UI            |

### Exemplo de Uso API

```powershell
# Status
Invoke-RestMethod http://localhost:8080/api/status

# Produtos sem imagem (top 50)
Invoke-RestMethod "http://localhost:8080/api/images/missing?limit=50"

# Progresso do scraper
Invoke-RestMethod http://localhost:8080/api/images/scraper-progress
```

---

## 🤖 Bot Discord

### Iniciar

```powershell
python bot_control.py
```

### Comandos

| Comando      | Descrição                |
| ------------ | ------------------------ |
| `!status`    | Status do sistema        |
| `!sync`      | Iniciar sincronização    |
| `!sync lite` | Sync modo LITE           |
| `!ajuda`     | Lista de comandos        |
| `!produtos`  | Estatísticas de produtos |
| `!logs`      | Últimas linhas do log    |

---

## 🐳 Docker

### Comandos Docker Compose

```powershell
# Build e iniciar
docker-compose up -d

# Ver logs
docker-compose logs -f

# Logs de serviço específico
docker-compose logs dashboard -f
docker-compose logs bot -f

# Parar
docker-compose down

# Rebuild após mudanças
docker-compose build --no-cache
docker-compose up -d

# Status
docker-compose ps
```

### Executar Scraper no Container

```bash
# Entrar no container
docker-compose exec dashboard bash

# Rodar scraper
python scrape_all_images.py --stock-only
```

---

## 🧪 Testes

```powershell
# Todos os testes
pytest

# Com verbosidade
pytest -v

# Teste específico
pytest tests/test_parser.py -v

# Com coverage
pytest --cov=src --cov-report=html

# Coverage mínimo
pytest --cov=src --cov-fail-under=80
```

---

## 📁 Gerenciamento de Arquivos

### Limpar Cache/Progresso

```powershell
# Limpar progresso do scraper
Remove-Item data/scraper_progress.json -Force -ErrorAction SilentlyContinue

# Limpar cache Vision AI
Remove-Item data/vision_cache.json -Force -ErrorAction SilentlyContinue

# Limpar imagens
Remove-Item data/images/*.jpg -Force -ErrorAction SilentlyContinue

# Limpar tudo de uma vez
Remove-Item data/scraper_progress.json, data/vision_cache.json -Force -ErrorAction SilentlyContinue
Remove-Item data/images/*.jpg -Force -ErrorAction SilentlyContinue
```

### Ver Estatísticas

```powershell
# Contar imagens
(Get-ChildItem data/images/*.jpg).Count

# Ver progresso
Get-Content data/scraper_progress.json | ConvertFrom-Json |
    Select-Object -ExpandProperty stats

# Ver cache
(Get-Content data/vision_cache.json | ConvertFrom-Json).PSObject.Properties.Count
```

---

## 📊 Análise de Dados

### Analisar CSV

```powershell
# Ver primeiras linhas
Get-Content data/input/Athos.csv -First 10

# Contar linhas
(Get-Content data/input/Athos.csv).Count

# Contar por departamento
python -c "
import csv
from collections import Counter
with open('data/input/Athos.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f, delimiter=';')
    depts = Counter(r['Departamento'] for r in reader)
    for d, c in depts.most_common():
        print(f'{d}: {c}')
"
```

---

## 🔧 Utilitários

### Verificar Configuração

```powershell
# Testar conexão WooCommerce
python -c "
from config.settings import settings
print(f'WooCommerce: {settings.woo_configured}')
print(f'Google API: {bool(settings.google_api_key)}')
print(f'Vision AI: {settings.vision_ai_enabled}')
"
```

### Verificar APIs

```powershell
# Testar Google Search
python -c "
from src.image_scraper import search_images_google
results = search_images_google('coleira cachorro', max_results=1)
print(f'Google OK: {len(results)} resultado(s)')
"

# Testar Vision AI
python -c "
from src.image_scraper import VISION_AI_ENABLED, GOOGLE_API_KEY
print(f'Vision AI: {VISION_AI_ENABLED}')
print(f'API Key: {bool(GOOGLE_API_KEY)}')
"
```

---

## 📝 Logs

### Ver Logs

```powershell
# Último log de sync
Get-ChildItem logs/sync_*.log |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 |
    Get-Content -Tail 50

# Log do scraper
Get-Content logs/scraper_full.log -Tail 50

# Filtrar erros
Select-String -Path logs/*.log -Pattern "ERROR|FAIL|Exception"
```

---

## 🚀 Fluxo de Produção Completo

### 1. Preparação

```powershell
# Entrar no diretório
cd "C:\Users\pedro\OneDrive\Documentos\aquaflora-stock-sync-main"

# Definir encoding
$env:PYTHONIOENCODING="utf-8"

# Verificar que Athos.csv está atualizado
Get-Item data/input/Athos.csv | Select-Object Name, LastWriteTime
```

### 2. Buscar Imagens

```powershell
# Limpar progresso anterior (opcional)
Remove-Item data/scraper_progress.json -Force -ErrorAction SilentlyContinue

# Rodar scraper
python scrape_all_images.py --stock-only
```

### 3. Gerar CSV para WooCommerce

```powershell
# Modo FULL (primeira importação)
python main.py --input data/input/Athos.csv

# OU Modo LITE (atualizações subsequentes)
python main.py --input data/input/Athos.csv --lite
```

### 4. Importar no WooCommerce

1. Acesse: WooCommerce → Produtos → Importar
2. Selecione o CSV em `data/output/woocommerce_import_*.csv`
3. Mapeie as colunas
4. Execute importação

### 5. Verificar Produtos sem Imagem

```powershell
# Via API
Invoke-RestMethod "http://localhost:8080/api/images/missing?limit=100" |
    Select-Object -ExpandProperty missing |
    Format-Table sku, name, stock
```

---

_Guia de comandos v3.0 - AquaFlora Stock Sync_
