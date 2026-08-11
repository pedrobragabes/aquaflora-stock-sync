# AquaFlora Stock Sync

Sincronizacao de estoque e preco do ERP Athos para WooCommerce.

O uso operacional recomendado e o modo **LITE**. Ele atualiza somente SKU, preco e estoque, preservando nomes, descricoes, categorias, SEO, imagens e demais edicoes manuais feitas na loja.

## Fluxo Principal

1. O ERP Athos exporta um CSV para `C:\Estoque\Athos.csv`.
2. O script le o CSV, limpa os dados e identifica SKU, preco e estoque.
3. No modo LITE, o WooCommerce recebe apenas atualizacoes de preco e estoque para SKUs ja existentes.
4. Ao final, o sistema grava logs, atualiza `last_run_stats.json` e envia notificacao ao Discord se `DISCORD_WEBHOOK_URL` estiver configurado.

## Instalacao Local

Abra o PowerShell na pasta do projeto. No Windows, use sempre o Python do
ambiente virtual de forma explicita; nao dependa da ativacao do ambiente nem do
comando global `python`.

```powershell
py -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r .\requirements.txt
copy .env.example .env
notepad .env
```

Confirme que o ambiente esta correto:

```powershell
Test-Path .\venv\Scripts\python.exe
.\venv\Scripts\python.exe -c "import pydantic_settings; print('VENV OK')"
```

Se aparecer `VENV OK`, os comandos operacionais podem ser executados. Se
`Test-Path` retornar `False`, recrie o `venv` com os comandos acima.

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

## Atualizar um PC Ja Instalado

Depois de receber uma atualizacao do Git, atualize tambem as dependencias do
`venv` antes de testar o sync:

```powershell
git pull --ff-only
.\venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\venv\Scripts\python.exe -m pip check
```

O `.env`, o `products.db`, os logs e os CSVs em `data/input` e `data/output`
sao locais e nao sao substituidos pelo Git.

### Perfil agregado seguro do Athos

Para conferir um novo export sem publicar produtos, descricoes, identificadores,
precos ou estoques individuais:

```powershell
.\venv\Scripts\python.exe .\scripts\profile_athos_export.py `
    "C:\Estoque\Athos.csv" `
    --output ".\data\output\athos-profile.json"
```

O JSON contem somente hash do arquivo, formato, contagens agregadas, unidades e
estatisticas de identificadores/preco/estoque. Revise o arquivo antes de
anexa-lo a uma issue. A fixture versionada em `tests/fixtures/athos` e
completamente sintetica e nao contem linhas do cadastro real.

## Comandos Seguros

Mapear produtos existentes na loja antes da primeira sincronizacao:

```powershell
.\venv\Scripts\python.exe .\main.py --map-site
```

Esse comando consulta o WooCommerce e atualiza somente a whitelist local em
`products.db`; ele nao altera produtos no site.

Rodar uma simulacao sem publicar na loja:

```powershell
.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv" --lite --dry-run
```

Rodar a rotina real LITE:

```powershell
.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv" --lite
```

O comando real atualiza somente preco e estoque dos SKUs previamente mapeados.
Ele nao cria produtos e nao altera nomes, descricoes, categorias ou imagens.

Gerar CSV LITE para importacao manual no WooCommerce:

```powershell
.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv" --lite --dry-run
```

O arquivo gerado em `data/output/woocommerce_LITE_*.csv` contem somente:

```csv
SKU,Regular price,Stock
```

## Automacao no PC do Chefe

O caminho recomendado e o Agendador de Tarefas do Windows.

Instalar tarefa para rodar a cada 1 hora e tambem ao ligar o PC:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_tasks.ps1 -AtStartup
```

O Athos gera `C:\Estoque\Athos.csv` a cada 2 horas. A frequencia horaria do
sincronizador reduz para menos de 1 hora o atraso entre um novo arquivo e a
atualizacao no WooCommerce. Quando preco e estoque nao mudaram, os hashes em
`products.db` fazem o LITE registrar `SKIP` e evitam uma escrita desnecessaria
no WooCommerce.

Testar a tarefa manualmente:

```powershell
Start-ScheduledTask -TaskName "AquaFlora Stock Sync LITE"
```

Verificar o historico:

```powershell
$task = Get-ScheduledTask -TaskName "AquaFlora Stock Sync LITE"
$task | Select-Object TaskName, State
$task | Get-ScheduledTaskInfo |
    Format-List LastRunTime, LastTaskResult, NextRunTime, NumberOfMissedRuns
$task.Actions | Format-List Execute, Arguments

$log = Get-ChildItem .\logs\sync_lite_*.log |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
$log.FullName
Get-Content $log.FullName -Tail 150
```

`LastTaskResult: 0` indica conclusao normal. O codigo decimal `267009`
normalmente indica que a tarefa ainda esta executando. Para comprovar que o
WooCommerce recebeu mudancas, procure no log por `Whitelist`, `Batch updated`,
`Sync complete` e `AquaFlora LITE sync finished`.

A notificacao verde do Discord significa que o processo terminou sem erro
registrado, mas nao garante sozinha que houve alteracao. Confira o campo
`Atualizados`: se ele for zero, consulte o log para distinguir "nenhuma mudanca
necessaria" de produtos ignorados por falta de mapeamento.

O script chamado pela tarefa e `scripts/run_sync_lite.ps1`. Ele:

- usa `C:\Estoque\Athos.csv` por padrao;
- falha sem publicar se esse arquivo nao existir;
- prefere `venv\Scripts\python.exe` e so usa o Python global se o `venv` nao existir;
- roda `main.py --map-site` uma vez por dia antes do sync;
- roda `main.py --lite` para atualizar somente preco e estoque;
- evita duas execucoes simultaneas com lock em `logs/sync_lite.lock`;
- salva log diario em `logs/sync_lite_YYYYMMDD.log`.

Para forcar o mapeamento em toda execucao, reinstale a tarefa com:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_tasks.ps1 -AtStartup -MapSiteEveryRun
```

Para desligar o mapeamento diario automatico:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_tasks.ps1 -AtStartup -NoMapSiteDaily
```

## Modos

| Modo | Comando | Uso |
| --- | --- | --- |
| LITE | `.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv" --lite` | Rotina diaria: preco e estoque |
| LITE dry-run | `.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv" --lite --dry-run` | Teste sem publicar |
| FULL | `.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv"` | Recriacao completa de cadastro; usar com cuidado |
| LITE+IMG | `.\venv\Scripts\python.exe .\main.py --input "C:\Estoque\Athos.csv" --lite-images` | Preco, estoque e imagens |

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

- Use sempre `.\venv\Scripts\python.exe`; `python main.py` pode chamar um
  interpretador global sem as dependencias do projeto.
- Use LITE para rotina automatica.
- Rode `--map-site` antes da primeira sincronizacao real.
- Deixe `ZERO_GHOST_STOCK=false` salvo no `.env`, salvo quando o CSV for comprovadamente o universo completo.
- Nao use `--allow-create` na rotina automatica.
- Nao publique FULL para rotina de preco/estoque.

## Erro `No module named pydantic_settings`

Esse erro indica que o comando usou um Python sem as dependencias do projeto.
Nao corrija instalando pacotes aleatoriamente no Python global. Execute:

```powershell
Test-Path .\venv\Scripts\python.exe
.\venv\Scripts\python.exe -m pip install -r .\requirements.txt
.\venv\Scripts\python.exe -c "import pydantic_settings; print('VENV OK')"
```

Depois repita o comando desejado usando `.\venv\Scripts\python.exe`.

## Recuperar Pais Despublicados

Se uma execucao antiga zerou/despublicou SKUs pai `P-...`, simule a recuperacao:

```powershell
.\venv\Scripts\python.exe .\scripts\restore_parent_products.py
```

Se a lista estiver correta, publique esses pais novamente:

```powershell
.\venv\Scripts\python.exe .\scripts\restore_parent_products.py --execute
```

## Reconstruir Somente Produtos Diversos

Quando pet, pesca e ração já estiverem corrigidos no site, use o reconciliador
para recuperar do export antigo somente os demais produtos que ainda existem
no Athos atual. O comando preserva nome, descrição, categorias, imagens e marca
do WooCommerce antigo; atualiza preço e estoque pelo Athos; e deixa o `ID` vazio
para o importador localizar cada produto pelo SKU.

```powershell
.\venv\Scripts\python.exe .\scripts\build_diversos_import.py `
  --athos "C:\caminho\Athos.csv" `
  --current-pet-fishing "C:\caminho\wc-export-pet-pesca-atual.csv" `
  --legacy-all "C:\caminho\wc-export-antigo-completo.csv" `
  --split-dir "data\output\diversos_por_departamento"
```

Com `--split-dir`, o script gera um CSV por departamento Athos e
`99_todos_produtos_diversos.csv` com a união exata de todos eles. O script não
publica no site. Produtos do export antigo ausentes no Athos atual ficam apenas
no relatório e não são reimportados.
