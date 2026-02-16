# 📋 Contexto Técnico - AquaFlora Stock Sync v4.0

> **Documento de referência para desenvolvimento e manutenção**
> Última atualização: 16 Fevereiro 2026

---

## 🎯 Visão Geral

**AquaFlora Stock Sync** é um sistema ETL que sincroniza dados do ERP Athos com o WooCommerce:

1. Importa CSV do ERP Athos (dados "sujos")
2. Enriquece com marca, peso, SEO
3. Busca imagens automaticamente
4. Upload FTP para Hostinger
5. Gera CSV para importação no WooCommerce

**Status atual:** ✅ **Sync de estoque funcionando em produção** (modo LITE).

---

## 📊 Números do Projeto

| Métrica | Valor |
|---------|-------|
| Produtos no ERP | ~4.300+ |
| Departamentos | 12 |
| Marcas detectadas | 160+ |
| Modo principal | LITE (preço + estoque) |

---

## 🏗️ Arquitetura

```
ERP Athos (CSV) → AthosParser → ProductEnricher → CSV Export → WooCommerce
                                       ↑
                              Image Finder (local)
                                       ↑
                          Image Scraper (DuckDuckGo/Google)
```

### Módulos Principais

| Módulo | Responsabilidade |
|--------|-----------------|
| `main.py` | CLI principal, orquestra o fluxo |
| `src/parser.py` | Parser CSV "sujo" do ERP |
| `src/enricher.py` | Detecta marca, peso, gera SEO |
| `src/database.py` | SQLite + histórico de preços |
| `src/sync.py` | API WooCommerce + PriceGuard |
| `src/image_scraper.py` | Busca de imagens (Google/DuckDuckGo) |
| `src/image_curator.py` | Curadoria com Vision AI |
| `src/models.py` | Pydantic models |
| `src/notifications.py` | Discord webhooks |
| `src/backup.py` | Backup do banco |
| `scrape_all_images.py` | Scraper de imagens v3 |
| `upload_images.py` | Upload FTP |
| `bot_control.py` | Bot Discord |
| `dashboard/app.py` | FastAPI + HTMX |

### Configurações

| Arquivo | Conteúdo |
|---------|----------|
| `config/settings.py` | Pydantic Settings (.env) |
| `config/brands.json` | 160+ marcas |
| `config/exclusion_list.json` | Exclusões para e-commerce |
| `config/image_sources.json` | Regras de fontes de imagem |

### Scripts Utilitários

| Script | Função |
|--------|--------|
| `scripts/analyze_missing_products.py` | Análise de gaps de imagens |
| `scripts/delete_products_by_sku.py` | Deletar produtos do WC |
| `scripts/remove_excluded_from_woocommerce.py` | Remove excluídos do WC |
| `scripts/update_woo_image_urls.py` | Atualiza URLs de imagens |
| `scripts/upload_images_ftp.py` | Upload FTP alternativo |
| `scripts/upload_images_to_woocommerce.py` | Upload direto ao WC |
| `scripts/run_scraper_background.ps1` | Scraper em background |

---

## 🔧 Fluxo de Produção

### Sync Diário (LITE)

```powershell
$env:PYTHONIOENCODING="utf-8"
python main.py --input data/input/Athos.csv --lite
# Importar CSV gerado no WooCommerce
```

### Sync Completo (quando necessário)

```powershell
python scripts/analyze_missing_products.py          # Verificar gaps
python scrape_all_images.py --only-missing --cheap   # Buscar imagens
python upload_images.py                              # Upload FTP
python main.py --input data/input/Athos.csv          # CSV completo
```

---

## ⚙️ Variáveis de Ambiente (.env)

```env
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx
IMAGE_BASE_URL=https://sualoja.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=sualoja.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DRY_RUN=false
IMAGE_SEARCH_MODE=cheap
```

---

## 🖼️ Organização de Imagens

Imagens em `data/images/{categoria}/{SKU}.{ext}`:
- Categorias: pesca, pet, aquarismo, racao, farmacia, passaros, aves, piscina, cutelaria, tabacaria, ferramentas, insumo, geral
- Extensões: `.jpg`, `.jpeg`, `.png`, `.webp`, `.avif`, `.gif`

---

## 📝 Histórico

| Versão | Data | Mudanças |
|--------|------|----------|
| 4.0 | 16/02/2026 | Limpeza total, sync funcionando, pronto para servidor |
| 3.3 | 27/01/2026 | Análise de gaps, --only-missing-images |
| 3.2 | 22/01/2026 | Consolidação de imagens, multi-extensão |
| 3.1 | 21/01/2026 | Modo cheap melhorado |
| 3.0 | 19/01/2026 | Dashboard HTMX, scraper v3, Vision AI |
| 2.0 | 15/01/2026 | Bot Discord, notificações |
| 1.0 | 10/01/2026 | Versão inicial |
