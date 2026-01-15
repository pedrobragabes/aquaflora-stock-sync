# AquaFlora Stock Sync v2.1

**Sincronizador inteligente de estoque** - Migra dados do ERP Athos para WooCommerce com segurança máxima.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-green.svg)
![Discord](https://img.shields.io/badge/Discord-Bot%202.0-blueviolet.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![Tests](https://img.shields.io/badge/Tests-pytest-yellow.svg)

---

## 🎯 O que este projeto faz

Lê arquivos CSV "sujos" exportados do sistema Athos ERP e sincroniza com sua loja WooCommerce:

- **Parsing inteligente** de CSVs com cabeçalhos misturados e lixo
- **Detecção automática** de marcas (160+), pesos e categorias
- **Geração de descrições SEO** em HTML com emojis
- **Sincronização segura** com múltiplas camadas de proteção
- **Dashboard Web** para controle visual
- **Bot Discord 2.0** com comandos inteligentes
- **Notificações** via Discord/Telegram

---

## ⚡ Quick Start

```bash
# 1. Clone e entre no diretório
cd aquaflora-stock-sync

# 2. Instale dependências
pip install -r requirements.txt

# 3. Configure credenciais
cp .env.example .env
# Edite .env com suas credenciais WooCommerce

# 4. Mapeie produtos existentes (IMPORTANTE - faça primeiro!)
python main.py --map-site

# 5. Sincronize com segurança
python main.py --input "data\input\estoque.csv" --lite --dry-run
```

---

## 🖥️ Dashboard Web (v2.1)

Interface visual para controlar sincronização sem usar terminal:

```bash
python -m uvicorn dashboard.app:app --host localhost --port 8080
```

Acesse: **http://localhost:8080**

### Funcionalidades:
- 📊 **Métricas em tempo real** (atualizam a cada 3s)
- 🚀 **Botão "Sincronizar Agora"** - um clique para rodar
- 📤 **Upload de CSV** via browser
- ⏰ **Agendamento APScheduler** - sync automático funcional
- 📋 **Histórico de preços** - tabela price_history
- 🔒 **Autenticação opcional** (HTTP Basic Auth)

### Endpoints API:
| Endpoint | Descrição |
|----------|----------|
| `/docs` | Swagger UI interativo |
| `/redoc` | Documentação ReDoc |
| `/metrics` | Métricas para monitoring |

---

## 🤖 Discord Bot 2.0 (NOVO!)

Bot com comandos inteligentes para controle remoto:

```bash
python bot_control.py
```

### Comandos:
| Comando | Descrição |
|---------|-----------|
| `!ajuda` | Menu visual de todos os comandos |
| `!status` | Status atual do sistema |
| `!whitelist` | Estatísticas de SKUs mapeados |
| `!produtos` | Últimos 10 produtos alterados |
| `!precos` | Top 5 maiores altas e quedas |
| `!forcar_agora` | Força sync imediato |
| `!log` | Envia último arquivo de log |

### Notificações Premium:
- **Logo AquaFlora** como thumbnail
- **Cores semafóricas:** 🟢 Verde (sucesso), 🟡 Amarelo (warnings), 🔴 Vermelho (erros)
- **Top 10 Destaques** com variação de preço
- **Seção Price Guard** para bloqueios destacados

---

## 🚀 Modos de Execução

| Comando | Descrição |
|---------|-----------|
| `--map-site` | Baixa SKUs do WooCommerce e cria whitelist local |
| `--input arquivo.csv` | Processa arquivo do ERP |
| `--lite` | Atualiza **apenas** preço e estoque (preserva SEO) |
| `--dry-run` | Testa sem enviar para WooCommerce |
| `--allow-create` | Permite criar produtos novos |
| `--watch` | Modo daemon - monitora pasta |
| `--log-level DEBUG` | Log detalhado |

### Exemplos de uso:

```bash
# Primeira execução: mapear site
python main.py --map-site

# Atualização rápida de preço/estoque (mais seguro)
python main.py --input "data\input\estoque.csv" --lite

# Sincronização completa (nome, descrição, atributos)
python main.py --input "data\input\estoque.csv"

# Permitir criação de novos produtos
python main.py --input "data\input\estoque.csv" --allow-create

# Testar sem enviar
python main.py --input "data\input\estoque.csv" --lite --dry-run
```

---

## 🛡️ Camadas de Segurança

### 1. **Whitelist de SKUs**
- Por padrão, **NÃO cria** produtos novos
- Só atualiza SKUs já mapeados do site
- Use `--map-site` para popular a whitelist
- Use `--allow-create` para habilitar criação

### 2. **Price Guard**
- Bloqueia atualizações com variação > 40%
- Evita erros de digitação no ERP
- Produtos bloqueados vão para log de revisão

### 3. **Dual Hash Strategy**
- `hash_full`: Detecta mudanças em nome, descrição, atributos
- `hash_fast`: Detecta mudanças apenas em preço e estoque
- Envia só o necessário, economizando API calls

### 4. **Parser de Preços Inteligente**
- Auto-detecta formato: Brasileiro (1.234,56) vs Americano (1,234.56)
- Evita erros de conversão de vírgula/ponto

---

## 📁 Estrutura do Projeto

```
aquaflora-stock-sync/
├── config/
│   └── settings.py           # Configurações (Pydantic)
├── src/
│   ├── parser.py             # AthosParser - lê CSV sujo
│   ├── enricher.py           # ProductEnricher - marca, peso, SEO
│   ├── database.py           # SQLite - hashes e whitelist
│   ├── sync.py               # WooSyncManager - API sync
│   ├── notifications.py      # Webhooks Discord/Telegram
│   └── models.py             # Pydantic models
├── dashboard/                # Dashboard Web (NOVO!)
│   ├── app.py                # FastAPI backend
│   ├── templates/            # Jinja2 + HTMX
│   └── static/               # CSS + JS
├── bot_control.py            # Discord bot 2.0
├── main.py                   # Entry point principal
├── data/
│   ├── input/                # Arquivos do ERP
│   └── output/               # CSVs gerados
├── logs/                     # Logs rotativos
├── products.db               # Banco SQLite
├── Dockerfile                # Deploy containerizado
├── docker-compose.yml        # Orquestração
├── .env                      # Credenciais (não versionar!)
└── requirements.txt          # Dependências Python
```

---

## 🐳 Deploy com Docker (Proxmox)

```bash
# No servidor
docker-compose up -d

# Dashboard: http://IP:8080
# Bot Discord roda automaticamente
```

O `docker-compose.yml` inclui:
- Dashboard web (porta 8080)
- Bot Discord (opcional)
- Volumes persistentes para DB, logs e arquivos

---

## ⚙️ Configuração (.env)

```env
# WooCommerce API
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxxxx
WOO_CONSUMER_SECRET=cs_xxxxx

# Caminhos
INPUT_DIR=./data/input
OUTPUT_DIR=./data/output
DB_PATH=./products.db

# Opções
SYNC_ENABLED=true
DRY_RUN=false

# Segurança
PRICE_GUARD_MAX_VARIATION=40
ZERO_GHOST_STOCK=false  # CUIDADO: só ative com arquivo completo

# Notificações
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Discord Bot
DISCORD_BOT_TOKEN=seu_token_aqui
DISCORD_CHANNEL_ID=seu_channel_id
```

---

## 📋 Marcas Detectadas (160+)

O sistema detecta automaticamente marcas como:
- **Pet Food**: Royal Canin, Premier, Golden, Farmina, Pedigree...
- **Veterinária**: NexGard, Bravecto, Simparic, Frontline...
- **Aquarismo**: Alcon, Tetra, Sera, Tropical, Ocean Tech...
- **Pesca**: Marine Sports, Shimano, Daiwa...
- **Agro**: Forth, Dimy, Nutriplan...
- **Piscina**: Genco, HTH, Hidroazul...
- **Ferramentas**: Tramontina, Starrett...

---

## 🔧 Troubleshooting

### "No products mapped! Run --map-site first"
Execute `python main.py --map-site` para popular a whitelist.

### "WooCommerce credentials not configured"
Configure `WOO_URL`, `WOO_CONSUMER_KEY`, `WOO_CONSUMER_SECRET` no `.env`.

### Preços errados (ex: 99.90 virando 9990)
O parser foi atualizado para auto-detectar formato. Se persistir, verifique o formato do CSV.

### Dashboard não inicia
Instale as dependências: `pip install fastapi uvicorn jinja2 python-multipart`

---

## 📄 Licença

Proprietary - AquaFlora Agroshop © 2026
