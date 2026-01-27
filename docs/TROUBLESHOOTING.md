# 🔧 Troubleshooting - AquaFlora Stock Sync

> **Guia de resolução de problemas comuns**  
> Versão: 3.3 | Atualização: 27 Janeiro 2026

---

## 📋 Índice

1. [Erros de Encoding](#-erros-de-encoding)
2. [Problemas com Imagens](#-problemas-com-imagens)
3. [Erros de API](#-erros-de-api)
4. [Problemas de FTP](#-problemas-de-ftp)
5. [Dashboard não Funciona](#-dashboard-não-funciona)
6. [Scraper não Encontra Imagens](#-scraper-não-encontra-imagens)
7. [CSV não Importa no WooCommerce](#-csv-não-importa-no-woocommerce)
8. [Erros de Memória](#-erros-de-memória)
9. [Problemas com Docker](#-problemas-com-docker)
10. [Cobertura Baixa](#-cobertura-baixa)

---

## 🔤 Erros de Encoding

### Sintoma

```
UnicodeEncodeError: 'charmap' codec can't encode character
```

### Causa

Windows usa encoding diferente de UTF-8 por padrão.

### Solução

```powershell
# Definir antes de executar qualquer comando
$env:PYTHONIOENCODING="utf-8"

# Ou adicionar no início do script
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

### Solução Permanente

Adicionar variável de ambiente do sistema:

1. Configurações → Sistema → Sobre → Configurações avançadas
2. Variáveis de ambiente
3. Nova variável: `PYTHONIOENCODING` = `utf-8`

---

## 🖼️ Problemas com Imagens

### Imagem não encontrada no export

**Sintoma:** CSV gerado sem URLs de imagem para produtos que têm imagem.

**Verificar:**

```powershell
# Listar imagens de um SKU
Get-ChildItem -Recurse data/images -Filter "7898242033022*"
```

**Causas possíveis:**

1. Imagem está em pasta errada
2. Extensão não suportada
3. Nome do arquivo não é exatamente o SKU

**Solução:**

```powershell
# Renomear para padrão correto
Rename-Item "7898242033022_foto.jpg" "7898242033022.jpg"

# Mover para pasta correta
Move-Item "7898242033022.jpg" "data/images/pet/"
```

### Imagem corrompida

**Sintoma:** Erro ao processar imagem.

**Solução:**

```powershell
# Deletar e rebuscar
Remove-Item "data/images/pet/7898242033022.jpg"
python scrape_all_images.py --only-missing-images --cheap
```

### Baixa cobertura em departamento

**Sintoma:** Departamento com muitas imagens faltando.

**Diagnóstico:**

```powershell
python analyze_missing_products.py
```

**Soluções:**

1. Verificar se produtos têm marca detectada
2. Considerar excluir departamento genérico
3. Buscar imagens manualmente para produtos específicos

---

## 🌐 Erros de API

### DuckDuckGo - RatelimitException

**Sintoma:**

```
duckduckgo_search.exceptions.RatelimitException
```

**Causa:** Muitas requisições em pouco tempo.

**Solução:**

```powershell
# Usar menos workers
python scrape_all_images.py --cheap --workers 1

# Ou esperar alguns minutos e tentar novamente
```

### Google API - Quota exceeded

**Sintoma:**

```
HttpError 429: Quota exceeded
```

**Causa:** Limite diário de 100 buscas atingido.

**Soluções:**

1. Usar modo cheap: `--cheap`
2. Esperar 24h para reset da quota
3. Criar nova API key (projeto diferente)

### Vision AI - Permission denied

**Sintoma:**

```
403 Permission Denied
```

**Verificar:**

1. API Vision habilitada no Google Cloud Console
2. Billing ativo na conta
3. API key tem permissão para Vision API

---

## 📤 Problemas de FTP

### Connection refused

**Sintoma:**

```
ftplib.error_temp: 421 Too many connections
```

**Solução:**

```powershell
# Esperar e tentar novamente
Start-Sleep -Seconds 30
python upload_images.py
```

### Login incorrect

**Sintoma:**

```
ftplib.error_perm: 530 Login incorrect
```

**Verificar:**

1. Usuário e senha corretos no `.env`
2. Usuário tem permissão FTP no Hostinger
3. IP não está bloqueado

### Timeout

**Sintoma:**

```
TimeoutError: [WinError 10060]
```

**Solução no .env:**

```env
FTP_TIMEOUT=120
FTP_PASSIVE=true
```

---

## 🌐 Dashboard não Funciona

### Porta em uso

**Sintoma:**

```
ERROR: [Errno 10048] Port 8000 already in use
```

**Solução Windows:**

```powershell
# Encontrar processo
netstat -ano | findstr :8000

# Matar processo (substituir PID)
taskkill /PID 12345 /F

# Ou usar porta diferente
uvicorn dashboard.app:app --port 8001
```

### Module not found

**Sintoma:**

```
ModuleNotFoundError: No module named 'fastapi'
```

**Solução:**

```powershell
# Ativar venv e reinstalar
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 🔍 Scraper não Encontra Imagens

### Nenhum resultado

**Sintoma:** Scraper roda mas não encontra imagens.

**Verificar query:**

```powershell
# Testar busca manual
python -c "from duckduckgo_search import DDGS; print(list(DDGS().images('Alcon Carniboros 300g', max_results=3)))"
```

**Possíveis causas:**

1. Produto muito específico/raro
2. Nome sem marca
3. API temporariamente indisponível

**Soluções:**

1. Usar modo premium (Google + Vision)
2. Buscar manualmente e salvar em `data/images/`
3. Adicionar sinônimos na query

### Vision AI rejeita todas

**Sintoma:** Imagens baixadas mas rejeitadas pela Vision AI.

**Verificar:**

```powershell
# Ver cache de rejeições
Get-Content data/vision_cache.json | ConvertFrom-Json
```

**Solução:**

```powershell
# Usar modo cheap (sem Vision)
python scrape_all_images.py --cheap
```

### Timeout em produtos

**Sintoma:**

```
⏰ TIMEOUT (>60s) - skipping SKU
```

**Causa:** Download lento ou servidor não responde.

**Solução:**

```powershell
# Produtos com timeout vão para lista de falhas
# Reprocessar depois com:
python scrape_all_images.py --only-failed --cheap
```

---

## 📊 CSV não Importa no WooCommerce

### Encoding incorreto

**Sintoma:** Caracteres estranhos nos nomes.

**Solução:**

- Abrir CSV no Excel com encoding UTF-8
- Ou usar plugin de importação com opção "UTF-8"

### Campos não mapeiam

**Sintoma:** WooCommerce não reconhece colunas.

**Verificar:**

- Nome das colunas deve ser exato
- Primeira linha deve ser header
- Separador é vírgula (não ponto-e-vírgula)

### SKU duplicado

**Sintoma:**

```
Error: SKU already exists
```

**Soluções:**

1. Usar modo "Atualizar produtos existentes"
2. Deletar produtos antigos antes

---

## 💾 Erros de Memória

### MemoryError

**Sintoma:**

```
MemoryError
```

**Soluções:**

1. **Processar em lotes:**

```powershell
python scrape_all_images.py --limit 500
# Depois
python scrape_all_images.py --skip-existing --limit 500
```

2. **Menos workers:**

```powershell
python scrape_all_images.py --workers 1
```

3. **Aumentar swap (Linux):**

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 🐳 Problemas com Docker

### Build falha

**Sintoma:**

```
ERROR: failed to solve: failed to fetch
```

**Soluções:**

```bash
# Limpar cache
docker system prune -a

# Rebuild sem cache
docker compose build --no-cache
```

### Container não inicia

**Sintoma:**

```
Exited (1)
```

**Verificar logs:**

```bash
docker compose logs app
```

### Volume não persiste

**Verificar docker-compose.yml:**

```yaml
volumes:
  - ./data:/app/data
  - ./logs:/app/logs
```

---

## 📉 Cobertura Baixa

### Departamento com cobertura < 30%

**Sintoma:** `analyze_missing_products.py` mostra departamento como FERRAMENTAS com 11.5%.

**Diagnóstico:**

```powershell
python analyze_missing_products.py
```

**Soluções:**

1. **Excluir departamento temporariamente:**

```json
// config/exclusion_list.json
{
  "exclude_departments": ["FERRAMENTAS"]
}
```

2. **Melhorar queries de busca:**
   - Verificar se produtos têm marca detectada
   - Adicionar novas marcas em `config/brands.json`

3. **Buscar manualmente:**
   - Identificar produtos específicos no relatório
   - Buscar imagens manualmente e salvar em pasta correta

### Produtos falhando repetidamente

**Sintoma:** Mesmos SKUs sempre falham no scraper.

**Verificar:**

```powershell
# Ver relatório de falhas
Get-Content data/missing_products_report.json | ConvertFrom-Json | Select-Object -ExpandProperty failed_products | Select-Object -First 20
```

**Soluções:**

1. Verificar se são produtos genéricos (kits, combos)
2. Adicionar à lista de exclusão
3. Buscar imagens manualmente

---

## 📞 Quando Pedir Ajuda

Se nenhuma solução funcionou, forneça:

1. **Versão do sistema:**

```powershell
python --version
pip freeze | Select-String "fastapi|pydantic|requests"
```

2. **Erro completo:**

```powershell
python main.py 2>&1 | Tee-Object error.log
```

3. **Configuração (sem senhas!):**

```powershell
Get-Content .env | Select-String -NotMatch "KEY|SECRET|PASSWORD"
```

4. **Últimos logs:**

```powershell
Get-Content logs\*.log -Tail 50
```

5. **Relatório de cobertura:**

```powershell
python analyze_missing_products.py
```

---

## 🔄 Reset Completo

Se tudo mais falhar, reset para estado limpo:

```powershell
# CUIDADO: Isso apaga dados!

# 1. Backup primeiro
Compress-Archive data, products.db, .env -DestinationPath backup.zip

# 2. Limpar estado
Remove-Item products.db -ErrorAction SilentlyContinue
Remove-Item data\scraper_progress.json -ErrorAction SilentlyContinue
Remove-Item data\vision_cache.json -ErrorAction SilentlyContinue
Remove-Item data\search_cache.json -ErrorAction SilentlyContinue
Remove-Item data\missing_products_report.json -ErrorAction SilentlyContinue
Remove-Item logs\*.log -ErrorAction SilentlyContinue
Remove-Item data\reports\*.json -ErrorAction SilentlyContinue
Remove-Item data\reports\*.md -ErrorAction SilentlyContinue

# 3. Reinstalar dependências
Remove-Item -Recurse venv
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 4. Testar
python main.py --dry-run --input data/input/Athos.csv
```
