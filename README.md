# 🐠 AquaFlora Stock Sync v4.0

**Sincronização automática de estoque e preços** — ERP Athos → WooCommerce via CSV.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)
![Status](https://img.shields.io/badge/Status-Produção-brightgreen.svg)
![License](https://img.shields.io/badge/License-Private-red.svg)

---

## ✅ Status do Projeto

O sync de estoque **está funcionando em produção**. O CSV do ERP Athos é processado e gera um CSV para importação no WooCommerce, atualizando preços e estoque automaticamente.

---

## 🎯 O que este projeto faz

1. **Lê CSV do ERP Athos** → Parser que limpa dados "sujos" do relatório
2. **Enriquece produtos** → Detecta marca (160+), peso, gera SEO
3. **Busca imagens** → Modo premium (Google + Vision AI) ou barato (DuckDuckGo/Bing)
4. **Upload FTP** → Envia imagens para o servidor Hostinger
5. **Exporta CSV WooCommerce** → Modo FULL ou LITE (só preço/estoque)
6. **Dashboard Web** → Controle visual com FastAPI + HTMX
7. **Bot Discord** → Comandos remotos e notificações

---

## 🚀 Quickstart

### 1. Instalar Dependências

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Configurar Ambiente

```powershell
copy .env.example .env
notepad .env
```

**Variáveis essenciais:**

```env
# WooCommerce
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# FTP para upload de imagens
IMAGE_BASE_URL=https://sualoja.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=sualoja.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha

# Discord (opcional)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### 3. Uso em Produção

```powershell
$env:PYTHONIOENCODING="utf-8"

# Sync LITE — só preço e estoque (uso diário)
python main.py --input data/input/Athos.csv --lite

# Sync FULL — tudo (nome, descrição, imagens, preço, estoque)
python main.py --input data/input/Athos.csv

# Dry run — simula sem gerar arquivo
python main.py --input data/input/Athos.csv --dry-run
```

---

## 📁 Estrutura do Projeto

```
aquaflora-stock-sync/
├── main.py                   # CLI principal
├── scrape_all_images.py      # Scraper de imagens
├── upload_images.py          # Upload FTP
├── bot_control.py            # Bot Discord
├── tasks.ps1                 # Comandos PowerShell
├── Makefile                  # Comandos Make
│
├── config/                   # Configurações
│   ├── settings.py           # Pydantic settings (.env)
│   ├── brands.json           # 160+ marcas
│   ├── exclusion_list.json   # Produtos excluídos
│   └── image_sources.json    # Regras de fontes de imagem
│
├── src/                      # Código principal
│   ├── parser.py             # Parser CSV Athos
│   ├── enricher.py           # Enriquecimento de produtos
│   ├── database.py           # SQLite + histórico
│   ├── sync.py               # API WooCommerce
│   ├── image_scraper.py      # Google/Vision/DuckDuckGo
│   ├── image_curator.py      # Curadoria de imagens
│   ├── models.py             # Pydantic models
│   ├── notifications.py      # Discord webhooks
│   ├── backup.py             # Backup do banco
│   ├── logging_config.py     # Configuração de logs
│   └── exceptions.py         # Exceções customizadas
│
├── scripts/                  # Scripts utilitários
│   ├── analyze_missing_products.py
│   ├── delete_products_by_sku.py
│   ├── remove_excluded_from_woocommerce.py
│   ├── update_woo_image_urls.py
│   ├── upload_images_ftp.py
│   ├── upload_images_to_woocommerce.py
│   └── run_scraper_background.ps1
│
├── dashboard/                # Web UI (FastAPI + HTMX)
├── tests/                    # Testes unitários
├── docs/                     # Documentação
├── data/
│   ├── input/                # CSVs do ERP
│   ├── output/               # CSVs gerados para WooCommerce
│   ├── images/               # Imagens organizadas por categoria
│   └── reports/              # Relatórios
│
└── logs/                     # Logs do sistema
```

---

## 📤 Modos de Exportação

| Modo | Comando | O que atualiza |
|------|---------|---------------|
| **FULL** | `python main.py --input Athos.csv` | Tudo: nome, descrição, imagens, preço, estoque |
| **LITE** | `python main.py --input Athos.csv --lite` | Só preço e estoque (preserva SEO) |
| **LITE+IMG** | `python main.py --input Athos.csv --lite-images` | Preço, estoque e imagens |
| **TESTE** | `python main.py --input Athos.csv --teste` | Só PET, PESCA, AQUARISMO |

---

## 🖼️ Sistema de Imagens

Imagens organizadas em `data/images/{categoria}/`:

| Pasta | Departamentos |
|-------|--------------|
| `pesca/` | GERAL PESCA, PESCA |
| `pet/` | PET |
| `aquarismo/` | AQUARISMO |
| `racao/` | RAÇÃO |
| `farmacia/` | FARMÁCIA |
| `passaros/` | PÁSSAROS |
| `aves/` | AVES |
| `piscina/` | PISCINA |
| `cutelaria/` | CUTELARIA |
| `tabacaria/` | TABACARIA |
| `ferramentas/` | FERRAMENTAS |
| `insumo/` | INSUMO |
| `geral/` | Outros |

```powershell
# Buscar imagens faltantes
python scrape_all_images.py --only-missing-images --cheap --workers 4

# Upload para servidor
python upload_images.py

# Analisar cobertura
python scripts/analyze_missing_products.py
```

---

## 🐳 Docker

```powershell
docker compose build
docker compose up -d
docker compose logs -f
```

---

## 📚 Documentação

| Documento | Descrição |
|-----------|-----------|
| [COMANDOS.md](docs/COMANDOS.md) | Referência de comandos |
| [DEPLOY.md](docs/DEPLOY.md) | Guia de deploy em servidor |
| [contexto.md](docs/contexto.md) | Contexto técnico |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Arquitetura do sistema |
| [CHANGELOG.md](docs/CHANGELOG.md) | Histórico de versões |
| [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Resolução de problemas |

---

## 🔧 Requisitos

- Python 3.10+
- 2GB RAM (recomendado)
- Credenciais WooCommerce
- Acesso FTP (para imagens)
- Google Cloud (opcional, para Vision AI)

---

## 📝 Licença

Projeto privado — AquaFlora Agroshop © 2026
