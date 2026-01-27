# AquaFlora Stock Sync - Comandos PowerShell
# Uso: .\tasks.ps1 <comando>

param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'install', 'sync', 'sync-real', 'sync-lite', 'scrape', 'scrape-all', 'scrape-stock', 'upload', 'upload-real', 'analyze', 'test', 'dashboard', 'bot', 'clean')]
    [string]$Command = 'help'
)

$InputFile = "data/input/Athos.csv"

function Show-Help {
    Write-Host ""
    Write-Host "  AquaFlora Stock Sync - Comandos Disponiveis" -ForegroundColor Cyan
    Write-Host "  ============================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  .\tasks.ps1 install     " -NoNewline -ForegroundColor Yellow; Write-Host "- Instalar dependencias"
    Write-Host "  .\tasks.ps1 sync        " -NoNewline -ForegroundColor Yellow; Write-Host "- Sincronizar estoque (dry-run)"
    Write-Host "  .\tasks.ps1 sync-real   " -NoNewline -ForegroundColor Yellow; Write-Host "- Sincronizar estoque (producao)"
    Write-Host "  .\tasks.ps1 sync-lite   " -NoNewline -ForegroundColor Yellow; Write-Host "- Sync apenas preco/estoque"
    Write-Host "  .\tasks.ps1 scrape      " -NoNewline -ForegroundColor Yellow; Write-Host "- Buscar imagens (limite 50)"
    Write-Host "  .\tasks.ps1 scrape-all  " -NoNewline -ForegroundColor Yellow; Write-Host "- Buscar todas as imagens"
    Write-Host "  .\tasks.ps1 scrape-stock" -NoNewline -ForegroundColor Yellow; Write-Host "- Buscar imagens (so com estoque)"
    Write-Host "  .\tasks.ps1 upload      " -NoNewline -ForegroundColor Yellow; Write-Host "- Upload imagens FTP (dry-run)"
    Write-Host "  .\tasks.ps1 upload-real " -NoNewline -ForegroundColor Yellow; Write-Host "- Upload imagens FTP (producao)"
    Write-Host "  .\tasks.ps1 analyze     " -NoNewline -ForegroundColor Yellow; Write-Host "- Analisar produtos sem imagem"
    Write-Host "  .\tasks.ps1 test        " -NoNewline -ForegroundColor Yellow; Write-Host "- Rodar testes"
    Write-Host "  .\tasks.ps1 dashboard   " -NoNewline -ForegroundColor Yellow; Write-Host "- Iniciar dashboard web"
    Write-Host "  .\tasks.ps1 bot         " -NoNewline -ForegroundColor Yellow; Write-Host "- Iniciar bot Discord"
    Write-Host "  .\tasks.ps1 clean       " -NoNewline -ForegroundColor Yellow; Write-Host "- Limpar cache"
    Write-Host ""
}

switch ($Command) {
    'help' { Show-Help }
    
    'install' {
        Write-Host "📦 Instalando dependencias..." -ForegroundColor Green
        python -m pip install -r requirements.txt
    }
    
    'sync' {
        Write-Host "🔄 Sincronizando estoque (DRY-RUN)..." -ForegroundColor Yellow
        python main.py --input $InputFile --dry-run
    }
    
    'sync-real' {
        Write-Host "🚀 Sincronizando estoque (PRODUCAO)..." -ForegroundColor Red
        python main.py --input $InputFile
    }
    
    'sync-lite' {
        Write-Host "⚡ Sync lite (preco/estoque)..." -ForegroundColor Cyan
        python main.py --input $InputFile --lite
    }
    
    'scrape' {
        Write-Host "🔍 Buscando imagens (limite 50)..." -ForegroundColor Green
        python scrape_all_images.py --limit 50
    }
    
    'scrape-all' {
        Write-Host "🔍 Buscando TODAS as imagens..." -ForegroundColor Yellow
        python scrape_all_images.py
    }
    
    'scrape-stock' {
        Write-Host "🔍 Buscando imagens (produtos com estoque)..." -ForegroundColor Green
        python scrape_all_images.py --stock-only
    }
    
    'upload' {
        Write-Host "📤 Upload imagens (DRY-RUN)..." -ForegroundColor Yellow
        python upload_images.py --dry-run
    }
    
    'upload-real' {
        Write-Host "📤 Upload imagens (PRODUCAO)..." -ForegroundColor Red
        python upload_images.py
    }
    
    'analyze' {
        Write-Host "📊 Analisando produtos sem imagem..." -ForegroundColor Cyan
        python scripts/analyze_missing_products.py
    }
    
    'test' {
        Write-Host "🧪 Rodando testes..." -ForegroundColor Green
        python -m pytest tests/ -v
    }
    
    'dashboard' {
        Write-Host "🌐 Iniciando dashboard..." -ForegroundColor Cyan
        python -m dashboard.app
    }
    
    'bot' {
        Write-Host "🤖 Iniciando bot Discord..." -ForegroundColor Magenta
        python bot_control.py
    }
    
    'clean' {
        Write-Host "🧹 Limpando cache..." -ForegroundColor Yellow
        if (Test-Path "data/search_cache.json") { Remove-Item "data/search_cache.json" -Force }
        if (Test-Path "__pycache__") { Remove-Item "__pycache__" -Recurse -Force }
        if (Test-Path "src/__pycache__") { Remove-Item "src/__pycache__" -Recurse -Force }
        if (Test-Path "tests/__pycache__") { Remove-Item "tests/__pycache__" -Recurse -Force }
        if (Test-Path "config/__pycache__") { Remove-Item "config/__pycache__" -Recurse -Force }
        if (Test-Path "dashboard/__pycache__") { Remove-Item "dashboard/__pycache__" -Recurse -Force }
        Write-Host "✅ Cache limpo!" -ForegroundColor Green
    }
}
