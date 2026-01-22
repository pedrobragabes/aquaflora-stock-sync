# 📋 Contexto Técnico - AquaFlora Stock Sync v3.2

> **Documento de referência para desenvolvimento e manutenção**  
> Última atualização: 22 Janeiro 2026

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

---

## 📊 Números do Projeto

| Métrica               | Valor  |
| --------------------- | ------ |
| Produtos no ERP       | 4.074+ |
| Departamentos         | 12     |
| Marcas detectadas     | 160+   |
| Semânticas Vision AI  | 80+    |
| Imagens consolidadas  | 3.206  |
| - WooCommerce (base)  | 1.967  |
| - Scraper (novidades) | 1.239  |
| Cobertura de imagens  | 76%    |

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
| `dashboard/app.py`     | FastAPI + HTMX                        |

### Módulos src/

| Módulo             | Responsabilidade              |
| ------------------ | ----------------------------- |
| `parser.py`        | Lê CSV "sujo" do ERP Athos    |
| `enricher.py`      | Detecta marca, peso, gera SEO |
| `database.py`      | SQLite + histórico de preços  |
| `sync.py`          | API WooCommerce + PriceGuard  |
| `image_scraper.py` | Google Search + Vision AI     |
| `models.py`        | Pydantic models + hashes      |
| `notifications.py` | Discord/Telegram webhooks     |
| `exceptions.py`    | Exceções customizadas         |

### Configurações config/

| Arquivo               | Conteúdo                            |
| --------------------- | ----------------------------------- |
| `settings.py`         | Pydantic Settings (carrega .env)    |
| `brands.json`         | Lista de 160+ marcas                |
| `exclusion_list.json` | Exclusões completas para e-commerce |

### Scripts Utilitários (scripts/)

| Script                           | Função                                     |
| -------------------------------- | ------------------------------------------ |
| `organize_images.py`             | Organiza imagens do scraper por categoria  |
| `organize_woocommerce_images.py` | Organiza imagens exportadas do WooCommerce |
| `consolidate_images.py`          | Unifica imagens WC + scraper em uma pasta  |
| `compare_images.py`              | Compara SKUs entre pastas de imagens       |
| `analyze_departments.py`         | Analisa departamentos do ERP               |
| `analyze_missing_images.py`      | Lista produtos sem imagem                  |
| `test_image_scraper.py`          | Testa scraper em produtos específicos      |

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
- farmacia, aves, piscina, cutelaria, tabacaria, geral

### 4. Image Scraper (scrape_all_images.py)

**Modos de busca:**

- **Premium:** Google Custom Search + Vision AI (validação semântica)
- **Cheap:** DuckDuckGo + Bing (fallback, sem validação AI)

**Features:**

- Progresso salvo automaticamente (retomável)
- Cache de buscas por SKU
- Cache de Vision AI
- Paralelismo configurável (--workers)
- Organização automática por categoria

### 5. CSV Export (main.py)

**Modos:**

- **FULL:** Nome, descrição, imagens, preço, estoque, peso, marca
- **LITE:** Só preço e estoque (preserva SEO manual)
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
├── geral/          # Outros
└── sem_categoria/  # Fallback
```

### Nomenclatura

Arquivos seguem padrão: `{SKU}.{extensão}`

- SKU pode ser código interno ou EAN
- Extensão detectada automaticamente

### Consolidação

O script `scripts/consolidate_images.py` unifica:

1. **Base:** Imagens do WooCommerce (exportação)
2. **Novidades:** Imagens do scraper (apenas SKUs não existentes)

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
```

---

## 📈 Métricas de Qualidade

### Cobertura de Imagens

- Total de produtos: 4.074
- Com imagem: 3.101 (76%)
- Sem imagem: 973 (24%)

### Fontes de Imagens

- WooCommerce (exportação): 1.967 (61%)
- Scraper (novidades): 1.239 (39%)

### Extensões

- WEBP: maioria das imagens WooCommerce
- JPG: maioria das imagens scraper
- PNG, AVIF, GIF: algumas

---

## 🚀 Próximos Passos

1. **Automatização 24h:** Cron job ou Windows Task Scheduler
2. **Dashboard aprimorado:** Mais estatísticas, gráficos
3. **Scraper incremental:** Só produtos novos/alterados
4. **Backup automático:** Antes de cada sync

---

## 📝 Histórico de Versões

| Versão | Data       | Mudanças                                                           |
| ------ | ---------- | ------------------------------------------------------------------ |
| 3.2    | 22/01/2026 | Consolidação de imagens, multi-extensão, organização por categoria |
| 3.1    | 21/01/2026 | Modo cheap melhorado (DDGS API fix), queries de pesca              |
| 3.0    | 19/01/2026 | Dashboard HTMX, scraper v3, Vision AI                              |
| 2.0    | 15/01/2026 | Bot Discord, notificações                                          |
| 1.0    | 10/01/2026 | Versão inicial                                                     |
