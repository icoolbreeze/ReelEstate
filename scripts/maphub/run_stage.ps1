# usage: powershell -ExecutionPolicy Bypass -File scripts\maphub\run_stage.ps1 -Ep projects\map-hub\ep07-xihu -Stage voice
# Runs one runbook stage as a detached headless grok job (survives remote-shell disconnects):
#   prompt = <Ep>\jobs\<Stage>.md   log = <Ep>\jobs\<Stage>.log   pid = <Ep>\jobs\<Stage>.pid
# Stage prompts are written RESUMABLE (skip outputs that already pass their checks), so re-running a stage is safe.
param([string]$Ep, [string]$Stage)
$R = 'C:\Users\shipi\vswp\ReelEstate'
$J = Join-Path $R "$Ep\jobs"; New-Item -ItemType Directory -Force $J | Out-Null
$prompt = ((Get-Content -Raw -Encoding UTF8 "$J\$Stage.md") -replace '"', "'") -replace "`r?`n", ' '
$p = Start-Process -FilePath 'C:\Users\shipi\.grok\bin\grok.exe' -ArgumentList @('-p', "`"$prompt`"", '--always-approve', '--cwd', $R) `
     -RedirectStandardOutput "$J\$Stage.log" -RedirectStandardError "$J\$Stage.err" -WindowStyle Hidden -PassThru
$p.Id | Set-Content "$J\$Stage.pid"
"started $Stage pid $($p.Id)"
