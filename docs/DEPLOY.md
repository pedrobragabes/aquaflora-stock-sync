# Deploy e Operacao

Este projeto deve rodar no PC local da loja com Windows quando a fonte do CSV Athos tambem estiver nesse ambiente.

## Windows: rotina do PC do chefe

### 1. Preparar o ambiente

```powershell
cd C:\caminho\aquaflora-stock-sync
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Configure no `.env`:

```env
WOO_URL=https://aquafloragroshop.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
SYNC_ENABLED=true
DRY_RUN=false
ZERO_GHOST_STOCK=false
```

### 2. Validar antes de publicar

```powershell
python main.py --map-site
python main.py --input C:\Estoque\Athos.csv --lite --dry-run
```

Verifique o CSV em `data/output/` e o log em `logs/`.

### 3. Rodar publicacao LITE manual

```powershell
python main.py --input C:\Estoque\Athos.csv --lite
```

No modo LITE, a API envia somente os campos tecnicos necessarios para preco e estoque. O CSV LITE exportado contem somente:

```csv
SKU,Regular price,Stock
```

### 4. Instalar automacao a cada 2 horas

Abra PowerShell como administrador dentro do projeto:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_tasks.ps1 -AtStartup
```

Isso cria a tarefa `AquaFlora Stock Sync LITE`, que executa:

```powershell
scripts\run_sync_lite.ps1
```

A tarefa roda a cada 2 horas e tambem no startup do Windows quando `-AtStartup` e usado. Por padrao, ela le o CSV em `C:\Estoque\Athos.csv`.

Se o caminho mudar, instale informando o arquivo:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_tasks.ps1 -AtStartup -InputFile "D:\OutroCaminho\Athos.csv"
```

### 5. Testar a tarefa

```powershell
Start-ScheduledTask -TaskName "AquaFlora Stock Sync LITE"
Get-Content .\logs\sync_lite_$(Get-Date -Format yyyyMMdd).log -Tail 80
```

### 6. Conferir se ficou instalada

```powershell
Get-ScheduledTask -TaskName "AquaFlora Stock Sync LITE"
Get-ScheduledTaskInfo -TaskName "AquaFlora Stock Sync LITE"
```

## Discord

As notificacoes sao enviadas ao final de cada execucao quando `DISCORD_WEBHOOK_URL` esta preenchido no `.env`.

Nao precisa rodar o bot Discord para receber notificacao de sync. O bot em `bot_control.py` serve para comandos remotos, mas a rotina automatica usa webhook.

## Recuperar pais despublicados por sync antigo

Se uma rotina antiga tiver enviado SKUs pai `P-...` para rascunho, rode primeiro em simulacao:

```powershell
python scripts/restore_parent_products.py
```

Depois execute a republicacao:

```powershell
python scripts/restore_parent_products.py --execute
```

O script le `last_run_stats.json`, filtra apenas SKUs `P-...` e altera somente `status=publish` e `catalog_visibility=visible`.

## Checklist operacional

- [ ] Python instalado no PC.
- [ ] Dependencias instaladas em `venv`.
- [ ] `.env` configurado com WooCommerce e Discord.
- [ ] `C:\Estoque\Athos.csv` presente e atualizado pelo Athos.
- [ ] `python main.py --map-site` executado.
- [ ] Dry-run LITE conferido.
- [ ] Publicacao LITE manual testada.
- [ ] Tarefa Windows instalada.
- [ ] Log diario aparecendo em `logs/sync_lite_YYYYMMDD.log`.
- [ ] Notificacao recebida no Discord.
