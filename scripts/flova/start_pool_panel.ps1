# Start the Flova pool panel and open it in the browser.
# If it is already listening, only open the browser.
# ASCII on purpose: Windows PowerShell 5.1 reads a no-BOM script as ANSI.
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $root

$python = @(
    "C:\ProgramData\miniconda3\python.exe",
    "C:\Python313\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) { $python = "python" }

$portreg = Join-Path $env:USERPROFILE ".config\port-registry\portreg.py"

function Get-PoolPort {
    if (-not (Test-Path $portreg)) { return $null }
    $lines = & $python $portreg list 2>$null
    foreach ($line in @($lines)) {
        $text = "$line"
        $parts = ($text -split "\s+")
        if ($parts.Length -ge 3 -and $parts[1] -eq "flova-pool" -and $parts[2] -eq "ReelEstate") {
            return [int]$parts[0]
        }
    }
    return $null
}

function Test-Listening([int]$port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $wait = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        if (-not $wait.AsyncWaitHandle.WaitOne(400)) { return $false }
        $client.EndConnect($wait)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Wait-IfFailed([string]$reason) {
    Write-Host ""
    Write-Host $reason
    Read-Host "Press Enter to close"
    exit 1
}

try {
    $existing = Get-PoolPort
    if ($existing -and (Test-Listening $existing)) {
        Start-Process "http://127.0.0.1:${existing}/"
        exit 0
    }
} catch {
    Wait-IfFailed ("Startup failed: " + $_.Exception.Message)
}

$script:opened = $false
$script:failed = $false
& $python -u (Join-Path $root "scripts\flova\pool_panel.py") 2>&1 | ForEach-Object {
    $line = "$_"
    Write-Host $line
    if ($line -match "Traceback|WinError|bind failed") { $script:failed = $true }
    if (-not $script:failed -and -not $script:opened -and $line -match "(http://127\.0\.0\.1:\d+/)") {
        Start-Process $Matches[1]
        $script:opened = $true
    }
}
if ($script:failed -or $LASTEXITCODE) {
    Wait-IfFailed "Startup failed. The panel is not running. The reason is above."
}
