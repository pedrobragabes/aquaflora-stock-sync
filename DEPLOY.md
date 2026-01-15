# Deployment Guide - AquaFlora Stock Sync

Guia para deploy no Proxmox usando LXC (recomendado) ou VM.

## Prerequisites

- Docker e Docker Compose instalados
- Arquivo `.env` configurado (copie de `.env.example`)
- Acesso às credenciais do WooCommerce e Discord

---

## Option A: LXC Container (Recommended)

LXC é mais leve e eficiente que uma VM completa.

### 1. Create LXC Container

No Proxmox Web UI:
1. **Create CT** → Template: `debian-12-standard` ou `ubuntu-22.04`
2. **Resources**: 1 CPU, 512MB RAM (mínimo), 4GB disk
3. **Network**: DHCP ou IP fixo conforme sua rede

### 2. Install Docker

```bash
# SSH into LXC
ssh root@<lxc-ip>

# Update and install Docker
apt update && apt upgrade -y
apt install -y curl git

# Install Docker (official script)
curl -fsSL https://get.docker.com | sh

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version
```

### 3. Deploy Application

```bash
# Clone repository
cd /opt
git clone <your-repo-url> aquaflora-stock-sync
cd aquaflora-stock-sync

# Configure environment
cp .env.example .env
nano .env  # Edit with your credentials

# Create required files (if not exist)
touch products.db last_run_stats.json
mkdir -p data/input data/output logs

# Start services
docker compose up -d

# Verify
docker compose ps
docker compose logs -f
```

### 4. Verify Deployment

```bash
# Check health
curl http://localhost:8080/api/status

# Check metrics (novo v2.1)
curl http://localhost:8080/metrics

# API Docs (novo v2.1)
# Acesse: http://localhost:8080/docs

# View logs
docker compose logs dashboard --tail=50
docker compose logs bot --tail=50
```

---

## Option B: Full VM

Para isolamento total ou ambiente "enterprise".

### 1. Create VM

No Proxmox Web UI:
1. **Create VM** → ISO: Debian 12 ou Ubuntu 22.04
2. **Resources**: 1 CPU, 1GB RAM, 10GB disk
3. Complete installation

### 2. Install Docker

Same as LXC (see step 2 above).

### 3. Deploy Application

Same as LXC (see step 3 above).

---

## Management Commands

```bash
# Start/Stop
docker compose up -d
docker compose down

# View logs
docker compose logs -f              # All services
docker compose logs dashboard -f    # Dashboard only
docker compose logs bot -f          # Bot only

# Restart services
docker compose restart

# Rebuild after code changes
docker compose build --no-cache
docker compose up -d

# Check status
docker compose ps
```

---

## Troubleshooting

### Bot não conecta ao Discord
```bash
# Verificar token
docker compose logs bot | grep -i "token\|login\|error"

# Token inválido? Edite .env e reinicie
docker compose restart bot
```

### Dashboard não abre
```bash
# Verificar porta
docker compose ps  # Deve mostrar 8080->8080

# Verificar healthcheck
docker compose exec dashboard curl http://localhost:8080/api/status
```

### Sync falha com API error
```bash
# Verificar credenciais WooCommerce
docker compose exec dashboard python -c "from config.settings import settings; print(settings.woo_configured)"

# Deve retornar True
```

---

## Auto-Start on Boot

Docker Compose com `restart: unless-stopped` já garante que os serviços reiniciem automaticamente após reboot do servidor.

Para verificar:
```bash
reboot
# Após reiniciar:
docker compose ps  # Ambos serviços devem estar "Up"
```
