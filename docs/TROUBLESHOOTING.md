# 🔧 Troubleshooting - AquaFlora Stock Sync v4.0

> **Guia de resolução de problemas comuns**
> Última atualização: 16 Fevereiro 2026

---

## 🔤 Erros de Encoding

```
UnicodeEncodeError: 'charmap' codec can't encode character
```

**Solução:**

```powershell
$env:PYTHONIOENCODING="utf-8"
```

**Permanente:** Adicionar variável de ambiente do sistema `PYTHONIOENCODING=utf-8`.

---

## 🖼️ Imagem não Encontrada no Export

CSV sem URL para produto que tem imagem.

**Verificar:**

```powershell
Get-ChildItem -Recurse data/images -Filter "SKU_AQUI*"
```

**Causas:** pasta errada, extensão não suportada, nome ≠ SKU.

---

## 🌐 DuckDuckGo - RatelimitException

```powershell
# Usar menos workers
python scrape_all_images.py --cheap --workers 1
```

---

## 🌐 Google API - Quota Exceeded

- Usar `--cheap` (DuckDuckGo/Bing)
- Esperar 24h para reset
- Criar nova API key

---

## 📤 FTP - Connection Refused / Timeout

```env
# Aumentar timeout no .env
FTP_TIMEOUT=120
FTP_PASSIVE=true
```

---

## 🌐 Dashboard - Porta em Uso

```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
# ou
uvicorn dashboard.app:app --port 8001
```

---

## 📊 CSV não Importa no WooCommerce

- Encoding: abrir com UTF-8
- Colunas: nomes devem ser exatos
- Separador: vírgula (não ponto-e-vírgula)
- SKU duplicado: usar "Atualizar existentes"

---

## 💾 MemoryError

```powershell
python scrape_all_images.py --limit 500 --workers 1
```

---

## 🐳 Docker - Build Falha

```bash
docker system prune -a
docker compose build --no-cache
```

---

## 🔄 Reset Completo

```powershell
# 1. Backup
Compress-Archive data, products.db, .env -DestinationPath backup.zip

# 2. Limpar estado
Remove-Item products.db, data\scraper_progress.json, data\vision_cache.json, data\search_cache.json -ErrorAction SilentlyContinue
Remove-Item logs\*.log -ErrorAction SilentlyContinue

# 3. Reinstalar
Remove-Item -Recurse venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Testar
python main.py --dry-run --input data/input/Athos.csv
```

---

## 📞 Informações para Debug

```powershell
python --version
pip freeze | Select-String "fastapi|pydantic|requests"
Get-Content .env | Select-String -NotMatch "KEY|SECRET|PASSWORD"
Get-Content logs\*.log -Tail 50
```
