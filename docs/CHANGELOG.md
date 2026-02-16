# 📜 Changelog - AquaFlora Stock Sync

> **Histórico de versões e mudanças**
> Formato: [Semantic Versioning](https://semver.org/)

---

## [4.0.0] - 2026-02-16

### 🧹 Limpeza Total

- **Removido:** Pasta `Correção Imagem/` (CSVs antigos por categoria)
- **Removido:** `scripts/.old/` (17 scripts obsoletos)
- **Removido:** `data/.old/` (relatórios e dados antigos)
- **Removido:** Pastas duplicadas `data/images scraper/` e `data/images woocommerce/`
- **Removido:** `docs/CLEANUP_SUMMARY.md` (documento pontual)
- **Removido:** Caches, logs antigos e artefatos runtime

### 📚 Documentação

- **Atualizado:** Todos os `.md` reescritos para v4.0
- **README.md:** Simplificado, foco no sync LITE em produção
- **contexto.md:** Reflete estado atual do projeto
- **DEPLOY.md:** Foco em deploy no servidor
- **ARCHITECTURE.md:** Sem referências a features/scripts deletados
- **COMANDOS.md:** Só comandos dos scripts ativos
- **.gitignore:** Limpo, sem duplicatas

### ✅ Status

- Sync de estoque funcionando em produção (modo LITE)
- Projeto limpo e pronto para deploy em servidor

---

## [3.3.0] - 2026-01-27

### ✨ Adicionado

- **Análise de gaps:** Script `analyze_missing_products.py`
- **Flag --only-missing-images:** Processa apenas SKUs sem imagem
- **Relatórios de sucesso:** Geração automática por departamento/marca
- **Timeout por produto:** Evita travamentos

### 🔄 Alterado

- Documentação atualizada para v3.3
- .gitignore expandido

---

## [3.2.0] - 2026-01-22

### ✨ Adicionado

- **Consolidação de imagens:** Unifica WooCommerce + Scraper
- **Multi-extensão:** Suporte a .jpg, .jpeg, .png, .webp, .avif, .gif
- **Flag --lite-images:** Exporta preço, estoque e imagens
- **Documentação:** ARCHITECTURE.md, CHANGELOG.md, TROUBLESHOOTING.md

---

## [3.1.0] - 2026-01-21

### ✨ Adicionado

- **Modo cheap melhorado:** DuckDuckGo com fallback Bing
- **Cache de busca:** `data/search_cache.json`

### 🐛 Corrigido

- **DDGS API:** `keywords=` → `query=`

---

## [3.0.0] - 2026-01-19

### ✨ Adicionado

- **Dashboard HTMX:** Interface web com FastAPI
- **Scraper v3:** Arquitetura redesenhada
- **Vision AI:** Validação semântica de imagens
- **Bot Discord 2.0:** Comandos expandidos

---

## [2.0.0] - 2026-01-15

### ✨ Adicionado

- Bot Discord, notificações Discord/Telegram
- SQLite com histórico de preços
- PriceGuard

---

## [1.0.0] - 2026-01-10

### ✨ Versão Inicial

- Parser CSV, detecção de marcas, export WooCommerce, scraper básico

---

## Legenda

| Emoji | Significado |
|-------|------------|
| ✨ | Novo recurso |
| 🔄 | Alteração |
| 🐛 | Correção |
| 🗑️ | Removido |
| 🧹 | Limpeza |
| 📚 | Documentação |
