# 🔧 Troubleshooting - AquaFlora Stock Sync v4.1

> **Guia de resolução de problemas comuns**
> Última atualização: 27 Abril 2026

---

## 📥 Arquivo de Entrada — Qual usar?

A pasta `AthosEstoque/` (ou `data/input/`) costuma ter três arquivos:

| Arquivo | Recomendação |
|---------|--------------|
| `Athos.csv` | ✅ **Use este.** CSV limpo `;` com EAN, marca e categoria. |
| `Relatório Completo Athos.csv` | ⚠️ Use só se não tiver o limpo. SKUs longos podem ser corrompidos. |
| `Athos.rpt` | ❌ **Não suportado.** É binário do Crystal Reports — abra-o no Crystal e exporte como CSV. |

```powershell
# Correto
python main.py --input data/input/Athos.csv --lite

# Errado (vai falhar com mensagem clara)
python main.py --input data/input/Athos.rpt --lite
```

---

## 🔢 SKUs de mais de 15 dígitos são corrompidos

**Sintoma:** três produtos diferentes aparecem com o mesmo SKU no `data/output/woocommerce_*.csv`.

```
WARNING | ⚠️  Found 2 duplicate SKU(s) (5 extra rows will be discarded).
WARNING |     SKU 42127836542536000: ['FORTMAX 12MG', 'FORTMAX 3MG', 'FORTMAX 6MG']
```

**Causa:** o "Relatório Completo" passa pelo Crystal Reports/Excel, que armazena
SKUs como `float64` (precisão de ~15 dígitos significativos). Códigos como
`42127836542535989`, `...990`, `...991` são todos arredondados para
`42127836542536000`.

**Solução:**

1. Use `Athos.csv` (formato limpo) — SKUs preservados como string.
2. Se precisar do relatório longo, exporte do Crystal **direto para CSV** sem
   abrir no Excel. O parser ainda emite o aviso, mas as linhas únicas sobrevivem.

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
