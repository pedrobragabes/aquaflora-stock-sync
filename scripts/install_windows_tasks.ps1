param(
    [string]$ProjectRoot = "",
    [string]$InputFile = "C:\Estoque\Athos.csv",
    [string]$TaskName = "AquaFlora Stock Sync LITE",
    [int]$IntervalHours = 2,
    [switch]$AtStartup
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

$runScript = Join-Path $ProjectRoot "scripts\run_sync_lite.ps1"
if (-not (Test-Path $runScript)) {
    throw "Run script not found: $runScript"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runScript`" -ProjectRoot `"$ProjectRoot`" -InputFile `"$InputFile`""

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

$repetition = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Hours $IntervalHours) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$triggers = @($repetition)
if ($AtStartup) {
    $triggers += New-ScheduledTaskTrigger -AtStartup
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Principal $principal `
    -Settings $settings `
    -Description "Runs AquaFlora WooCommerce LITE sync every $IntervalHours hours. LITE updates price and stock only." `
    -Force | Out-Null

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Project root: $ProjectRoot"
Write-Host "Input CSV: $InputFile"
Write-Host "Interval: every $IntervalHours hours"
Write-Host "At logon: $($AtStartup.IsPresent)"
Write-Host "Test now with:"
Write-Host "  Start-ScheduledTask -TaskName `"$TaskName`""
