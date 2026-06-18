param(
    [string]$InputFile = "C:\Estoque\Athos.csv",
    [string]$ProjectRoot = "",
    [switch]$SkipMapSiteDaily,
    [switch]$MapSiteEveryRun
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:ZERO_GHOST_STOCK = "false"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

Set-Location $ProjectRoot

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$lockFile = Join-Path $logDir "sync_lite.lock"
$logFile = Join-Path $logDir ("sync_lite_{0}.log" -f (Get-Date -Format "yyyyMMdd"))
$mapMarkerFile = Join-Path $logDir ("map_site_{0}.ok" -f (Get-Date -Format "yyyyMMdd"))

if (Test-Path $lockFile) {
    $ageMinutes = ((Get-Date) - (Get-Item $lockFile).LastWriteTime).TotalMinutes
    if ($ageMinutes -lt 110) {
        "[$(Get-Date -Format s)] Another sync is already running. Lock: $lockFile" |
            Tee-Object -FilePath $logFile -Append
        exit 0
    }
    Remove-Item -LiteralPath $lockFile -Force
}

New-Item -ItemType File -Force -Path $lockFile | Out-Null

try {
    if (-not (Test-Path $InputFile)) {
        throw "Input CSV not found: $InputFile"
    }

    $python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        $python = "python"
    }

    if ($MapSiteEveryRun.IsPresent -or (-not $SkipMapSiteDaily.IsPresent -and -not (Test-Path $mapMarkerFile))) {
        "[$(Get-Date -Format s)] Mapping WooCommerce site before sync..." |
            Tee-Object -FilePath $logFile -Append

        & $python "main.py" --map-site 2>&1 |
            Tee-Object -FilePath $logFile -Append

        if ($LASTEXITCODE -ne 0) {
            throw "map-site exited with code $LASTEXITCODE"
        }

        New-Item -ItemType File -Force -Path $mapMarkerFile | Out-Null

        "[$(Get-Date -Format s)] WooCommerce site mapping finished." |
            Tee-Object -FilePath $logFile -Append
    }

    "[$(Get-Date -Format s)] Starting AquaFlora LITE sync: $InputFile" |
        Tee-Object -FilePath $logFile -Append

    & $python "main.py" --input $InputFile --lite 2>&1 |
        Tee-Object -FilePath $logFile -Append

    if ($LASTEXITCODE -ne 0) {
        throw "main.py exited with code $LASTEXITCODE"
    }

    "[$(Get-Date -Format s)] AquaFlora LITE sync finished." |
        Tee-Object -FilePath $logFile -Append
} catch {
    "[$(Get-Date -Format s)] ERROR: $($_.Exception.Message)" |
        Tee-Object -FilePath $logFile -Append
    exit 1
} finally {
    if (Test-Path $lockFile) {
        Remove-Item -LiteralPath $lockFile -Force
    }
}
