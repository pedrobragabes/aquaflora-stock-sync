# 🚀 Guia de Deploy - AquaFlora Stock Sync v3.3

> **Guia completo para deploy em produção**  
> Última atualização: 27 Janeiro 2026

---

## 📋 Pré-requisitos

- Servidor Linux (Debian/Ubuntu) ou Windows Server
- Docker e Docker Compose (opcional)
- Python 3.10+ (se sem Docker)
- 2GB RAM, 20GB disco (recomendado)
- Acesso FTP ao servidor de imagens

---

## 🖥️ Opção A: Windows (Produção Local)

### 1. Instalar Python

```powershell
# Baixar Python 3.10+ de python.org
# Marcar "Add to PATH" durante instalação

# Verificar instalação
python --version
pip --version
```

### 2. Clonar/Copiar Projeto

```powershell
cd C:\Users\pedro\OneDrive\Documentos
git clone <repo-url> aquaflora-stock-sync
# ou copiar pasta manualmente
```

### 3. Criar Ambiente Virtual

```powershell
cd aquaflora-stock-sync
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 4. Configurar Ambiente

```powershell
copy .env.example .env
notepad .env
```

**Configurar:**

```env
# WooCommerce
WOO_URL=https://aquafloragroshop.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# FTP Hostinger
IMAGE_BASE_URL=https://aquafloragroshop.com.br/wp-content/uploads/produtos/
IMAGE_FTP_HOST=aquafloragroshop.com.br
IMAGE_FTP_USER=usuario
IMAGE_FTP_PASSWORD=senha

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Produção
DRY_RUN=false
```

### 5. Testar

```powershell
$env:PYTHONIOENCODING="utf-8"
python main.py --input data/input/Athos.csv --dry-run
```

### 6. Automatizar com Task Scheduler

1. Abrir **Task Scheduler** (Agendador de Tarefas)
2. Criar nova tarefa:
   - Nome: `AquaFlora Sync`
   - Gatilho: Diário às 06:00
   - Ação: Executar programa
     - Programa: `powershell.exe`
     - Argumentos: `-ExecutionPolicy Bypass -File "C:\...\scripts\run_sync.ps1"`

**Usar o `tasks.ps1` já incluso ou criar script `scripts/run_sync.ps1`:**

```powershell
$env:PYTHONIOENCODING="utf-8"
cd "C:\Users\pedro\OneDrive\Documentos\aquaflora-stock-sync-main"
.\venv\Scripts\Activate.ps1

# Analisar cobertura
python scripts/analyze_missing_products.py

# Buscar imagens faltantes
python scrape_all_images.py --only-missing-images --cheap --workers 4

# Upload novas imagens
python upload_images.py

# Gerar CSV
python main.py --input data/input/Athos.csv 2>&1 |
    Tee-Object -FilePath "logs\sync_$(Get-Date -Format yyyyMMdd).log"
```

**Ou simplesmente usar tasks.ps1:**

```powershell
.\tasks.ps1 analyze
.\tasks.ps1 scrape-all
.\tasks.ps1 upload-real
.\tasks.ps1 sync-real
```

---

## 🐧 Opção B: Linux (Servidor)

### 1. Preparar Servidor

```bash
# SSH no servidor
ssh root@<ip-servidor>

# Atualizar sistema
apt update && apt upgrade -y
apt install -y python3.10 python3-pip python3-venv git
```

### 2. Clonar Projeto

```bash
cd /opt
git clone <repo-url> aquaflora-stock-sync
cd aquaflora-stock-sync
```

### 3. Criar Ambiente

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configurar

```bash
cp .env.example .env
nano .env
```

### 5. Criar Serviço Systemd

**Criar `/etc/systemd/system/aquaflora-sync.service`:**

```ini
[Unit]
Description=AquaFlora Stock Sync
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/aquaflora-stock-sync
Environment=PYTHONIOENCODING=utf-8
ExecStart=/opt/aquaflora-stock-sync/venv/bin/python main.py --input data/input/Athos.csv

[Install]
WantedBy=multi-user.target
```

**Criar timer `/etc/systemd/system/aquaflora-sync.timer`:**

```ini
[Unit]
Description=Run AquaFlora Sync daily

[Timer]
OnCalendar=*-*-* 06:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable aquaflora-sync.timer
systemctl start aquaflora-sync.timer

# Verificar
systemctl list-timers
```

### 6. Dashboard como Serviço

**Criar `/etc/systemd/system/aquaflora-dashboard.service`:**

```ini
[Unit]
Description=AquaFlora Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/aquaflora-stock-sync
Environment=PYTHONIOENCODING=utf-8
ExecStart=/opt/aquaflora-stock-sync/venv/bin/uvicorn dashboard.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable aquaflora-dashboard
systemctl start aquaflora-dashboard

# Verificar
systemctl status aquaflora-dashboard
```

---

## 🐳 Opção C: Docker

### 1. Instalar Docker

```bash
# Linux
curl -fsSL https://get.docker.com | sh
apt install -y docker-compose-plugin

# Windows
# Baixar Docker Desktop de docker.com
```

### 2. Configurar

```bash
cp .env.example .env
nano .env  # ou notepad .env no Windows
```

### 3. Build e Iniciar

```bash
docker compose build
docker compose up -d
```

### 4. Verificar

```bash
docker compose ps
docker compose logs -f
```

### 5. Comandos Úteis

```bash
# Parar
docker compose down

# Rebuild
docker compose build --no-cache
docker compose up -d

# Executar comando
docker compose exec app python main.py --dry-run
docker compose exec app python analyze_missing_products.py

# Shell no container
docker compose exec app bash
```

---

## 🔐 Segurança

### Proteger Credenciais

1. **Nunca commitar `.env`** - já está no `.gitignore`
2. **Usar senhas fortes** para FTP e APIs
3. **Limitar acesso FTP** apenas ao diretório de imagens
4. **Rotacionar chaves** WooCommerce periodicamente

### Firewall (Linux)

```bash
# Permitir apenas portas necessárias
ufw allow 22    # SSH
ufw allow 8000  # Dashboard (se exposto)
ufw enable
```

### HTTPS para Dashboard

Usar Nginx como proxy reverso com SSL:

```nginx
server {
    listen 443 ssl;
    server_name dashboard.sualoja.com.br;

    ssl_certificate /etc/letsencrypt/live/.../fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/.../privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 📊 Monitoramento

### Logs

```bash
# Linux
tail -f /opt/aquaflora-stock-sync/logs/*.log
journalctl -u aquaflora-sync -f

# Windows
Get-Content logs\*.log -Wait
```

### Discord Notifications

Configurar webhook para receber notificações de:

- ✅ Sincronização completa
- ❌ Erros de processamento
- 📊 Estatísticas diárias

### Healthcheck

```bash
# Verificar se dashboard responde
curl http://localhost:8000/health

# Verificar último sync
cat last_run_stats.json

# Verificar cobertura de imagens
python analyze_missing_products.py
```

### Relatórios Automáticos

O scraper gera relatórios de sucesso em:

- `data/reports/image_success_*.json` - Dados brutos
- `data/reports/image_success_*.md` - Relatório legível
- `data/missing_products_report.json` - Análise de gaps

---

## 🔄 Atualizações

### Git Pull

```bash
cd /opt/aquaflora-stock-sync
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
systemctl restart aquaflora-dashboard
```

### Docker

```bash
docker compose pull
docker compose build --no-cache
docker compose up -d
```

---

## 🆘 Troubleshooting

### Erro de Encoding

```powershell
# Windows - adicionar no início de scripts
$env:PYTHONIOENCODING="utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### FTP Timeout

```env
# Aumentar timeout no .env
FTP_TIMEOUT=60
```

### Memória Insuficiente

```bash
# Aumentar swap (Linux)
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
```

### Dashboard não Inicia

```bash
# Verificar porta em uso
lsof -i :8000
# ou
netstat -an | findstr 8000

# Matar processo
kill -9 <PID>
```

### Rate Limit do DuckDuckGo

```powershell
# Usar menos workers
python scrape_all_images.py --cheap --workers 1

# Ou usar modo premium (se tiver quota)
python scrape_all_images.py --stock-only
```

---

## 📋 Checklist de Deploy

- [ ] Python 3.10+ instalado
- [ ] Dependências instaladas (`pip install -r requirements.txt`)
- [ ] `.env` configurado com credenciais
- [ ] Diretórios criados (`data/input`, `data/output`, `data/images`, `logs`)
- [ ] CSV do ERP copiado para `data/input/`
- [ ] Teste dry-run funcionando
- [ ] FTP testado (upload de imagem teste)
- [ ] Discord webhook configurado
- [ ] Automação configurada (Task Scheduler / Cron / Systemd)
- [ ] Dashboard acessível
- [ ] Backup configurado
- [ ] `analyze_missing_products.py` rodando para monitorar gaps
