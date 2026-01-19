# 📋 Contexto Técnico - AquaFlora Stock Sync v3.0

> **Documento de referência para desenvolvimento e manutenção**  
> Última atualização: 19 Janeiro 2026

---

## 🎯 Visão Geral

**AquaFlora Stock Sync** é um sistema completo de e-commerce que:

1. Importa dados do ERP Athos (CSV)
2. Enriquece com marca, peso, SEO
3. Busca imagens automaticamente (Google + Vision AI)
4. Sincroniza com WooCommerce
5. Fornece dashboard web e bot Discord

---

## 📊 Números do Projeto

| Métrica                     | Valor  |
| --------------------------- | ------ |
| Produtos no ERP             | 4.352  |
| Departamentos               | 12     |
| Marcas detectadas           | 160+   |
| Semânticas Vision AI        | 80+    |
| Produtos válidos e-commerce | ~2.700 |
| Excluídos (automático)      | ~300   |

---

## 🏗️ Arquitetura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ERP Athos     │────▶│   AthosParser   │────▶│ ProductEnricher │
│   (CSV)         │     │   (parser.py)   │     │  (enricher.py)  │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│   WooCommerce   │◀────│  WooSyncManager │◀─────────────┘
│   (API REST)    │     │   (sync.py)     │
└─────────────────┘     └─────────────────┘
         ▲
         │
┌────────┴────────┐     ┌─────────────────┐
│  Image Scraper  │────▶│   Vision AI     │
│ (scrape_all_images)   │ (image_scraper) │
└─────────────────┘     └─────────────────┘
```

---

## 📁 Estrutura de Arquivos

### Arquivos Principais

| Arquivo                | Função                                |
| ---------------------- | ------------------------------------- |
| `main.py`              | CLI principal, orquestra todo o fluxo |
| `scrape_all_images.py` | Scraper de imagens v3                 |
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

| Arquivo               | Conteúdo                         |
| --------------------- | -------------------------------- |
| `settings.py`         | Pydantic Settings (carrega .env) |
| `brands.json`         | Lista de 160+ marcas             |
| `exclusion_list.json` | Exclusões para e-commerce        |

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
  - sku: str           # Código interno
  - name: str          # Descrição
  - stock: float       # Estoque
  - price: float       # Preço venda
  - cost: float        # Custo
  - department: str    # Departamento
  - ean: str           # Código de barras (CodigoBarras)
  - brand: str         # Marca
```

### 2. ProductEnricher (enricher.py)

**Funcionalidades:**

- Detecta marca em 160+ padrões
- Extrai peso do nome (500g, 1kg, 1,5L)
- Gera categoria WooCommerce
- Cria descrição SEO em HTML
- Cria short_description

**Exemplo de saída:**

```python
EnrichedProduct:
  - sku: "7898242033022"
  - name: "Sachê Special Dog Carne 100g"
  - brand: "Special Dog"
  - weight_kg: 0.1
  - category: "Ração > Cachorro > Úmida"
  - description: "<div>...</div>"  # HTML com emojis
```

### 3. WooSyncManager (sync.py)

**Estratégia de Sync:**

```
1. Calcula hash_full (todos os campos)
2. Calcula hash_fast (só preço/estoque)
3. Compara com banco de dados
4. Decide: NEW | FULL_UPDATE | FAST_UPDATE | SKIP | BLOCKED
```

**PriceGuard:**

- Bloqueia variação > 40% (configurável)
- Log + notificação
- Evita erros de digitação no ERP

**Modos:**
| Modo | Campos Atualizados |
|------|-------------------|
| FULL | Nome, descrição, preço, estoque, categoria |
| LITE | Apenas preço e estoque (preserva SEO manual) |

### 4. Image Scraper v3 (scrape_all_images.py)

**Pipeline:**

```
1. Carrega produtos do CSV
2. Aplica exclusões (departamento + keywords)
3. Ordena por prioridade (estoque > 0 primeiro)
4. Para cada produto:
   a. Verifica se imagem existe → SKIP
   b. Verifica cache de Vision → usa score
   c. Busca no Google Custom Search
   d. Analisa com Vision AI
   e. Valida score semântico
   f. Salva imagem 800x800
5. Salva progresso a cada 20 produtos
```

**Otimizações v3:**

- [1] Cache de Vision AI por hash URL
- [2] Fallback de busca (3 estratégias)
- [3] Retry com backoff exponencial
- [4] Skip de imagens existentes
- [5] Prioridade por estoque

**Thresholds:**
| Departamento | Score Mínimo |
|--------------|--------------|
| PET, RACAO, PESCA | 0.45 |
| Demais (difíceis) | 0.35 |

### 5. Dashboard (dashboard/app.py)

**Stack:**

- FastAPI + Jinja2 + HTMX
- APScheduler para sync agendado
- HTTP Basic Auth opcional

**Endpoints principais:**
| Endpoint | Função |
|----------|--------|
| `GET /` | Dashboard principal |
| `GET /images` | Curadoria de imagens |
| `POST /api/sync` | Iniciar sync |
| `GET /api/images/missing` | Produtos sem imagem |
| `GET /api/images/scraper-progress` | Status scraper |
| `GET /metrics` | Prometheus metrics |

---

## 💾 Banco de Dados (SQLite)

### Tabela: products

```sql
CREATE TABLE products (
    sku TEXT PRIMARY KEY,
    name TEXT,
    woo_id INTEGER,           -- ID no WooCommerce
    last_hash_full TEXT,      -- Hash de todos os campos
    last_hash_fast TEXT,      -- Hash só preço/estoque
    last_price REAL,          -- Último preço sincronizado
    last_sync_at DATETIME,
    exists_on_site INTEGER,   -- 1 = mapeado do site
    created_at DATETIME
);
```

### Tabela: price_history

```sql
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY,
    sku TEXT,
    old_price REAL,
    new_price REAL,
    variation_percent REAL,
    blocked INTEGER,          -- 1 = bloqueado por PriceGuard
    created_at DATETIME
);
```

---

## 📤 Exclusões para E-commerce

### config/exclusion_list.json

```json
{
  "exclude_departments": ["FERRAMENTAS", "INSUMO"],
  "exclude_keywords": {
    "pereciveis": ["isca viva", "minhoca viva"],
    "decoracao_aquario": ["pedra dolomita", "cascalho", "substrato"],
    "itens_pequenos": ["anzol avulso", "miçanga"],
    "muito_pesados": ["25kg", "50kg", "20kg", "15kg"]
  },
  "max_weight_kg": 15.0
}
```

### Lógica de Exclusão

1. **Departamento** - FERRAMENTAS, INSUMO
2. **Keywords** - Perecíveis, decoração, pequenos, pesados
3. **Peso** - > 15kg automaticamente excluído

---

## 🔌 APIs Externas

### Google Custom Search

```
Endpoint: https://www.googleapis.com/customsearch/v1
Quota: 100 queries/dia (free) ou $5/1000 queries
Uso: Buscar imagens de produtos
```

### Google Vision AI

```
Endpoint: https://vision.googleapis.com/v1/images:annotate
Custo: $1.50/1000 imagens
Uso: Validar qualidade e labels das imagens
```

### WooCommerce REST API

```
Endpoint: {WOO_URL}/wp-json/wc/v3/products
Autenticação: OAuth 1.0 (consumer_key + consumer_secret)
Uso: CRUD de produtos
```

---

## 🧪 Testes

### Estrutura

```
tests/
├── conftest.py        # Fixtures compartilhadas
├── test_parser.py     # Testes do parser
├── test_enricher.py   # Testes do enricher
├── test_database.py   # Testes do banco
├── test_models.py     # Testes dos modelos
└── test_image_scraper.py  # Testes do scraper
```

### Executar

```powershell
# Todos os testes
pytest

# Com coverage
pytest --cov=src --cov-report=html

# Teste específico
pytest tests/test_parser.py -v
```

---

## 📝 Variáveis de Ambiente

### Obrigatórias

```env
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx
```

### Imagens (recomendado)

```env
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=75f6d255f...
VISION_AI_ENABLED=true
VISION_MIN_CONFIDENCE=0.6
```

### Opcionais

```env
# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_BOT_TOKEN=MTI...

# Telegram
TELEGRAM_WEBHOOK_URL=https://api.telegram.org/bot.../sendMessage

# Segurança
PRICE_GUARD_MAX_VARIATION=40
DRY_RUN=false
SYNC_ENABLED=true

# Dashboard
DASHBOARD_AUTH_ENABLED=false
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=secret
```

---

## 🚀 Roadmap Futuro

| Feature                    | Status       | Prioridade |
| -------------------------- | ------------ | ---------- |
| Scraper v3                 | ✅ Concluído | -          |
| Dashboard falhas           | ✅ Concluído | -          |
| Integração CSV + Images    | ✅ Concluído | -          |
| Upload manual de imagens   | 🔜 Próximo   | Alta       |
| Webhook estoque tempo real | 🔜 Próximo   | Média      |
| Gráficos de vendas         | 💭 Planejado | Baixa      |

---

## 📞 Suporte

- **Logs:** `logs/sync_*.log` e `logs/scraper_full.log`
- **Erros:** Verificar `get_errors` no dashboard
- **Discord:** Bot responde `!status` e `!ajuda`

---

_Documento gerado automaticamente - v3.0_
