# Detach one stage. Auto fallback is only allowed before any executor has started.
param(
  [Parameter(Mandatory=$true)][string]$Ep,
  [Parameter(Mandatory=$true)][ValidatePattern('^[a-z][a-z0-9_-]*$')][string]$Stage,
  [ValidateSet('auto','claude','zcode','opencode','grok')][string]$Executor = 'auto',
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$R = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$episode = [IO.Path]::GetFullPath((Join-Path $R $Ep))
$series = [IO.Path]::GetFullPath((Join-Path $R 'projects\map-hub')) + [IO.Path]::DirectorySeparatorChar
if (-not $episode.StartsWith($series, [StringComparison]::OrdinalIgnoreCase)) { throw 'Episode must be inside projects/map-hub' }
$J = Join-Path $episode 'jobs'
$taskFile = Join-Path $J "$Stage.md"
if (-not (Test-Path $taskFile -PathType Leaf)) { throw "Missing task file: $taskFile" }
if ($Executor -eq 'auto' -and $env:REEL_AGENT_EXECUTOR) { $Executor = $env:REEL_AGENT_EXECUTOR.ToLowerInvariant() }
if ($Executor -notin @('auto','claude','zcode','opencode','grok')) { throw 'Invalid REEL_AGENT_EXECUTOR' }
$order = if ($Executor -eq 'auto') { @('claude','zcode','opencode') } else { @($Executor) }
$selected = $null; $exe = $null
foreach ($name in $order) {
  $override = [Environment]::GetEnvironmentVariable(('REEL_' + $name.ToUpperInvariant() + '_BIN'))
  $candidate = if ($override) { Get-Command $override -CommandType Application -ErrorAction SilentlyContinue } else { Get-Command $name -CommandType Application -ErrorAction SilentlyContinue }
  if ($candidate) { $selected = $name; $exe = $candidate.Source; break }
}
if (-not $exe) { throw "No available executor: $($order -join ', '). Configure PATH or REEL_<EXECUTOR>_BIN." }
$prompt = '"Read and execute the task in ' + $taskFile + '. Follow AGENTS.md. Work in ' + $R + '."'
$argv = switch ($selected) {
  'claude' { @('-p', $prompt, '--permission-mode', 'bypassPermissions', '--output-format', 'json') }
  'zcode' { @('-p', $prompt, '--mode', 'yolo', '--cwd', ('"' + $R + '"')) }
  'opencode' { @('run', '--format', 'json', $prompt) }
  'grok' { @('-p', $prompt, '--always-approve', '--cwd', ('"' + $R + '"')) }
}
$record = @{ executor=$selected; cwd=$R; stage=$Stage; task_file=$taskFile; status='planned' }
if ($DryRun) { $record | ConvertTo-Json -Compress; exit 0 }
$pidFile = Join-Path $J "$Stage.pid"
if (Test-Path $pidFile) {
  $oldPid = [int](Get-Content $pidFile)
  if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { throw "Stage already running: PID $oldPid" }
}
if ([IO.Path]::GetExtension($exe) -in @(".cmd", ".bat")) {
  $native = '""' + $exe + '" ' + ($argv -join ' ') + '"'
  $argv = @('/d', '/s', '/c', $native)
  $exe = $env:ComSpec
}
$p = Start-Process -FilePath $exe -ArgumentList $argv -WorkingDirectory $R -WindowStyle Hidden -PassThru `
     -RedirectStandardOutput (Join-Path $J "$Stage.log") -RedirectStandardError (Join-Path $J "$Stage.err")
[IO.File]::WriteAllText($pidFile, [string]$p.Id, (New-Object Text.UTF8Encoding $false))
$record.pid = $p.Id; $record.status = 'started'
[IO.File]::WriteAllText((Join-Path $J "$Stage.job.json"), ($record | ConvertTo-Json), (New-Object Text.UTF8Encoding $false))
"started $Stage executor=$selected pid=$($p.Id)"
