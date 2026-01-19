# 🚀 Guia de Deploy - AquaFlora Stock Sync v3.0

> **Guia completo para deploy em produção**  
> Última atualização: 19 Janeiro 2026

---

## 📋 Pré-requisitos

- Servidor Linux (Debian/Ubuntu) ou LXC Container
- Docker e Docker Compose instalados
- 1 CPU, 1GB RAM, 10GB disco (mínimo)
- Acesso às APIs: WooCommerce, Google Cloud

---

## 🔧 Opção A: LXC Container (Recomendado)

### 1. Criar Container no Proxmox

```
Proxmox → Create CT
- Template: debian-12-standard ou ubuntu-22.04
- Resources: 1 CPU, 1GB RAM, 8GB disk
- Network: DHCP ou IP fixo
```

### 2. Instalar Docker

```bash
# SSH no container
ssh root@<lxc-ip>

# Atualizar sistema
apt update && apt upgrade -y
apt install -y curl git

# Instalar Docker (script oficial)
curl -fsSL https://get.docker.com | sh

# Instalar Docker Compose plugin
apt install -y docker-compose-plugin

# Verificar instalação
docker --version
docker compose version
```

### 3. Clonar Projeto

```bash
cd /opt
git clone <seu-repo-url> aquaflora-stock-sync
cd aquaflora-stock-sync
```

### 4. Configurar Ambiente

```bash
# Copiar template
cp .env.example .env

# Editar credenciais
nano .env
```

**Configurações obrigatórias no .env:**

```env
# WooCommerce
WOO_URL=https://sualoja.com.br
WOO_CONSUMER_KEY=ck_xxx
WOO_CONSUMER_SECRET=cs_xxx

# Google APIs
GOOGLE_API_KEY=AIzaSy...
GOOGLE_SEARCH_ENGINE_ID=75f6d255f...
VISION_AI_ENABLED=true

# Produção
DRY_RUN=false
SYNC_ENABLED=true
```

### 5. Preparar Arquivos

```bash
# Criar diretórios necessários
mkdir -p data/input data/output data/images logs

# Criar arquivos vazios (se não existem)
touch products.db last_run_stats.json

# Copiar CSV do ERP
scp usuario@local:Athos.csv /opt/aquaflora-stock-sync/data/input/
```

### 6. Iniciar Serviços

```bash
# Build e start
docker compose up -d

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f
```

### 7. Verificar Deploy

```bash
# Health check
curl http://localhost:8080/api/status

# Métricas
curl http://localhost:8080/metrics

# Swagger UI
# Acesse: http://<ip>:8080/docs
```

---

## 🖼️ Image Scraper em Produção

### Executar Manualmente

```bash
# Entrar no container
docker compose exec dashboard bash

# Rodar scraper (dentro do container)
python scrape_all_images.py --stock-only
```

### Executar via Docker Run

```bash
# One-shot (não precisa entrar no container)
docker compose run --rm dashboard python scrape_all_images.py --stock-only
```

### Opções do Scraper

| Flag           | Descrição                   |
| -------------- | --------------------------- |
| `--stock-only` | Só produtos com estoque > 0 |
| `--limit N`    | Limitar a N produtos        |
| `--reset`      | Recomeçar do zero           |

### Custos Estimados

| Cenário        | Produtos | Custo Estimado |
| -------------- | -------- | -------------- |
| Só com estoque | ~3.200   | R$ 86          |
| Todos válidos  | ~4.100   | R$ 112         |

_Baseado em Vision AI $1.50/1000 imagens (~R$0.027/imagem)_

---

## ⏰ Agendamento com Cron

### Sync Diário

```bash
# Editar crontab
crontab -e

# Sync às 11h todos os dias
0 11 * * * cd /opt/aquaflora-stock-sync && docker compose run --rm dashboard python main.py --input data/input/Athos.csv --lite >> logs/cron.log 2>&1
```

### Scraper Semanal

```bash
# Executar domingo às 3h
0 3 * * 0 cd /opt/aquaflora-stock-sync && docker compose run --rm dashboard python scrape_all_images.py --stock-only >> logs/scraper_cron.log 2>&1
```

### Upload Automático do CSV

Se o ERP puder enviar o CSV via FTP/SFTP:

```bash
# Instalar inotify-tools
apt install -y inotify-tools

# Script de watch
cat > /opt/aquaflora-stock-sync/watch_input.sh << 'EOF'
#!/bin/bash
inotifywait -m /opt/aquaflora-stock-sync/data/input -e create -e moved_to |
while read dir action file; do
    if [[ "$file" == *.csv ]]; then
        echo "$(date): Novo arquivo detectado: $file"
        cd /opt/aquaflora-stock-sync
        docker compose run --rm dashboard python main.py --input "data/input/$file" --lite
    fi
done
EOF

chmod +x /opt/aquaflora-stock-sync/watch_input.sh
```

---

## 📊 Monitoramento

### Ver Logs

```bash
# Todos os serviços
docker compose logs -f

# Dashboard apenas
docker compose logs dashboard -f

# Bot apenas
docker compose logs bot -f

# Últimas 100 linhas
docker compose logs --tail=100
```

### Métricas Prometheus

O endpoint `/metrics` fornece:

```
# Exemplo de métricas
aquaflora_syncs_total 150
aquaflora_syncs_success 148
aquaflora_syncs_failed 2
aquaflora_products_updated 12500
aquaflora_last_sync_duration_seconds 45.2
```

### Integrar com Grafana

1. Adicione Prometheus como data source
2. Importe dashboard ou crie painéis com as métricas

---

## 🔄 Comandos de Manutenção

### Restart Serviços

```bash
# Restart todos
docker compose restart

# Restart específico
docker compose restart dashboard
docker compose restart bot
```

### Atualizar Código

```bash
# Parar serviços
docker compose down

# Atualizar código
git pull

# Rebuild e restart
docker compose build --no-cache
docker compose up -d
```

### Backup

```bash
# Backup do banco
cp products.db products.db.backup

# Backup das imagens
tar -czf images_backup.tar.gz data/images/

# Backup completo
tar -czf aquaflora_backup_$(date +%Y%m%d).tar.gz \
    products.db \
    data/images/ \
    data/scraper_progress.json \
    .env
```

### Limpar Espaço

```bash
# Limpar logs antigos
find logs/ -name "*.log" -mtime +30 -delete

# Limpar cache Docker
docker system prune -af
```

---

## 🔒 Segurança

### Firewall (UFW)

```bash
# Permitir SSH
ufw allow 22

# Permitir Dashboard (apenas rede local)
ufw allow from 192.168.0.0/24 to any port 8080

# Ativar
ufw enable
```

### Autenticação Dashboard

No `.env`:

```env
DASHBOARD_AUTH_ENABLED=true
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=sua_senha_forte
```

### HTTPS com Nginx

```bash
# Instalar Nginx
apt install -y nginx certbot python3-certbot-nginx

# Configurar proxy reverso
cat > /etc/nginx/sites-available/aquaflora << 'EOF'
server {
    listen 80;
    server_name aquaflora.seudominio.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/aquaflora /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Obter certificado SSL
certbot --nginx -d aquaflora.seudominio.com
```

---

## 🐛 Troubleshooting

### Container não inicia

```bash
# Ver logs de erro
docker compose logs dashboard

# Verificar configuração
docker compose config

# Testar manualmente
docker compose run --rm dashboard python -c "from config.settings import settings; print(settings.woo_configured)"
```

### Erro de conexão WooCommerce

```bash
# Testar API
docker compose exec dashboard python -c "
from src.sync import WooSyncManager
from config.settings import settings
sync = WooSyncManager(settings.woo_url, settings.woo_consumer_key, settings.woo_consumer_secret)
print('OK')
"
```

### Imagens não são baixadas

```bash
# Verificar API Key
docker compose exec dashboard python -c "
from src.image_scraper import GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID
print(f'API Key: {bool(GOOGLE_API_KEY)}')
print(f'Search ID: {bool(GOOGLE_SEARCH_ENGINE_ID)}')
"

# Testar busca
docker compose exec dashboard python -c "
from src.image_scraper import search_images_google
r = search_images_google('coleira cachorro', max_results=1)
print(f'Resultados: {len(r)}')
"
```

### Disco cheio

```bash
# Ver uso
df -h

# Limpar Docker
docker system prune -af

# Limpar logs
truncate -s 0 logs/*.log
```

---

## ✅ Checklist de Deploy

- [ ] Container/VM criado
- [ ] Docker instalado
- [ ] Projeto clonado
- [ ] .env configurado
- [ ] CSV do ERP copiado
- [ ] `docker compose up -d`
- [ ] Dashboard acessível
- [ ] API status OK
- [ ] Scraper testado
- [ ] Cron configurado
- [ ] Backup automático

---

## 📞 Suporte

| Problema           | Verificar             |
| ------------------ | --------------------- |
| Serviço não inicia | `docker compose logs` |
| Erro de API        | Credenciais no .env   |
| Imagens não baixam | API Key do Google     |
| Sync falha         | Logs + PriceGuard     |

---

_Guia de Deploy v3.0 - AquaFlora Stock Sync_
