# 📋 Contexto Técnico - AquaFlora Stock Sync v3.1

> **Documento de referência para desenvolvimento e manutenção**  
> Última atualização: 21 Janeiro 2026

---

## 🎯 Visão Geral

**AquaFlora Stock Sync** é um sistema completo de e-commerce que:

1. Importa dados do ERP Athos (CSV)
2. Enriquece com marca, peso, SEO
3. Busca imagens automaticamente (Google + Vision AI)
4. Faz upload FTP para Hostinger
5. Gera CSV para importação no WooCommerce
6. Fornece dashboard web e bot Discord

---

## 📊 Números do Projeto

| Métrica                     | Valor  |
| --------------------------- | ------ |
| Produtos no ERP             | 4.352  |
| Departamentos               | 12     |
| Marcas detectadas           | 160+   |
| Semânticas Vision AI        | 80+    |
| Produtos válidos e-commerce | ~3.962 |
| Excluídos (automático)      | ~390   |
| Imagens processadas         | 1.727  |

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
         ▲
         │
┌────────┴────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Image Scraper  │────▶│   Vision AI     │────▶│   FTP Upload    │
│ (scrape_all_images)   │ (image_scraper) │     │   (Hostinger)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
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

| Arquivo               | Conteúdo                            |
| --------------------- | ----------------------------------- |
| `settings.py`         | Pydantic Settings (carrega .env)    |
| `brands.json`         | Lista de 160+ marcas                |
| `exclusion_list.json` | Exclusões completas para e-commerce |

### Scripts (pasta scripts/)

| Script                       | Função                                  |
| ---------------------------- | --------------------------------------- |
| `analyze_departments.py`     | Analisa departamentos do ERP            |
| `analyze_geral_pesca.py`     | Análise específica dept Geral Pesca     |
| `analyze_missing_images.py`  | Lista produtos sem imagem               |
| `test_image_scraper.py`      | Testa scraper em produtos específicos   |
| `run_scraper_background.ps1` | Roda scraper em background (PowerShell) |

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
  - category: "Pet"
  - description: "<div>...</div>"  # HTML com emojis
```

### 3. Export CSV WooCommerce (main.py)

**Formato PT-BR com colunas:**

```
ID, Tipo, SKU, Nome, Publicado, Em destaque?, Visibilidade no catálogo,
Descrição curta, Descrição, Preço promocional, Preço normal,
Categorias, Tags, Imagens, Limite de downloads, Dias para expirar...
```

**Campos importantes:**

- **Categorias**: Departamento do ERP (Pet, Pesca, Aquarismo, etc.)
- **Tags**: Categoria + Marca (ex: "Pet, Special Dog")
- **Marcas**: Marca detectada pelo enricher
- **Imagens**: URL pública no Hostinger (https://aquafloragroshop.com.br/wp-content/uploads/produtos/{sku}.jpg)

### 4. Sistema de Exclusões

**config/exclusion_list.json:**

```json
{
  "exclude_departments": ["FERRAMENTAS", "INSUMO", "INSUMOS"],
  "exclude_keywords": {
    "pereciveis": ["isca viva", "minhoca viva", "larva"],
    "bebidas": ["refrigerante", "cerveja", "agua mineral"],
    "tabaco": ["cigarro", "fumo"],
    "muito_pesados": ["25kg", "50kg", "20kg"],
    "muito_grandes_volumosos": [
      "bebedouro galinha",
      "caixa d'agua",
      "gaiola grande"
    ],
    "dificil_embalar": ["vara de bambu", "cano pvc"],
    "decoracao_aquario": ["pedra dolomita", "cascalho"],
    "itens_pequenos": ["anzol avulso", "miçanga"],
    "frageis_quebraveis": ["aquario vidro", "vaso ceramica grande"]
  },
  "max_weight_kg": 15.0,
  "priority_categories_for_test": ["PET", "PESCA", "AQUARISMO"]
}
```

**Lógica de Exclusão:**

1. **Departamento** - FERRAMENTAS, INSUMO (194 produtos)
2. **Keywords** - Perecíveis, bebidas, frágeis, volumosos (164 produtos)
3. **Peso** - > 15kg automaticamente excluído (32 produtos)

**Exceção:** Ração > 15kg é mantida (usa plástico stretch para embalar)

### 5. Image Scraper v3 (scrape_all_images.py)

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

**Thresholds:**
| Departamento | Score Mínimo |
|--------------|--------------|
| PET, RACAO, PESCA | 0.45 |
| Demais (difíceis) | 0.35 |

### 6. FTP Upload (Hostinger)

**Configuração:**

```python
FTP_HOST = "147.93.38.37"
FTP_PORT = 21
FTP_USER = "u599889telefo@aquafloragroshop.com.br"
FTP_PATH = "/domains/aquafloragroshop.com.br/public_html/wp-content/uploads/produtos/"
```

**URL Pública:**

```
https://aquafloragroshop.com.br/wp-content/uploads/produtos/{sku}.jpg
```

### 7. Dashboard (dashboard/app.py)

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

---

## 🚀 Comandos CLI

### Importação Completa

```powershell
python main.py --input data/input/Athos.csv
```

### Modo Teste (apenas PET, PESCA, AQUARISMO)

```powershell
python main.py --input data/input/Athos.csv --teste
```

### Modo LITE (só preço/estoque)

```powershell
python main.py --input data/input/Athos.csv --lite
```

### Dry Run (simula sem alterar)

```powershell
python main.py --input data/input/Athos.csv --dry-run
```

### Scraper de Imagens

```powershell
python scrape_all_images.py --limit 100 --dept PET
```

### Upload FTP

```powershell
python -c "from src.image_scraper import upload_images_ftp; upload_images_ftp()"
```

---

## 📝 Variáveis de Ambiente

### Obrigatórias

```env
WOO_URL=https://aquafloragroshop.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx
```

### FTP (para upload de imagens)

```env
FTP_HOST=147.93.38.37
FTP_USER=u599889telefo@aquafloragroshop.com.br
FTP_PASS=sua_senha
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

## 📞 Suporte

- **Logs:** `logs/sync_*.log` e `logs/scraper_full.log`
- **Erros:** Verificar `get_errors` no dashboard
- **Discord:** Bot responde `!status` e `!ajuda`

---

_Documento atualizado - v3.1 - 21/01/2026_
