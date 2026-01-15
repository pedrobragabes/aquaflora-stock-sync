# AquaFlora Stock Sync - Guia de Comandos 📚

> **Última atualização:** Janeiro 2026

Referência completa de todos os comandos e argumentos do projeto.

---

## 🖥️ CLI Principal (`main.py`)

Script principal para sincronização via linha de comando.

### Comandos Básicos

```bash
# Sincronização básica (FULL MODE)
python main.py --input data/input/estoque.csv

# Modo LITE - Apenas preço e estoque (não altera nome/descrição/imagens)
python main.py --input data/input/estoque.csv --lite

# Dry Run - Simula sem alterar nada no WooCommerce
python main.py --input data/input/estoque.csv --dry-run

# Criar novos produtos (por padrão, só atualiza existentes)
python main.py --input data/input/estoque.csv --allow-create
```

### Comandos Avançados

```bash
# Mapear whitelist do site WooCommerce
python main.py --map-site

# Modo Watch - Monitora pasta e sincroniza automaticamente
python main.py --watch

# Combinar opções
python main.py --input data/input/estoque.csv --lite --dry-run
python main.py --input data/input/estoque.csv --allow-create --lite
```

### Argumentos Disponíveis

| Argumento | Descrição |
|-----------|-----------|
| `--input FILE` | Arquivo CSV de entrada do Athos ERP |
| `--lite` | Modo lite: só atualiza preço e estoque |
| `--dry-run` | Simula sem enviar para WooCommerce |
| `--allow-create` | Permite criar novos produtos |
| `--map-site` | Baixa lista de SKUs do WooCommerce |
| `--watch` | Daemon que monitora pasta de entrada |

---

## 🌐 Dashboard Web (`dashboard/app.py`)

Interface web FastAPI com HTMX para controle visual.

### Iniciar Dashboard

# Desenvolvimento (com reload automático)
uvicorn dashboard.app:app --reload --port 8080

# Produção
python -m uvicorn dashboard.app:app --host [IP_ADDRESS] --port 6958

# Via Docker
docker-compose up dashboard

### Endpoints da API

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Página principal do dashboard |
| `/docs` | GET | Documentação Swagger UI |
| `/redoc` | GET | Documentação ReDoc |
| `/metrics` | GET | Métricas para monitoring |
| `/api/status` | GET | Status atual do sistema |
| `/api/sync/run` | POST | Iniciar sincronização |
| `/api/schedule` | POST | Configurar agendamento |
| `/api/upload` | POST | Upload de arquivo CSV |
| `/api/whitelist/refresh` | POST | Atualizar whitelist |

### Autenticação (opcional)

Configurar no `.env`:
```env
DASHBOARD_AUTH_ENABLED=true
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=sua_senha_segura
```

---

## 🤖 Bot Discord (`bot_control.py`)

Controle remoto via comandos Discord.

### Iniciar Bot

```bash
# Direto
python bot_control.py

# Via Docker
docker-compose up bot
```

### Comandos do Bot

| Comando | Aliases | Descrição |
|---------|---------|-----------|
| `!ajuda` | `!help_sync`, `!comandos`, `!menu` | Menu de ajuda |
| `!status` | `!s`, `!stats` | Status da última sincronização |
| `!forcar_agora` | `!sync`, `!forcar` | Força sincronização imediata |
| `!produtos` | `!prods`, `!changes` | Últimos 10 produtos alterados |
| `!precos` | `!prices`, `!variacao` | Top variações de preço |
| `!whitelist` | `!wl`, `!mapeados` | Estatísticas da whitelist |
| `!log` | `!logs` | Envia último arquivo de log |

### Configuração no `.env`

```env
DISCORD_BOT_TOKEN=seu_token_aqui
DISCORD_CHANNEL_ID=123456789  # Canal principal
```

---

## 🐳 Docker Compose

Comandos para gerenciar os serviços containerizados.

```bash
# Subir todos os serviços
docker-compose up -d

# Subir apenas o dashboard
docker-compose up -d dashboard

# Subir apenas o bot
docker-compose up -d bot

# Ver logs
docker-compose logs -f dashboard
docker-compose logs -f bot

# Reiniciar serviços
docker-compose restart dashboard bot

# Parar tudo
docker-compose down
```

---

## 🧪 Testes

Executar suite de testes automatizados.

```bash
# Rodar todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ --cov=src --cov-report=html

# Teste específico
pytest tests/test_parser.py -v
pytest tests/test_enricher.py -v
pytest tests/test_database.py -v
pytest tests/test_models.py -v
```

---

## ⚙️ Configuração Rápida (.env)

```env
# WooCommerce API
WOO_URL=https://aquafloraagroshop.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# Diretórios
INPUT_DIR=./data/input
OUTPUT_DIR=./data/output
DB_PATH=./products.db

# Segurança
PRICE_GUARD_MAX_VARIATION=40.0
DRY_RUN=false

# Dashboard
DASHBOARD_AUTH_ENABLED=true
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=senha123

# Notificações
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx
DISCORD_BOT_TOKEN=xxx
DISCORD_CHANNEL_ID=xxx

# Logs
LOG_LEVEL=INFO
LOG_JSON_FORMAT=false
```

---

## 📌 Atalhos Úteis

```bash
# Sync rápido (lite + último CSV)
python main.py --input $(ls -t data/input/*.csv | head -1) --lite

# Health check do dashboard
curl http://localhost:8080/api/status

# Verificar métricas
curl http://localhost:8080/metrics
```
