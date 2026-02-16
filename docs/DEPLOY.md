# 🚀 Guia de Deploy - AquaFlora Stock Sync v4.0

> **Guia completo para deploy em produção**
> Última atualização: 16 Fevereiro 2026

---

## 📋 Pré-requisitos

- Servidor Linux (Debian/Ubuntu) ou Windows Server
- Docker e Docker Compose (opcional)
- Python 3.10+ (se sem Docker)
- 2GB RAM, 20GB disco
- Acesso FTP ao servidor de imagens

---

## 🖥️ Opção A: Windows (Produção Local)

### 1. Instalar e Configurar

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
notepad .env
```

### 2. Testar

```powershell
$env:PYTHONIOENCODING="utf-8"
python main.py --input data/input/Athos.csv --dry-run
```

### 3. Automatizar com Task Scheduler

1. Abrir **Task Scheduler** (Agendador de Tarefas)
2. Criar nova tarefa:
   - Nome: `AquaFlora Sync`
   - Gatilho: A cada 2 horas (ou conforme necessidade)
   - Ação: Executar programa
     - Programa: `powershell.exe`
     - Argumentos: `-ExecutionPolicy Bypass -File "C:\...\scripts\run_sync.ps1"`

**Exemplo de script `run_sync.ps1`:**

```powershell
$env:PYTHONIOENCODING="utf-8"
cd "C:\caminho\aquaflora-stock-sync"
.\venv\Scripts\Activate.ps1

python main.py --input data/input/Athos.csv --lite 2>&1 |
    Tee-Object -FilePath "logs\sync_$(Get-Date -Format yyyyMMdd).log"
```

---

## 🐧 Opção B: Linux (Servidor)

### 1. Preparar Servidor

```bash
ssh root@<ip-servidor>
apt update && apt upgrade -y
apt install -y python3.10 python3-pip python3-venv git
```

### 2. Instalar

```bash
cd /opt
git clone <repo-url> aquaflora-stock-sync
cd aquaflora-stock-sync
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env
```

### 3. Serviço Systemd (sync automático)

**`/etc/systemd/system/aquaflora-sync.service`:**

```ini
[Unit]
Description=AquaFlora Stock Sync
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/aquaflora-stock-sync
Environment=PYTHONIOENCODING=utf-8
ExecStart=/opt/aquaflora-stock-sync/venv/bin/python main.py --input data/input/Athos.csv --lite

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/aquaflora-sync.timer`:**

```ini
[Unit]
Description=Run AquaFlora Sync every 2 hours

[Timer]
OnCalendar=*-*-* 0/2:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl daemon-reload
systemctl enable aquaflora-sync.timer
systemctl start aquaflora-sync.timer
systemctl list-timers
```

### 4. Dashboard como Serviço

**`/etc/systemd/system/aquaflora-dashboard.service`:**

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
```

---

## 🐳 Opção C: Docker

```bash
cp .env.example .env
nano .env

docker compose build
docker compose up -d
docker compose logs -f
```

---

## 🔐 Segurança

- **Nunca commitar `.env`** — já está no `.gitignore`
- **Senhas fortes** para FTP e APIs
- **Rotacionar chaves** WooCommerce periodicamente
- **Firewall:** liberar apenas portas 22 (SSH) e 8000 (Dashboard)

### HTTPS (Nginx proxy reverso)

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

## 📋 Checklist de Deploy

- [ ] Python 3.10+ instalado
- [ ] Dependências instaladas
- [ ] `.env` configurado com credenciais
- [ ] Diretórios criados (`data/input`, `data/output`, `data/images`, `logs`)
- [ ] CSV do ERP copiado para `data/input/`
- [ ] Teste dry-run funcionando
- [ ] FTP testado
- [ ] Automação configurada (Timer/Cron/Task Scheduler)
- [ ] Dashboard acessível
