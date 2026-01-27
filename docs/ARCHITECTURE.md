# 🏗️ Arquitetura do Sistema - AquaFlora Stock Sync

> **Documentação técnica da arquitetura**  
> Versão: 3.3 | Atualização: 27 Janeiro 2026

---

## 📊 Visão Geral

O AquaFlora Stock Sync é um sistema de ETL (Extract, Transform, Load) especializado para e-commerce, que:

1. **Extract:** Lê dados do ERP Athos (CSV)
2. **Transform:** Enriquece com marca, peso, SEO, imagens
3. **Load:** Gera CSV para importação no WooCommerce
4. **Analyze:** Monitora cobertura de imagens e gaps

---

## 🔄 Fluxo de Dados

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTRADA (Extract)                        │
├─────────────────────────────────────────────────────────────────┤
│  ERP Athos → CSV → AthosParser → RawProduct[]                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSAMENTO (Transform)                    │
├─────────────────────────────────────────────────────────────────┤
│  RawProduct → ProductEnricher → EnrichedProduct                │
│    ├── Detecção de marca (160+ padrões)                        │
│    ├── Extração de peso                                         │
│    ├── Geração de SEO (descrição, short_description)           │
│    ├── Categorização WooCommerce                                │
│    └── Busca de imagem local                                    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        SAÍDA (Load)                             │
├─────────────────────────────────────────────────────────────────┤
│  EnrichedProduct → CSV Export → WooCommerce Import             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ANÁLISE (Monitor)                          │
├─────────────────────────────────────────────────────────────────┤
│  analyze_missing_products.py → Relatórios de gaps              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧩 Componentes Principais

### 1. AthosParser (`src/parser.py`)

**Responsabilidade:** Ler e normalizar CSV do ERP Athos.

**Problema resolvido:** O ERP exporta CSVs "sujos" com:

- Headers de empresa/relatório
- Paginação (quebras de página)
- Totais e subtotais
- Encoding inconsistente

**Solução:**

```python
class AthosParser:
    def parse(self, filepath: str) -> List[RawProduct]:
        # 1. Detecta formato (limpo vs sujo)
        # 2. Remove linhas de garbage
        # 3. Extrai departamento de "Departamento: XXX"
        # 4. Normaliza encoding (UTF-8 + ftfy)
        # 5. Retorna lista de RawProduct
```

**Saída:**

```python
@dataclass
class RawProduct:
    sku: str        # Código ou EAN
    name: str       # Descrição original
    stock: float    # Estoque
    price: float    # Preço venda
    cost: float     # Custo
    department: str # Departamento
    ean: str        # Código de barras
    brand: str      # Marca (se existir no ERP)
```

---

### 2. ProductEnricher (`src/enricher.py`)

**Responsabilidade:** Enriquecer produtos com dados derivados.

**Funcionalidades:**

| Feature           | Descrição                                       |
| ----------------- | ----------------------------------------------- |
| Detecção de marca | 160+ padrões em `config/brands.json`            |
| Extração de peso  | Regex para "500g", "1kg", "1,5L"                |
| Peso avançado     | "2x10kg", "15kg c/2", "10kg + 2kg"              |
| Categorização     | Mapeamento departamento → categoria WooCommerce |
| Descrição SEO     | HTML com detalhes do produto                    |
| Short description | Resumo de 1-2 linhas                            |

**Algoritmo de detecção de marca:**

```python
def detect_brand(name: str) -> Optional[str]:
    # 1. Busca exata no início do nome
    # 2. Busca em qualquer posição
    # 3. Busca com variações (acentos, case)
    # 4. Retorna primeira match ou None
```

---

### 3. Image Finder (`main.py`)

**Responsabilidade:** Localizar imagens para cada produto.

**Algoritmo:**

```python
def _find_image_path(sku: str, category: str) -> Optional[Path]:
    # Extensões suportadas (ordem de prioridade)
    EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif']

    # 1. Tentar caminho direto: data/images/{categoria}/{sku}.{ext}
    for ext in EXTENSIONS:
        path = images_dir / category / f"{sku}{ext}"
        if path.exists():
            return path

    # 2. Fallback: busca recursiva em todas as pastas
    for ext in EXTENSIONS:
        matches = list(images_dir.rglob(f"{sku}{ext}"))
        if matches:
            return matches[0]

    return None
```

**Mapeamento de categorias:**

```python
CATEGORY_FOLDERS = {
    'GERAL PESCA': 'pesca',
    'PESCA': 'pesca',
    'PET': 'pet',
    'AQUARISMO': 'aquarismo',
    'PÁSSAROS': 'passaros',
    'RAÇÃO': 'racao',
    'FARMÁCIA': 'farmacia',
    'AVES': 'aves',
    'PISCINA': 'piscina',
    'CUTELARIA': 'cutelaria',
    'TABACARIA': 'tabacaria',
    'FERRAMENTAS': 'ferramentas',
    'INSUMO': 'insumo',
}
```

---

### 4. Image Scraper (`scrape_all_images.py`)

**Responsabilidade:** Buscar imagens automaticamente na internet.

**Modos de operação:**

| Modo    | APIs                             | Validação       | Velocidade |
| ------- | -------------------------------- | --------------- | ---------- |
| Premium | Google Custom Search + Vision AI | Semântica       | Lenta      |
| Cheap   | DuckDuckGo + Bing                | Tamanho/formato | Rápida     |

**Fluxo Premium:**

```
Query → Google Search → URLs → Download → Vision AI → Validação → Salvar
```

**Fluxo Cheap:**

```
Query → DuckDuckGo → URLs (ou Bing fallback) → Download → Validar tamanho → Salvar
```

**Features v3.3:**

- `--only-missing-images`: processa apenas SKUs sem imagem local
- Timeout por produto (60s) para evitar travamentos
- Relatórios de sucesso por departamento/marca
- Métricas de cobertura em tempo real

---

### 5. Analyze Missing Products (`analyze_missing_products.py`) - NOVO!

**Responsabilidade:** Analisar gaps de cobertura de imagens.

**Funcionalidades:**

```python
def analyze_missing():
    # 1. Carrega produtos do CSV
    # 2. Carrega progresso do scraper
    # 3. Encontra imagens existentes no disco
    # 4. Calcula cobertura por departamento
    # 5. Calcula cobertura por marca
    # 6. Identifica produtos que falharam
    # 7. Gera recomendações de exclusão
    # 8. Salva relatório JSON detalhado
```

**Saída:**

```
📊 ESTATÍSTICAS GERAIS:
  Total produtos no CSV: 4352
  Imagens encontradas no disco: 2988
  Cobertura atual: 68.7%

📦 POR DEPARTAMENTO:
  FERRAMENTAS: 11.5% cobertura (108 faltando)
  PESCA: 93.1% cobertura (85 faltando)
  ...
```

---

### 6. CSV Export (`main.py`)

**Responsabilidade:** Gerar CSV compatível com WooCommerce.

**Campos exportados:**

```python
CSV_FIELDS = [
    'ID',
    'Type',
    'SKU',
    'Name',
    'Published',
    'Visibility',
    'Short description',
    'Description',
    'Tax status',
    'In stock?',
    'Stock',
    'Regular price',
    'Categories',
    'Images',
    'Weight (kg)',
    'Brands',
]
```

**Modos:**

- **FULL:** Todos os campos
- **LITE:** Só SKU, Stock, Regular price (preserva SEO manual)
- **LITE-IMAGES:** SKU, Stock, Regular price, Images
- **TESTE:** Só categorias PET, PESCA, AQUARISMO

---

## 📁 Estrutura de Diretórios

```
aquaflora-stock-sync/
├── main.py                      # Orquestrador principal
├── scrape_all_images.py         # Scraper de imagens v3
├── analyze_missing_products.py  # Análise de gaps (NOVO)
├── upload_images.py             # Upload FTP
├── bot_control.py               # Bot Discord
│
├── config/
│   ├── settings.py              # Pydantic Settings (.env)
│   ├── brands.json              # 160+ marcas
│   ├── exclusion_list.json      # Produtos excluídos
│   └── image_sources.json       # Regras de fontes
│
├── src/
│   ├── parser.py                # Parser CSV Athos
│   ├── enricher.py              # Enriquecimento
│   ├── image_scraper.py         # Core do scraper
│   ├── image_curator.py         # Curadoria de imagens
│   ├── database.py              # SQLite wrapper
│   ├── sync.py                  # API WooCommerce
│   ├── models.py                # Pydantic models
│   ├── notifications.py         # Discord webhooks
│   ├── backup.py                # Backup do banco
│   └── exceptions.py            # Exceções custom
│
├── dashboard/
│   ├── app.py                   # FastAPI + HTMX
│   ├── static/                  # CSS, JS
│   └── templates/               # Jinja2 templates
│
├── scripts/
│   ├── organize_images.py       # Organização scraper
│   ├── consolidate_images.py    # Unificação
│   ├── compare_images.py        # Comparação
│   ├── analyze_*.py             # Análises
│   └── upload_*.py              # Uploads
│
├── data/
│   ├── input/                   # CSVs do ERP
│   ├── output/                  # CSVs gerados
│   ├── reports/                 # Relatórios de sucesso
│   └── images/                  # Imagens organizadas
│       ├── pesca/
│       ├── pet/
│       ├── ferramentas/
│       └── ...
│
└── logs/                        # Logs do sistema
```

---

## 🔧 Configurações

### Variáveis de Ambiente (.env)

```env
# WooCommerce API
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# FTP para imagens
IMAGE_BASE_URL=https://sualoja.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=sualoja.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha

# Google APIs
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=xxx
VISION_AI_ENABLED=true

# Notificações
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Operação
DRY_RUN=false
SYNC_ENABLED=true

# Scraper
IMAGE_SEARCH_MODE=cheap
SCRAPER_CHEAP_WORKERS=4
SCRAPER_PREMIUM_WORKERS=1
```

### Configuração de Marcas (brands.json)

```json
{
  "brands": [
    "Alcon",
    "Sera",
    "Tetra",
    "JBL",
    "Marine Sports",
    ...
  ]
}
```

### Lista de Exclusão (exclusion_list.json)

```json
{
  "exclude_departments": ["FERRAMENTAS"],
  "exclude_keywords": {
    "generic": ["KIT", "COMBO", "PACOTE"]
  },
  "patterns": ["FRETE", "DESCONTO", "CONSERTO", "VALE PRESENTE"],
  "skus": ["9999", "0000"]
}
```

---

## 🔄 Ciclo de Vida

### Execução Típica

```
1. Análise de Gaps (analyze_missing_products.py)
   └── Identificar 318 produtos sem imagem

2. Scraping de Imagens (scrape_all_images.py --only-missing-images)
   └── Buscar imagens para produtos faltantes

3. Carga do CSV (AthosParser)
   └── 4.352 produtos parseados

4. Enriquecimento (ProductEnricher)
   ├── 160+ marcas detectadas
   ├── Peso extraído
   └── SEO gerado

5. Busca de Imagens (Image Finder)
   └── 2.988 imagens encontradas (68.7%)

6. Exportação CSV
   └── woocommerce_import_*.csv

7. Notificação Discord
   └── Relatório enviado
```

### Estados do Scraper

```
┌──────────┐     ┌───────────┐     ┌───────────┐
│ pending  │────▶│ searching │────▶│ completed │
└──────────┘     └───────────┘     └───────────┘
                       │
                       ▼
                 ┌───────────┐
                 │  failed   │
                 └───────────┘
                       │
                       ▼
                 ┌───────────┐
                 │  timeout  │ (novo em v3.3)
                 └───────────┘
```

---

## 📈 Métricas

### Performance

| Operação                | Tempo médio |
| ----------------------- | ----------- |
| Parse CSV (4K produtos) | ~2s         |
| Enriquecimento          | ~5s         |
| Busca de imagens        | ~30s        |
| Export CSV              | ~1s         |
| Análise de gaps         | ~3s         |

### Cobertura (27/01/2026)

| Métrica              | Valor  |
| -------------------- | ------ |
| Produtos processados | 4.352  |
| Com marca detectada  | ~85%   |
| Com peso extraído    | ~70%   |
| Com imagem           | 68.7%  |

---

## 🛡️ Tratamento de Erros

### Níveis de Log

```python
# logging_config.py
LEVELS = {
    'DEBUG': 'Detalhes técnicos',
    'INFO': 'Operações normais',
    'WARNING': 'Situações inesperadas',
    'ERROR': 'Falhas recuperáveis',
    'CRITICAL': 'Falhas fatais'
}
```

### Retry Strategy

```python
# Para APIs externas
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    retry=retry_if_exception_type(RequestException)
)
def fetch_image(url: str) -> bytes:
    ...
```

### Timeout por Produto

```python
# scrape_all_images.py
PRODUCT_TIMEOUT = 60  # Max seconds per product
```

---

## 🔮 Extensibilidade

### Adicionar Nova Marca

1. Editar `config/brands.json`
2. Adicionar nome da marca ao array
3. Reiniciar aplicação

### Adicionar Novo Departamento

1. Editar `src/enricher.py`
2. Adicionar mapeamento em `DEPARTMENT_CATEGORY_MAP`
3. Criar pasta em `data/images/{nova_categoria}/`
4. Atualizar `category_to_folder()` em `src/image_scraper.py`

### Adicionar Nova Fonte de Imagens

1. Implementar interface em `src/image_scraper.py`
2. Adicionar ao fluxo de busca em `search_with_fallback()`
3. Testar com `scripts/test_image_scraper.py`
