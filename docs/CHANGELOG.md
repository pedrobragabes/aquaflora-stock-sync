# 📜 Changelog - AquaFlora Stock Sync

> **Histórico de versões e mudanças**  
> Formato: [Semantic Versioning](https://semver.org/)

---

## [3.2.0] - 2026-01-22

### ✨ Adicionado

- **Consolidação de imagens:** Script `consolidate_images.py` unifica WooCommerce + Scraper
- **Comparação de imagens:** Script `compare_images.py` analisa SKUs entre pastas
- **Multi-extensão:** Suporte a .jpg, .jpeg, .png, .webp, .avif, .gif
- **Organização WooCommerce:** Script `organize_woocommerce_images.py`
- **Documentação completa:** ARCHITECTURE.md, CHANGELOG.md, TROUBLESHOOTING.md

### 🔄 Alterado

- **Image Finder:** Agora busca todas as extensões com ordem de prioridade
- **README.md:** Atualizado para v3.2 com números atuais
- **contexto.md:** Arquitetura e métricas atualizadas
- **COMANDOS.md:** Novos comandos de organização
- **DEPLOY.md:** Guia Windows melhorado
- **.gitignore:** Organizado e expandido

### 📊 Métricas

- Imagens consolidadas: 3.206
- Cobertura: 76% (3.101 de 4.074 produtos)

---

## [3.1.0] - 2026-01-21

### ✨ Adicionado

- **Modo cheap melhorado:** DuckDuckGo com fallback Bing
- **Queries de pesca:** Preservação de códigos de modelo (CBB12, N11)
- **Cache de busca:** `data/search_cache.json` para evitar rebusca

### 🐛 Corrigido

- **DDGS API:** Parâmetro `keywords=` → `query=` (breaking change da API)
- **Format specifier:** Erro em `scrape_all_images.py`

### 🔄 Alterado

- **Bing fallback:** Múltiplas tentativas com queries variadas
- **Logging:** Mais detalhes no modo cheap

---

## [3.0.0] - 2026-01-19

### ✨ Adicionado

- **Dashboard HTMX:** Interface web com FastAPI
- **Scraper v3:** Arquitetura redesenhada
- **Vision AI:** Validação semântica de imagens
- **Bot Discord 2.0:** Comandos expandidos
- **Organização por categoria:** Imagens em subpastas

### 🔄 Alterado

- **Estrutura de pastas:** `data/images/{categoria}/`
- **Progresso retomável:** JSON com estado completo

### 🗑️ Removido

- Scraper v2 (código legado)

---

## [2.0.0] - 2026-01-15

### ✨ Adicionado

- **Bot Discord:** Controle remoto
- **Notificações:** Discord e Telegram webhooks
- **SQLite:** Histórico de preços
- **PriceGuard:** Proteção contra variações bruscas

### 🔄 Alterado

- **Parser:** Suporte a formato "sujo" do ERP
- **Enricher:** 160+ marcas

---

## [1.0.0] - 2026-01-10

### ✨ Adicionado

- **Parser CSV:** Leitura do ERP Athos
- **Enricher:** Detecção de marca e peso
- **Export CSV:** Formato WooCommerce
- **Scraper básico:** Google Images

### 📋 Funcionalidades iniciais

- Leitura de CSV do ERP
- Detecção de 50 marcas
- Extração básica de peso
- Geração de CSV para WooCommerce

---

## Legenda

| Emoji | Significado     |
| ----- | --------------- |
| ✨    | Novo recurso    |
| 🔄    | Alteração       |
| 🐛    | Correção de bug |
| 🗑️    | Removido        |
| 📊    | Métricas        |
| 📋    | Documentação    |
| ⚡    | Performance     |
| 🔒    | Segurança       |

---

## Roadmap

### v3.3.0 (Planejado)

- [ ] Automação 24h com cron/Task Scheduler
- [ ] Dashboard com gráficos
- [ ] Scraper incremental (só novos produtos)
- [ ] Backup automático

### v4.0.0 (Futuro)

- [ ] Sync bidirecional WooCommerce ↔ ERP
- [ ] Machine learning para categorização
- [ ] API REST completa
- [ ] Multi-loja
