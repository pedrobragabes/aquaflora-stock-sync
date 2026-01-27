# 🧹 Resumo da Limpeza do Projeto

> **Data:** 27 Janeiro 2026

---

## 📁 Estrutura Após Limpeza

```
aquaflora-stock-sync-main/
├── main.py                    # Entry point principal
├── bot_control.py             # Bot Discord
├── scrape_all_images.py       # Scraper de imagens (principal)
├── upload_images.py           # Upload FTP de imagens
├── tasks.ps1                  # 🆕 Comandos PowerShell
├── Makefile                   # 🆕 Comandos Make
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── config/                    # Configurações
│   ├── settings.py
│   ├── brands.json
│   ├── exclusion_list.json
│   └── image_sources.json
│
├── src/                       # Código principal
│   ├── parser.py              # Parser do ERP Athos
│   ├── enricher.py            # Enriquecimento de produtos
│   ├── database.py            # Banco SQLite
│   ├── sync.py                # Sync WooCommerce
│   ├── image_scraper.py       # Busca de imagens
│   ├── image_curator.py       # Curadoria com Vision AI
│   ├── notifications.py       # Discord/email
│   ├── models.py              # Data classes
│   └── exceptions.py          # Exceções customizadas
│
├── scripts/                   # Scripts utilitários ATIVOS
│   ├── analyze_missing_products.py  # Análise de gaps
│   ├── delete_products_by_sku.py    # Deletar produtos WC
│   ├── remove_excluded_from_woocommerce.py
│   ├── update_woo_image_urls.py     # Atualizar URLs
│   ├── upload_images_ftp.py         # Upload alternativo
│   ├── upload_images_to_woocommerce.py
│   ├── run_scraper_background.ps1   # Background task
│   └── .old/                        # ⬅️ Scripts obsoletos
│
├── docs/                      # 📚 Documentação CENTRALIZADA
│   ├── ARCHITECTURE.md        # Arquitetura do sistema
│   ├── CHANGELOG.md           # Histórico de versões
│   ├── CLEANUP_SUMMARY.md     # Este resumo
│   ├── COMANDOS.md            # Referência de comandos
│   ├── contexto.md            # Contexto técnico
│   ├── DEPLOY.md              # Guia de deploy
│   └── TROUBLESHOOTING.md     # Resolução de problemas
│
├── dashboard/                 # Web UI
├── tests/                     # Testes unitários
├── logs/                      # Logs rotativos
│
└── data/
    ├── input/                 # CSV do ERP
    ├── output/                # CSVs gerados
    ├── images/                # Imagens organizadas
    ├── reports/               # Relatórios
    ├── scraper_progress.json  # Estado do scraper
    ├── search_cache.json      # Cache de buscas
    ├── vision_cache.json      # Cache Vision AI
    └── .old/                  # ⬅️ Dados obsoletos
```

---

## 🗑️ O Que Foi Movido para `.old`

### Scripts (14 arquivos)

| Script                            | Motivo                                        |
| --------------------------------- | --------------------------------------------- |
| `analyze_departments.py`          | Análise one-time já executada                 |
| `analyze_failed_products.py`      | Relatório pontual                             |
| `analyze_geral_pesca.py`          | Específico para data de 19/01/2026            |
| `analyze_missing_images.py`       | Substituído por `analyze_missing_products.py` |
| `compare_images.py`               | Migração já feita                             |
| `consolidate_images.py`           | Migração já feita                             |
| `identify_problematic.py`         | Análise já concluída                          |
| `list_all_missing.py`             | Dados já salvos                               |
| `list_exclusions_for_deletion.py` | Gerou `robust_deletion_list.json`             |
| `organize_images.py`              | Estrutura já organizada                       |
| `organize_woocommerce_images.py`  | Export específico                             |
| `scrape_aquarismo_fix.py`         | Fix pontual                                   |
| `scrape_missing_from_csv.py`      | Duplica `scrape_all_images.py`                |
| `test_image_scraper.py`           | Teste com 5 SKUs hardcoded                    |

### Dados (17 arquivos + 3 pastas)

| Arquivo                       | Motivo                     |
| ----------------------------- | -------------------------- |
| `all_missing_products.md`     | Relatório gerado           |
| `failed_products_analysis.md` | Relatório gerado           |
| `relatorio_*.md`              | Relatórios pontuais        |
| `*_skus*.json`                | Listas de SKUs processadas |
| `deletion_results.json`       | Resultado de deleção       |
| `produtos_*.csv`              | Exports pontuais           |
| `Imagens antigas/`            | Backup antigo              |
| `images_test/`                | Testes                     |
| `testes/`                     | Dados de teste             |

---

## 💡 Ideias de Melhoria

### 🔧 Curto Prazo (Fácil)

1. **CLI unificado** - Criar um `cli.py` com subcomandos:

   ```bash
   python cli.py sync --input data/input/estoque.csv
   python cli.py scrape --limit 100
   python cli.py analyze
   python cli.py upload --dry-run
   ```

2. **Makefile/Taskfile** - Comandos comuns:

   ```makefile
   make sync          # Rodar sync completo
   make scrape        # Buscar imagens
   make test          # Rodar testes
   make clean         # Limpar cache
   ```

3. **Pre-commit hooks** - Qualidade de código:
   - black (formatação)
   - ruff (linting)
   - mypy (type checking)

4. **GitHub Actions** - CI/CD básico:
   - Rodar testes em push
   - Lint automático

### 🚀 Médio Prazo (Moderado)

5. **Consolidar uploaders** - Unificar:
   - `upload_images.py` (raiz)
   - `upload_images_ftp.py` (scripts)
   - `upload_images_to_woocommerce.py` (scripts)

   Em um único `src/uploader.py` com strategy pattern.

6. **Dashboard melhorado**:
   - Gráficos de cobertura por departamento
   - Timeline de sincronizações
   - Botão de upload de imagens

7. **Scheduled tasks** - Usar cron/Windows Task Scheduler:
   - Sync automático diário às 6h
   - Scrape semanal de novos produtos
   - Backup mensal do banco

8. **Notificações ricas**:
   - Webhook Slack/Teams
   - Email com relatório HTML
   - Push notification (Pushover)

### 🎯 Longo Prazo (Complexo)

9. **API REST** - FastAPI para integração:

   ```
   GET  /api/products
   POST /api/sync
   GET  /api/images/missing
   POST /api/scrape/{sku}
   ```

10. **Filas de processamento** - Celery/RQ:
    - Scraping em background
    - Upload paralelo
    - Retry automático

11. **Monitoramento** - Observabilidade:
    - Prometheus metrics
    - Grafana dashboards
    - Alertas de falha

12. **Multi-tenant** - Suporte a múltiplas lojas:
    - Config por loja
    - Banco separado
    - Dashboard unificado

---

## ✅ Próximos Passos Recomendados

1. [ ] Criar `cli.py` com Click/Typer
2. [ ] Adicionar Makefile com comandos comuns
3. [ ] Configurar pre-commit (black + ruff)
4. [ ] Unificar scripts de upload
5. [ ] Adicionar testes de integração
6. [ ] Documentar fluxos no README

---

## 📊 Antes vs Depois

| Métrica             | Antes | Depois           |
| ------------------- | ----- | ---------------- |
| Scripts na raiz     | 5     | 4                |
| Scripts em /scripts | 20    | 7 (+14 em .old)  |
| Arquivos em /data   | 27+   | 10 (+17 em .old) |
| Pastas de teste     | 3     | 0 (movidas)      |

**Resultado:** Estrutura 60% mais limpa e organizada! 🎉
