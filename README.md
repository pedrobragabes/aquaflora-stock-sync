# AquaFlora Stock Sync v3.1

**Sistema completo de sincronização de estoque** - Migra dados do ERP Athos para WooCommerce com imagens automáticas via IA e upload FTP.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-green.svg)
![Vision AI](https://img.shields.io/badge/Google-Vision%20AI-orange.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

---

## 🎯 O que este projeto faz

Sistema completo para e-commerce que:

1. **Lê CSV do ERP Athos** → Parser inteligente que limpa dados "sujos"
2. **Enriquece produtos** → Detecta marca (160+), peso, gera SEO
3. **Busca imagens** → Modo premium (Google + Vision) ou modo barato (DuckDuckGo/Bing)
4. **Upload FTP** → Envia imagens para Hostinger
5. **Exporta CSV WooCommerce** → Formato PT-BR com URLs públicas
6. **Dashboard Web** → Controle visual completo
7. **Bot Discord** → Comandos remotos

---

## 🚀 Fluxo de Produção

### Passo 1: Buscar Imagens

```powershell
# Definir encoding UTF-8 (Windows)
$env:PYTHONIOENCODING="utf-8"

# Rodar scraper (só produtos com estoque)
python scrape_all_images.py --stock-only

# Ou todos os produtos
python scrape_all_images.py

# Modo barato (DuckDuckGo/Bing, sem Vision/Google)
python scrape_all_images.py --search-mode cheap
# ou
python scrape_all_images.py --cheap

# Paralelismo (mais rápido no cheap)
python scrape_all_images.py --search-mode cheap --workers 4
```

**Opções:**
| Flag | Descrição |
|------|-----------|
| `--stock-only` | Só produtos com estoque > 0 |
| `--limit N` | Limitar a N produtos |
| `--reset` | Recomeçar do zero |
| `--search-mode premium|cheap` | Define modo de busca |
| `--cheap` | Atalho para modo barato |
| `--only-failed` | Reprocessa apenas SKUs com falha |
| `--only-missing-images` | Processa apenas SKUs sem imagem local |
| `--skip-existing` | Pula SKUs com imagem local (padrão) |
| `--no-skip-existing` | Processa mesmo com imagem local |
| `--workers N` | Número de workers em paralelo |

**Saídas:**

- `data/images/<categoria>/SKU.jpg` - Imagens 800x800 organizadas por categoria
- `data/scraper_progress.json` - Progresso
- `data/vision_cache.json` - Cache Vision AI
- `data/search_cache.json` - Cache de busca por SKU
- `data/reports/image_success_*.json` - Relatório de sucesso por categoria/marca

### Passo 1.5: Upload FTP para Servidor

```powershell
# Upload de todas imagens para Hostinger
python -c "from src.image_scraper import upload_images_ftp; upload_images_ftp()"
```

### Passo 2: Gerar CSV para WooCommerce

```powershell
# Modo FULL (nome, descrição, imagens, preço, estoque)
python main.py --input data/input/Athos.csv

# Modo LITE (só preço e estoque - preserva SEO manual)
python main.py --input data/input/Athos.csv --lite

# Modo TESTE (apenas PET, PESCA, AQUARISMO - importação rápida)
python main.py --input data/input/Athos.csv --teste
```

**Saídas:**

- `data/output/woocommerce_import_*.csv` - CSV para importar
- Coluna `Images` preenchida automaticamente se imagem existe
- `data/reports/weight_outliers_*.json` - Outliers de peso por categoria

### Passo 3: Importar no WooCommerce

1. WooCommerce → Produtos → Importar
2. Selecione o CSV gerado
3. Mapeie as colunas (automático se padrão)
4. Execute importação

### Passo 4: Excluir Antigos

Após importação bem-sucedida:

1. WooCommerce → Produtos → Filtrar por "Sem imagem"
2. Ações em lote → Mover para lixeira

---

## 📊 Estatísticas do Projeto

| Métrica                 | Valor  |
| ----------------------- | ------ |
| Produtos no ERP         | 4.352  |
| Excluídos (automático)  | ~390   |
| Válidos para e-commerce | ~3.962 |
| Departamentos           | 12     |
| Marcas detectadas       | 160+   |
| Imagens processadas     | 1.727  |
| Semânticas Vision AI    | 80+    |

### Exclusões Automáticas

| Categoria         | Motivo                       |
| ----------------- | ---------------------------- |
| FERRAMENTAS       | Pesado, frete caro           |
| INSUMO            | Sacos pesados                |
| Decoração aquário | Baixa margem, difícil imagem |
| Itens pequenos    | Anzol avulso, miçangas       |
| Perecíveis        | Isca viva                    |
| Bebidas           | Legislação, quebra           |
| Frágeis           | Aquário vidro, cerâmica      |
| Volumosos         | Bebedouro galinha, gaiola    |
| > 15kg            | Frete inviável               |

---

## 🖼️ Image Scraper v3

Sistema inteligente de busca de imagens:

### Modos de busca

- **Premium (padrão)**: Google Custom Search + Vision AI (melhor qualidade)
- **Cheap**: DuckDuckGo + Bing (sem custos de API)

### Funcionalidades (gerais)

- ✅ **Busca premium** - Google Custom Search + Vision AI
- ✅ **Busca barata** - DuckDuckGo + Bing (fallback)
- ✅ **Validação Semântica** - Labels devem corresponder ao produto
- ✅ **Cache de Vision AI** - Evita análises duplicadas
- ✅ **Cache por SKU** - Evita buscas repetidas
- ✅ **Relatório diário** - Sucesso por categoria/marca
- ✅ **Fallback de Busca** - 3 estratégias de query
- ✅ **Retry com Backoff** - Trata erros 429
- ✅ **Prioridade por Estoque** - Processa estoque > 0 primeiro
- ✅ **Skip de Existentes** - Zero custo se imagem já existe

### Thresholds de Score

| Departamento               | Score Mínimo |
| -------------------------- | ------------ |
| PET, RACAO, PESCA          | 0.45         |
| FARMACIA, GERAL, TABACARIA | 0.35         |
| AVES, CUTELARIA, PISCINA   | 0.35         |

### APIs Necessárias (.env)

```env
# Modo premium (necessário)
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=75f6d255f...
VISION_AI_ENABLED=true

# Modo barato (opcional)
IMAGE_SEARCH_MODE=cheap
```

### Controle de fontes (opcional)

Configure domínios permitidos/bloqueados por categoria em:

- `config/image_sources.json` (allowlist por categoria; limpe a allowlist se quiser mais liberdade)

### Outliers de peso (opcional)

Regras de alerta por categoria ficam em:

- `config/exclusion_list.json` → `weight_outlier_rules`

### Custo Estimado

| Cenário                   | Produtos | Custo   |
| ------------------------- | -------- | ------- |
| Premium (Vision + Google) | ~3.200   | ~R$ 86  |
| Premium (Vision + Google) | ~4.100   | ~R$ 112 |
| Cheap (DuckDuckGo/Bing)   | ~4.100   | ~R$ 0   |

_Premium baseado em Vision AI $1.50/1000 imagens_

---

## 🖥️ Dashboard Web

Interface visual completa:

```powershell
python -m uvicorn dashboard.app:app --host 0.0.0.0 --port 8080
```

### Endpoints API

| Endpoint                           | Descrição             |
| ---------------------------------- | --------------------- |
| `GET /`                            | Dashboard principal   |
| `GET /images`                      | Curadoria de imagens  |
| `GET /api/status`                  | Status do sync        |
| `GET /api/images/missing`          | Produtos sem imagem   |
| `GET /api/images/scraper-progress` | Progresso do scraper  |
| `POST /api/sync`                   | Iniciar sincronização |
| `GET /metrics`                     | Métricas Prometheus   |
| `GET /docs`                        | Swagger UI            |

---

## 🤖 Bot Discord

Controle remoto via Discord:

```powershell
python bot_control.py
```

### Comandos

| Comando   | Descrição             |
| --------- | --------------------- |
| `!status` | Status do sistema     |
| `!sync`   | Iniciar sincronização |
| `!ajuda`  | Lista de comandos     |

---

## 🐳 Deploy com Docker

```bash
# Build e start
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar
docker-compose down
```

Ver [DEPLOY.md](DEPLOY.md) para guia completo de deploy no servidor.

---

## 📁 Estrutura do Projeto

```
aquaflora-stock-sync/
├── main.py                 # CLI principal
├── scrape_all_images.py    # Image scraper v3
├── bot_control.py          # Bot Discord
├── config/
│   ├── settings.py         # Configurações (.env)
│   ├── brands.json         # Marcas detectadas
│   └── exclusion_list.json # Exclusões para e-commerce
├── src/
│   ├── parser.py           # Parser CSV Athos
│   ├── enricher.py         # Enriquecimento de produtos
│   ├── database.py         # SQLite + histórico
│   ├── sync.py             # API WooCommerce
│   ├── image_scraper.py    # Google + Vision AI
│   ├── models.py           # Modelos Pydantic
│   └── notifications.py    # Discord/Telegram
├── dashboard/
│   ├── app.py              # FastAPI + HTMX
│   └── templates/          # HTML Jinja2
├── data/
│   ├── input/              # CSVs do ERP
│   ├── output/             # CSVs para WooCommerce
│   └── images/             # Imagens scraped (por categoria)
├── logs/                   # Logs rotativos
└── tests/                  # Testes pytest
```

---

## ⚙️ Configuração (.env)

```env
# WooCommerce
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# Google APIs (modo premium)
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=75f6d255f...
VISION_AI_ENABLED=true

# Modo barato (opcional)
IMAGE_SEARCH_MODE=cheap

# Discord (opcional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=MTI...

# Segurança
PRICE_GUARD_MAX_VARIATION=40
DRY_RUN=false
```

---

## 🧪 Testes

```powershell
# Rodar todos
pytest

# Com coverage
pytest --cov=src --cov-report=html
```

---

## 📝 Licença

Projeto privado - AquaFlora Agroshop © 2026
