# Create a stage prompt and launch the configured executor.
param(
  [Parameter(Mandatory=$true)][string]$Ep,
  [ValidatePattern('^[a-z][a-z0-9_-]*$')][string]$Stage='all',
  [ValidateSet('auto','claude','zcode','opencode','grok')][string]$Executor='auto',
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$R = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$episode = [IO.Path]::GetFullPath((Join-Path $R $Ep))
$roots = @('projects\listing') | ForEach-Object { [IO.Path]::GetFullPath((Join-Path $R $_)) + [IO.Path]::DirectorySeparatorChar }
if (-not ($roots | Where-Object { $episode.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) })) { throw 'Invalid episode path' }
if (-not (Test-Path (Join-Path $episode 'episode.yaml'))) { throw 'Missing episode.yaml' }
$yamlText = [IO.File]::ReadAllText((Join-Path $episode 'episode.yaml'))
$sm = [regex]::Match($yamlText, '(?m)^\s*series:\s*([a-z0-9-]+)')
if ($sm.Success -and $sm.Groups[1].Value -ne 'listing') {
  $leaf = Split-Path $episode -Leaf
  throw ("$leaf is series '$($sm.Groups[1].Value)', not listing. Use scripts\make-knowledge-video.cmd $leaf (docs/RUNBOOK-knowledge-koubo.md).")
}
$J = Join-Path $episode 'jobs'
New-Item -ItemType Directory -Force $J | Out-Null
$scope = if ($Stage -eq 'all') { 'all stages in order, starting from the first status that is not done' } else { "only stage '$Stage'" }
$prompt = @"
Run docs/RUNBOOK-map-hub-koubo.md for $Ep, $scope.
Read README.md, docs/PRODUCTION.md, docs/architecture.md, AGENTS.md and $Ep/episode.yaml first. The user retired the old project.json workflow; do not restore it. Run npm run doctor before production. Before each stage run python pipeline/maphub/stage.py $Ep.
Remotion cwd is $Ep/work/remotion, not the shared template. Each episode owns its data and outputs.
IndexTTS-2.5 is primary, F5 is an explicitly selected backup. Resolve shared presenter settings and episode overrides.
Missing cloned audio must stop. Edge and estimated captions are for drafts only; final captions need current audio timestamps.
Resume only when outputs match the current inputs and pass checks. Update episode status after a stage passes.
Render via python pipeline/maphub/render_episode.py $Ep; QA remains mandatory.
Never modify raw recordings or footage/raw. One HeyGen generation per episode. No commit or push.
Never touch .mcp.json, .grok, keys or credentials. If blocked, write jobs/BLOCKED.md with the actual error and stop.
"@
[IO.File]::WriteAllText((Join-Path $J "$Stage.md"), $prompt, (New-Object Text.UTF8Encoding $false))
& (Join-Path $R 'scripts\maphub\run_stage.ps1') -Ep $Ep -Stage $Stage -Executor $Executor -DryRun:$DryRun


