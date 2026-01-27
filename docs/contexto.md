# 📋 Contexto Técnico - AquaFlora Stock Sync v3.3

> **Documento de referência para desenvolvimento e manutenção**  
> Última atualização: 27 Janeiro 2026

---

## 🎯 Visão Geral

**AquaFlora Stock Sync** é um sistema completo de e-commerce que:

1. Importa dados do ERP Athos (CSV)
2. Enriquece com marca, peso, SEO
3. Busca imagens automaticamente (premium Google + Vision ou cheap DuckDuckGo/Bing)
4. Organiza imagens por categoria
5. Faz upload FTP para Hostinger
6. Gera CSV para importação no WooCommerce
7. Fornece dashboard web e bot Discord
8. **Analisa gaps de cobertura de imagens** (novo em v3.3)

---

## 📊 Números do Projeto

| Métrica              | Valor |
| -------------------- | ----- |
| Produtos no ERP      | 4.352 |
| Departamentos        | 12    |
| Marcas detectadas    | 160+  |
| Semânticas Vision AI | 80+   |
| Imagens no disco     | 2.988 |
| Cobertura de imagens | 68.7% |
| Produtos sem imagem  | 318   |

### Cobertura por Departamento (27/01/2026)

| Departamento | Cobertura | Faltando |
| ------------ | --------- | -------- |
| FARMACIA     | 99.4%     | 3        |
| AQUARISMO    | 99.6%     | 1        |
| GERAL        | 97.2%     | 15       |
| PET          | 94.4%     | 54       |
| PESCA        | 93.1%     | 85       |
| TABACARIA    | 90.9%     | 8        |
| RACAO        | 84.5%     | 29       |
| INSUMO       | 79.2%     | 15       |
| FERRAMENTAS  | 11.5%     | 108      |

---

## 🏗️ Arquitetura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ERP Athos     │────▶│   AthosParser   │────▶│ ProductEnricher │
│   (CSV)         │     │   (parser.py)   │     │  (enricher.py)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│   WooCommerce   │◀────│  CSV Export     │◀─────────────┘
│   (Import CSV)  │     │   (main.py)     │
└─────────────────┘     └─────────────────┘
         ▲                      ▲
         │                      │
┌─────────────────┐     ┌─────────────────┐
│   FTP Upload    │     │  Image Finder   │
│   (Hostinger)   │     │ (multi-format)  │
└─────────────────┘     └─────────────────┘
         ▲                      ▲
         │                      │
┌─────────────────────────────────────────┐
│        data/images/{categoria}/         │
│   (pesca, pet, aquarismo, farmacia...)  │
└─────────────────────────────────────────┘
         ▲
         │
┌─────────────────┐     ┌─────────────────┐
│  Image Scraper  │────▶│ Vision AI (opt) │
│ (DuckDuckGo/    │     │ (validação)     │
│  Bing/Google)   │     │                 │
└─────────────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│ Analyze Missing │ ◀── analyze_missing_products.py
│   (Reports)     │
└─────────────────┘
```

---

## 📁 Estrutura de Arquivos

### Arquivos Principais

| Arquivo                | Função                                |
| ---------------------- | ------------------------------------- |
| `main.py`              | CLI principal, orquestra todo o fluxo |
| `scrape_all_images.py` | Scraper de imagens v3                 |
| `upload_images.py`     | Upload FTP para servidor              |
| `bot_control.py`       | Bot Discord 2.0                       |
| `tasks.ps1`            | Comandos PowerShell rápidos           |
| `Makefile`             | Comandos Make                         |
| `dashboard/app.py`     | FastAPI + HTMX                        |

### Módulos src/

| Módulo             | Responsabilidade              |
| ------------------ | ----------------------------- |
| `parser.py`        | Lê CSV "sujo" do ERP Athos    |
| `enricher.py`      | Detecta marca, peso, gera SEO |
| `database.py`      | SQLite + histórico de preços  |
| `sync.py`          | API WooCommerce + PriceGuard  |
| `image_scraper.py` | Google Search + Vision AI     |
| `image_curator.py` | Curadoria e validação         |
| `models.py`        | Pydantic models + hashes      |
| `notifications.py` | Discord webhooks              |
| `backup.py`        | Backup do banco de dados      |
| `exceptions.py`    | Exceções customizadas         |

### Configurações config/

| Arquivo               | Conteúdo                            |
| --------------------- | ----------------------------------- |
| `settings.py`         | Pydantic Settings (carrega .env)    |
| `brands.json`         | Lista de 160+ marcas                |
| `exclusion_list.json` | Exclusões completas para e-commerce |
| `image_sources.json`  | Regras de fontes de imagem          |

### Scripts Utilitários (scripts/)

| Script                                | Função                                     |
| ------------------------------------- | ------------------------------------------ |
| `analyze_missing_products.py`         | Análise de gaps de imagens                 |
| `delete_products_by_sku.py`           | Deletar produtos do WooCommerce            |
| `remove_excluded_from_woocommerce.py` | Remove produtos excluídos do WC            |
| `update_woo_image_urls.py`            | Atualiza URLs de imagens no WC             |
| `upload_images_ftp.py`                | Upload FTP alternativo                     |
| `upload_images_to_woocommerce.py`     | Upload direto para WooCommerce             |
| `run_scraper_background.ps1`          | Script PowerShell para rodar em background |
| `.old/`                               | Scripts obsoletos arquivados               |

---

## 🔧 Componentes Detalhados

### 1. AthosParser (parser.py)

**Problema:** ERP exporta CSV "relatório" com lixo (headers empresa, paginação, totais).

**Solução:**

- Detecta formato automaticamente (limpo vs sujo)
- Remove linhas de garbage
- Extrai departamento de linhas "Departamento: XXX"
- Normaliza encoding (UTF-8 + ftfy)

**Campos extraídos:**

```python
RawProduct:
  - sku: str           # Código interno ou EAN
  - name: str          # Descrição
  - stock: float       # Estoque
  - price: float       # Preço venda
  - cost: float        # Custo
  - department: str    # Departamento
  - ean: str           # Código de barras
  - brand: str         # Marca
```

### 2. ProductEnricher (enricher.py)

**Funcionalidades:**

- Detecta marca em 160+ padrões
- Extrai peso do nome (500g, 1kg, 1,5L)
- Extrai peso avançado (2x10kg, 15kg c/2, 10kg + 2kg)
- Gera categoria WooCommerce
- Cria descrição SEO em HTML
- Cria short_description

### 3. Image Finder (main.py)

**Funcionalidade:** Busca imagens locais para cada produto.

**Algoritmo:**

1. Tenta `data/images/{categoria}/{sku}.{ext}` (extensões: jpg, jpeg, png, webp, avif, gif)
2. Fallback: busca recursiva em `data/images/**/{sku}.{ext}`
3. Prioridade de extensões: jpg > jpeg > png > webp > avif > gif

**Categorias suportadas:**

- pesca, pet, aquarismo, passaros, racao
- farmacia, aves, piscina, cutelaria, tabacaria
- ferramentas, insumo, geral

### 4. Image Scraper (scrape_all_images.py)

**Modos de busca:**

- **Premium:** Google Custom Search + Vision AI (validação semântica)
- **Cheap:** DuckDuckGo + Bing (fallback, sem validação AI)

**Features v3:**

- Progresso salvo automaticamente (retomável)
- Cache de buscas por SKU
- Cache de Vision AI
- Paralelismo configurável (--workers)
- Organização automática por categoria
- Flag `--only-missing-images` para processar apenas gaps
- Relatórios de sucesso por departamento/marca
- Timeout por produto para evitar travamentos

### 5. Analyze Missing Products (analyze_missing_products.py) - NOVO!

**Funcionalidade:** Análise completa de gaps de cobertura.

**Saída:**

- Estatísticas gerais
- Cobertura por departamento
- Cobertura por marca
- Produtos que falharam no scraper
- Recomendações de exclusão
- Relatório JSON detalhado

### 6. CSV Export (main.py)

**Modos:**

- **FULL:** Nome, descrição, imagens, preço, estoque, peso, marca
- **LITE:** Só preço e estoque (preserva SEO manual)
- **LITE-IMAGES:** Preço, estoque e imagens
- **TESTE:** Só categorias PET, PESCA, AQUARISMO

**Campos WooCommerce:**

```
SKU, Name, Description, Short description, Regular price,
Stock, Categories, Images, Weight (kg), Brands,
Tax status, In stock?, Published, Visibility
```

---

## 🖼️ Sistema de Imagens

### Organização

```
data/images/
├── pesca/          # GERAL PESCA, PESCA
├── pet/            # PET
├── aquarismo/      # AQUARISMO
├── passaros/       # PÁSSAROS
├── racao/          # RAÇÃO
├── farmacia/       # FARMÁCIA
├── aves/           # AVES
├── piscina/        # PISCINA
├── cutelaria/      # CUTELARIA
├── tabacaria/      # TABACARIA
├── ferramentas/    # FERRAMENTAS
├── insumo/         # INSUMO
├── geral/          # Outros
└── sem_categoria/  # Fallback
```

### Nomenclatura

Arquivos seguem padrão: `{SKU}.{extensão}`

- SKU pode ser código interno ou EAN
- Extensão detectada automaticamente

### Arquivos de Cache e Progresso

| Arquivo                             | Descrição                     |
| ----------------------------------- | ----------------------------- |
| `data/scraper_progress.json`        | Progresso do scraper          |
| `data/vision_cache.json`            | Cache Vision AI               |
| `data/search_cache.json`            | Cache de buscas               |
| `data/missing_products_report.json` | Análise de produtos           |
| `data/reports/*.json`               | Relatórios de sucesso diários |

---

## ⚙️ Configurações (.env)

```env
# === WooCommerce ===
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# === FTP/Imagens ===
IMAGE_BASE_URL=https://sualoja.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=sualoja.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha

# === Google APIs ===
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=xxx
VISION_AI_ENABLED=true

# === Discord ===
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# === Operação ===
DRY_RUN=false
SYNC_ENABLED=true

# === Scraper ===
IMAGE_SEARCH_MODE=cheap
SCRAPER_CHEAP_WORKERS=4
SCRAPER_PREMIUM_WORKERS=1
```

---

## 📈 Métricas de Qualidade

### Cobertura de Imagens (27/01/2026)

- Total de produtos: 4.352
- Com imagem: 2.988 (68.7%)
- Sem imagem: 318 (7.3%)
- Em progresso/falha: ~1.046

### Status do Scraper

- Completados: 2.535
- Falhados: 285
- Excluídos: 157
- Reutilizados: 2

### Extensões

- JPG: maioria das imagens scraper
- WEBP: maioria das imagens WooCommerce
- PNG, AVIF, GIF: algumas

---

## 🚀 Próximos Passos

1. **Melhorar FERRAMENTAS:** Cobertura atual de apenas 11.5%
2. **Automatização 24h:** Cron job ou Windows Task Scheduler
3. **Dashboard aprimorado:** Mais estatísticas, gráficos
4. **Scraper incremental:** Só produtos novos/alterados
5. **Backup automático:** Antes de cada sync

---

## 📝 Histórico de Versões

| Versão | Data       | Mudanças                                                           |
| ------ | ---------- | ------------------------------------------------------------------ |
| 3.3    | 27/01/2026 | Análise de gaps, --only-missing-images, relatórios de sucesso      |
| 3.2    | 22/01/2026 | Consolidação de imagens, multi-extensão, organização por categoria |
| 3.1    | 21/01/2026 | Modo cheap melhorado (DDGS API fix), queries de pesca              |
| 3.0    | 19/01/2026 | Dashboard HTMX, scraper v3, Vision AI                              |
| 2.0    | 15/01/2026 | Bot Discord, notificações                                          |
| 1.0    | 10/01/2026 | Versão inicial                                                     |
