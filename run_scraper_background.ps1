# AquaFlora - Run Scraper in Background (Windows)
# Roda o scraper em background, livre do terminal

param(
    [switch]$StockOnly,
    [int]$Limit = 0,
    [switch]$Reset
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "scrape_all_images.py"
$LogFile = Join-Path $ScriptDir "logs\scraper_background.log"

# Build arguments
$Args = @()
if ($StockOnly) { $Args += "--stock-only" }
if ($Limit -gt 0) { $Args += "--limit", $Limit }
if ($Reset) { $Args += "--reset" }

# Ensure log directory exists
$LogDir = Join-Path $ScriptDir "logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Write-Host "🚀 Starting scraper in background..." -ForegroundColor Green
Write-Host "📄 Log file: $LogFile" -ForegroundColor Cyan
Write-Host "💡 To monitor: Get-Content '$LogFile' -Wait -Tail 20" -ForegroundColor Yellow
Write-Host ""

# Run in background with hidden window
$ProcessArgs = "-NoProfile -ExecutionPolicy Bypass -Command `"cd '$ScriptDir'; python '$PythonScript' $($Args -join ' ') 2>&1 | Tee-Object -FilePath '$LogFile'`""

Start-Process powershell -ArgumentList $ProcessArgs -WindowStyle Hidden

Write-Host "✅ Scraper started in background!" -ForegroundColor Green
Write-Host ""
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  - Monitor logs:  Get-Content '$LogFile' -Wait -Tail 20"
Write-Host "  - Check status:  (Get-Content data/scraper_progress.json | ConvertFrom-Json).stats"
Write-Host "  - Stop scraper:  Get-Process python | Where-Object {`$_.Path -like '*python*'} | Stop-Process"
