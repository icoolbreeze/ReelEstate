# Called by scripts\make-video.cmd. Writes <Ep>\jobs\<Stage>.md from the fixed template and starts it with run_stage.ps1.
param([string]$Ep, [string]$Stage)
$R = 'C:\Users\shipi\vswp\ReelEstate'
$J = Join-Path $R "$Ep\jobs"; New-Item -ItemType Directory -Force $J | Out-Null
$scope = if ($Stage -eq 'all') { 'all stages in order, starting from the first stage whose status in episode.yaml is not done' } else { "only stage '$Stage'" }
@"
做视频: run the map-hub runbook (docs/RUNBOOK-map-hub-koubo.md) for $Ep, $scope.
Read $Ep\episode.yaml first; it is the single source of truth (listing ref, category, raw footage list, voice engine/seed/speeds, avatar, render settings).
Follow docs/FOOTAGE-SPEC.md for footage. Before each stage run python pipeline\maphub\stage.py $Ep. RESUMABLE: skip outputs that already exist and pass the stage check;
after each stage passes its check, update status.<stage>: done in episode.yaml and append a line to $Ep\jobs\progress.md.
Hard rules: only the user's own HeyGen avatar Cool Breeze and own cloned voice; never modify voices\clone\* or footage\raw\* (read-only);
one HeyGen generation per episode; no commit/push; never touch .mcp.json or .grok/. If blocked, write $Ep\jobs\BLOCKED.md and stop.
Finish with the QA report (LUFS, freezes, brand strip only, avatar uncovered) and the output path.
"@ | Set-Content -Encoding UTF8 "$J\$Stage.md"
& powershell -ExecutionPolicy Bypass -File (Join-Path $R 'scripts\maphub\run_stage.ps1') -Ep $Ep -Stage $Stage
