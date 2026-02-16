# 🏗️ Arquitetura do Sistema - AquaFlora Stock Sync v4.0

> **Documentação técnica da arquitetura**
> Última atualização: 16 Fevereiro 2026

---

## 📊 Visão Geral

Sistema ETL (Extract, Transform, Load) para e-commerce:

1. **Extract:** Lê CSV do ERP Athos
2. **Transform:** Enriquece com marca, peso, SEO, imagens
3. **Load:** Gera CSV para WooCommerce

---

## 🔄 Fluxo de Dados

```
┌─────────────────────────────────────────────────────────┐
│                    ENTRADA (Extract)                     │
│  ERP Athos → CSV → AthosParser → RawProduct[]           │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│                 PROCESSAMENTO (Transform)                │
│  RawProduct → ProductEnricher → EnrichedProduct          │
│    ├── Detecção de marca (160+ padrões)                  │
│    ├── Extração de peso                                  │
│    ├── Geração de SEO                                    │
│    ├── Categorização WooCommerce                         │
│    └── Busca de imagem local                             │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     SAÍDA (Load)                         │
│  EnrichedProduct → CSV Export → WooCommerce Import       │
│  Modos: FULL | LITE (só preço/estoque) | LITE-IMAGES     │
└─────────────────────────────────────────────────────────┘
```

---

## 🧩 Componentes

### 1. AthosParser (`src/parser.py`)

Lê e normaliza CSV "sujo" do ERP:
- Detecta formato (limpo vs sujo)
- Remove linhas de garbage (headers, paginação, totais)
- Extrai departamento de linhas "Departamento: XXX"
- Normaliza encoding (UTF-8 + ftfy)

**Saída:** `RawProduct` (sku, name, stock, price, cost, department, ean, brand)

### 2. ProductEnricher (`src/enricher.py`)

Enriquece com dados derivados:
- Detecção de marca (160+ padrões em `config/brands.json`)
- Extração de peso (500g, 1kg, 2x10kg, 15kg c/2)
- Categorização WooCommerce
- Descrição SEO em HTML

### 3. Image Finder (`main.py`)

Localiza imagens locais:
1. `data/images/{categoria}/{sku}.{ext}` (jpg > jpeg > png > webp > avif > gif)
2. Fallback: busca recursiva em `data/images/**/{sku}.{ext}`

### 4. Image Scraper (`scrape_all_images.py`)

Busca imagens na internet:

| Modo | APIs | Validação |
|------|------|-----------|
| Premium | Google Custom Search + Vision AI | Semântica |
| Cheap | DuckDuckGo + Bing | Tamanho/formato |

Features: progresso retomável, cache de buscas, paralelismo, `--only-missing-images`.

### 5. CSV Export (`main.py`)

Campos: SKU, Name, Description, Short description, Regular price, Stock, Categories, Images, Weight (kg), Brands, Tax status, In stock?, Published, Visibility.

Modos: FULL | LITE | LITE-IMAGES | TESTE

---

## 📁 Estrutura

```
aquaflora-stock-sync/
├── main.py                    # Orquestrador principal
├── scrape_all_images.py       # Scraper de imagens
├── upload_images.py           # Upload FTP
├── bot_control.py             # Bot Discord
│
├── config/                    # Configurações
│   ├── settings.py            # Pydantic Settings (.env)
│   ├── brands.json            # 160+ marcas
│   ├── exclusion_list.json    # Exclusões
│   └── image_sources.json     # Regras de fontes
│
├── src/                       # Módulos
│   ├── parser.py
│   ├── enricher.py
│   ├── database.py
│   ├── sync.py
│   ├── image_scraper.py
│   ├── image_curator.py
│   ├── models.py
│   ├── notifications.py
│   ├── backup.py
│   ├── logging_config.py
│   └── exceptions.py
│
├── scripts/                   # Utilitários
├── dashboard/                 # Web UI
├── tests/                     # Testes
├── data/                      # Dados (input/output/images/reports)
└── logs/                      # Logs
```

---

## ⚙️ Configurações (.env)

```env
WOO_URL, WOO_CONSUMER_KEY, WOO_CONSUMER_SECRET  # WooCommerce
IMAGE_BASE_URL, IMAGE_FTP_HOST/USER/PASSWORD      # FTP
GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID           # Google APIs (opcional)
DISCORD_WEBHOOK_URL                                # Notificações
DRY_RUN, SYNC_ENABLED                             # Operação
IMAGE_SEARCH_MODE, SCRAPER_CHEAP/PREMIUM_WORKERS  # Scraper
```

---

## 🔮 Extensibilidade

- **Nova marca:** Editar `config/brands.json`
- **Novo departamento:** Editar mapeamento em `src/enricher.py` + criar pasta em `data/images/`
- **Nova fonte de imagens:** Implementar em `src/image_scraper.py`
