param(
    [string]$InputFile = "",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

Set-Location $ProjectRoot

$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$lockFile = Join-Path $logDir "sync_lite.lock"
$logFile = Join-Path $logDir ("sync_lite_{0}.log" -f (Get-Date -Format "yyyyMMdd"))

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
    if ([string]::IsNullOrWhiteSpace($InputFile)) {
        $defaultInput = Join-Path $ProjectRoot "data\input\Athos.csv"
        if (Test-Path $defaultInput) {
            $InputFile = $defaultInput
        } else {
            $latestCsv = Get-ChildItem -Path (Join-Path $ProjectRoot "data\input") -Filter "*.csv" -File |
                Sort-Object LastWriteTime -Descending |
                Select-Object -First 1

            if ($null -eq $latestCsv) {
                throw "No CSV file found in data\input."
            }

            $InputFile = $latestCsv.FullName
        }
    }

    $python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $python)) {
        $python = "python"
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
