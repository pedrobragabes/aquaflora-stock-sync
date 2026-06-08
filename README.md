# AquaFlora Stock Sync

Sincronizacao de estoque e preco do ERP Athos para WooCommerce.

O uso operacional recomendado e o modo **LITE**. Ele atualiza somente SKU, preco e estoque, preservando nomes, descricoes, categorias, SEO, imagens e demais edicoes manuais feitas na loja.

## Fluxo Principal

1. O ERP Athos exporta um CSV para `C:\Estoque\Athos.csv`.
2. O script le o CSV, limpa os dados e identifica SKU, preco e estoque.
3. No modo LITE, o WooCommerce recebe apenas atualizacoes de preco e estoque para SKUs ja existentes.
4. Ao final, o sistema grava logs, atualiza `last_run_stats.json` e envia notificacao ao Discord se `DISCORD_WEBHOOK_URL` estiver configurado.

## Instalacao Local

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Variaveis essenciais no `.env`:

```env
WOO_URL=https://aquafloragroshop.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
SYNC_ENABLED=true
DRY_RUN=false
ZERO_GHOST_STOCK=false
```

## Comandos Seguros

Mapear produtos existentes na loja antes da primeira sincronizacao:

```powershell
python main.py --map-site
```

Rodar uma simulacao sem publicar na loja:

```powershell
python main.py --input C:\Estoque\Athos.csv --lite --dry-run
```

Rodar a rotina real LITE:

```powershell
python main.py --input C:\Estoque\Athos.csv --lite
```

Gerar CSV LITE para importacao manual no WooCommerce:

```powershell
python main.py --input C:\Estoque\Athos.csv --lite --dry-run
```

O arquivo gerado em `data/output/woocommerce_LITE_*.csv` contem somente:

```csv
SKU,Regular price,Stock
```

## Automacao no PC do Chefe

O caminho recomendado e o Agendador de Tarefas do Windows.

Instalar tarefa para rodar a cada 2 horas e tambem ao ligar o PC:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_tasks.ps1 -AtStartup
```

Testar a tarefa manualmente:

```powershell
Start-ScheduledTask -TaskName "AquaFlora Stock Sync LITE"
```

Verificar o historico:

```powershell
Get-ScheduledTask -TaskName "AquaFlora Stock Sync LITE"
Get-Content .\logs\sync_lite_$(Get-Date -Format yyyyMMdd).log -Tail 80
```

O script chamado pela tarefa e `scripts/run_sync_lite.ps1`. Ele:

- usa `C:\Estoque\Athos.csv` por padrao;
- falha sem publicar se esse arquivo nao existir;
- roda `python main.py --lite`;
- evita duas execucoes simultaneas com lock em `logs/sync_lite.lock`;
- salva log diario em `logs/sync_lite_YYYYMMDD.log`.

## Modos

| Modo | Comando | Uso |
| --- | --- | --- |
| LITE | `python main.py --input data/input/Athos.csv --lite` | Rotina diaria: preco e estoque |
| LITE dry-run | `python main.py --input data/input/Athos.csv --lite --dry-run` | Teste sem publicar |
| FULL | `python main.py --input data/input/Athos.csv` | Recriacao completa de cadastro; usar com cuidado |
| LITE+IMG | `python main.py --input data/input/Athos.csv --lite-images` | Preco, estoque e imagens |

## Estrutura

```text
main.py                    CLI principal
src/parser.py              Parser do CSV Athos
src/enricher.py            Normalizacao e enriquecimento
src/sync.py                Envio para WooCommerce
src/notifications.py       Webhook Discord/Telegram
src/database.py            SQLite local e whitelist
scripts/run_sync_lite.ps1  Execucao operacional LITE no Windows
scripts/install_windows_tasks.ps1 Instalacao do agendamento Windows
dashboard/                 Dashboard FastAPI
tests/                     Testes automatizados
docs/                      Documentacao
```

## Regras de Seguranca

- Use LITE para rotina automatica.
- Rode `--map-site` antes da primeira sincronizacao real.
- Deixe `ZERO_GHOST_STOCK=false` salvo no `.env`, salvo quando o CSV for comprovadamente o universo completo.
- Nao use `--allow-create` na rotina automatica.
- Nao publique FULL para rotina de preco/estoque.
