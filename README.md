# 🐠 AquaFlora Stock Sync v3.2

**Sistema completo de sincronização de estoque** — Migra dados do ERP Athos para WooCommerce com imagens automáticas via IA e upload FTP.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-Dashboard-green.svg)
![Vision AI](https://img.shields.io/badge/Google-Vision%20AI-orange.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![License](https://img.shields.io/badge/License-Private-red.svg)

---

## 📊 Números do Projeto

| Métrica              | Valor  |
| -------------------- | ------ |
| Produtos no ERP      | 4.074+ |
| Departamentos        | 12     |
| Marcas detectadas    | 160+   |
| Imagens organizadas  | 3.206  |
| Cobertura de imagens | 76%    |

---

## 🎯 O que este projeto faz

Sistema completo para e-commerce que:

1. **Lê CSV do ERP Athos** → Parser inteligente que limpa dados "sujos"
2. **Enriquece produtos** → Detecta marca (160+), peso, gera SEO
3. **Busca imagens** → Modo premium (Google + Vision AI) ou modo barato (DuckDuckGo/Bing)
4. **Organiza imagens** → Por categoria (pesca, pet, aquarismo, etc.)
5. **Upload FTP** → Envia imagens para Hostinger
6. **Exporta CSV WooCommerce** → Formato PT-BR com URLs públicas
7. **Dashboard Web** → Controle visual completo
8. **Bot Discord** → Comandos remotos

---

## 🚀 Quickstart

### 1. Instalar Dependências

```powershell
# Criar ambiente virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt
```

### 2. Configurar Ambiente

```powershell
# Copiar template
copy .env.example .env

# Editar credenciais
notepad .env
```

**Variáveis essenciais:**

```env
# WooCommerce (opcional, só para sync direto)
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# FTP para upload de imagens
IMAGE_BASE_URL=https://sualoja.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=sualoja.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha

# Google APIs (opcional, modo premium)
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=xxx
VISION_AI_ENABLED=true

# Discord (opcional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 3. Fluxo Completo de Produção

```powershell
# Encoding UTF-8 no Windows
$env:PYTHONIOENCODING="utf-8"

# PASSO 1: Buscar imagens (modo barato, rápido)
python scrape_all_images.py --cheap --stock-only --workers 4

# PASSO 2: Upload para servidor (se configurado FTP)
python upload_images.py

# PASSO 3: Gerar CSV para WooCommerce
python main.py --input data/input/Athos.csv

# PASSO 4: Importar no WooCommerce
# WooCommerce → Produtos → Importar → Selecionar CSV gerado
```

---

## 📁 Estrutura do Projeto

```
aquaflora-stock-sync/
├── main.py                  # CLI principal
├── scrape_all_images.py     # Scraper de imagens v3
├── upload_images.py         # Upload FTP
├── bot_control.py           # Bot Discord
├── config/
│   ├── settings.py          # Configurações (.env)
│   ├── brands.json          # 160+ marcas
│   └── exclusion_list.json  # Produtos excluídos
├── src/
│   ├── parser.py            # Parser CSV Athos
│   ├── enricher.py          # Enriquecimento produtos
│   ├── image_scraper.py     # Google/Vision/DuckDuckGo
│   ├── database.py          # SQLite + histórico
│   ├── sync.py              # API WooCommerce
│   └── models.py            # Pydantic models
├── dashboard/
│   ├── app.py               # FastAPI + HTMX
│   └── templates/           # HTML templates
├── scripts/
│   ├── organize_images.py           # Organizar por categoria
│   ├── consolidate_images.py        # Unificar imagens
│   └── compare_images.py            # Comparar pastas
├── data/
│   ├── input/               # CSVs do ERP
│   ├── output/              # CSVs para WooCommerce
│   └── images/              # Imagens organizadas por categoria
│       ├── pesca/
│       ├── pet/
│       ├── aquarismo/
│       └── ...
├── logs/                    # Logs do sistema
└── docs/                    # Documentação
```

---

## 🖼️ Sistema de Imagens

### Organização por Categoria

Imagens são organizadas em `data/images/{categoria}/`:

| Pasta        | Departamentos        |
| ------------ | -------------------- |
| `pesca/`     | GERAL PESCA, PESCA   |
| `pet/`       | PET                  |
| `aquarismo/` | AQUARISMO            |
| `passaros/`  | PÁSSAROS             |
| `racao/`     | RAÇÃO                |
| `farmacia/`  | FARMÁCIA             |
| `aves/`      | AVES                 |
| `piscina/`   | PISCINA              |
| `cutelaria/` | CUTELARIA            |
| `tabacaria/` | TABACARIA            |
| `geral/`     | Outros departamentos |

### Extensões Suportadas

O sistema detecta automaticamente imagens em:

- `.jpg`, `.jpeg` (prioridade)
- `.png`
- `.webp`
- `.avif`
- `.gif`

### Comandos de Imagem

```powershell
# Buscar imagens (modo barato)
python scrape_all_images.py --cheap --workers 4

# Buscar imagens (modo premium com Vision AI)
python scrape_all_images.py --stock-only

# Organizar imagens existentes por categoria
python scripts/organize_images.py

# Consolidar imagens de várias pastas
python scripts/consolidate_images.py

# Comparar imagens entre pastas
python scripts/compare_images.py

# Upload para FTP
python upload_images.py
```

---

## 📤 Exportação WooCommerce

### Modos de Exportação

```powershell
# FULL - Atualiza tudo (nome, descrição, imagens, preço, estoque)
python main.py --input data/input/Athos.csv

# LITE - Só preço e estoque (preserva SEO manual)
python main.py --input data/input/Athos.csv --lite

# TESTE - Só PET, PESCA, AQUARISMO (importação rápida)
python main.py --input data/input/Athos.csv --teste

# DRY RUN - Simula sem gerar arquivo
python main.py --input data/input/Athos.csv --dry-run
```

### CSV Gerado

Campos exportados:

- `SKU` - Código do produto
- `Name` - Nome formatado
- `Description` - Descrição SEO em HTML
- `Short description` - Resumo
- `Regular price` - Preço
- `Stock` - Estoque
- `Categories` - Categoria WooCommerce
- `Images` - URL da imagem (se existir)
- `Weight (kg)` - Peso
- `Brands` - Marca detectada
- E mais campos...

---

## 🌐 Dashboard Web

```powershell
# Iniciar dashboard
uvicorn dashboard.app:app --reload --port 8000

# Acessar
# http://localhost:8000
```

Funcionalidades:

- Status do sistema
- Produtos processados
- Imagens encontradas
- Logs em tempo real

---

## 🤖 Bot Discord

```powershell
# Iniciar bot
python bot_control.py
```

Comandos disponíveis:

- `!status` - Status do sistema
- `!sync` - Executar sincronização
- `!scrape` - Buscar imagens
- `!help` - Ajuda

---

## 🐳 Docker

```powershell
# Build
docker compose build

# Iniciar
docker compose up -d

# Ver logs
docker compose logs -f

# Parar
docker compose down
```

---

## 📚 Documentação Adicional

| Documento                                          | Descrição                       |
| -------------------------------------------------- | ------------------------------- |
| [COMANDOS.md](COMANDOS.md)                         | Referência completa de comandos |
| [DEPLOY.md](DEPLOY.md)                             | Guia de deploy em produção      |
| [contexto.md](contexto.md)                         | Contexto técnico detalhado      |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)       | Arquitetura do sistema          |
| [docs/CHANGELOG.md](docs/CHANGELOG.md)             | Histórico de versões            |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Resolução de problemas          |

---

## 🔧 Requisitos

- Python 3.10+
- Windows/Linux/macOS
- 4GB RAM (recomendado para scraper)
- Credenciais WooCommerce (para sync direto)
- Google Cloud (opcional, para Vision AI)

---

## 📝 Licença

Projeto privado - AquaFlora Agroshop © 2026

---

## 🆘 Suporte

- Discord: Configurar webhook para notificações
- Logs: `logs/` para diagnóstico
- Issues: Documentar em `docs/TROUBLESHOOTING.md`
