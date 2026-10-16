<#
.SYNOPSIS
    Tests for tasks/run-sentinel.ps1, the -MaxIdleHours / -WriteWatermark parts of
    tasks/fast-sentinel-gate.ps1, tasks/render-sentinel-sidecars.ps1 and the real
    tasks/sentinels.json manifest. No model, no network, no live sidecar is touched.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$wrapper = Join-Path $PSScriptRoot "run-sentinel.ps1"
$gate = Join-Path $PSScriptRoot "fast-sentinel-gate.ps1"
$renderer = Join-Path $PSScriptRoot "render-sentinel-sidecars.ps1"
$realManifestPath = Join-Path $PSScriptRoot "sentinels.json"

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("run-sentinel-test-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$lockDir = Join-Path $repoRoot ".loop-logs"

$pass = 0
$fail = 0
function Assert-Test([string]$Name, [bool]$Condition, [string]$Details = "") {
    if ($Condition) { Write-Host "PASS: $Name" -ForegroundColor Green; $script:pass++ }
    else { Write-Host "FAIL: $Name - $Details" -ForegroundColor Red; $script:fail++ }
}

# ---- fixtures -------------------------------------------------------------------------------
$sentinel = "rs-test-" + [guid]::NewGuid().ToString("N").Substring(0, 6)
$lockPath = Join-Path $lockDir "sentinel-$sentinel.lock"
$wmPath = Join-Path $tmp "wm.json"
$runLog = Join-Path $tmp "runs.jsonl"
$stubOut = Join-Path $tmp "stub-out.txt"
$stub = Join-Path $tmp "stub-agent.ps1"
Set-Content -Path $stub -Encoding utf8 -Value @'
param([Parameter(ValueFromRemainingArguments = $true)]$a)
Add-Content -Path $env:STUB_OUT -Value ("PWD=" + $PWD.Path + " " + ($a -join ' ')) -Encoding utf8
if ($env:STUB_EXIT) { exit ([int]$env:STUB_EXIT) }
exit 0
'@
$env:STUB_OUT = $stubOut
Remove-Item Env:STUB_EXIT -ErrorAction SilentlyContinue

function New-Manifest([string]$Path, [hashtable]$Overrides = @{}) {
    $cfg = [ordered]@{
        display_name         = "Test sentinel"
        description          = "test"
        cron                 = "0 */2 * * *"
        sidecar_dir          = "test-sentinel"
        prompt_file          = "tasks/sentinel-prompts/daily-security-sentinel.md"
        watermark            = $wmPath
        watch_paths          = @("tasks")
        max_idle_hours       = 8
        lock_timeout_minutes = 30
    }
    foreach ($k in $Overrides.Keys) { $cfg[$k] = $Overrides[$k] }
    $m = [ordered]@{ version = 1; timezone = "America/Los_Angeles"; sentinels = [ordered]@{ $sentinel = $cfg } }
    $m | ConvertTo-Json -Depth 10 | Set-Content -Path $Path -Encoding utf8
}

$manifest = Join-Path $tmp "sentinels.json"
New-Manifest $manifest

function Invoke-Wrapper([string[]]$More = @(), [string]$ManifestPath = $manifest, [string]$Name = $sentinel) {
    & pwsh -NoProfile -File $wrapper -SentinelName $Name -ManifestFile $ManifestPath -AgentCommand $stub -RunLog $runLog -NoSync @More *> $null
    return $LASTEXITCODE
}
function Get-Decisions { if (Test-Path $runLog) { return ,@(Get-Content $runLog | ForEach-Object { ($_ | ConvertFrom-Json).decision }) } else { return ,@() } }
function Get-StubCalls { if (Test-Path $stubOut) { @(Get-Content $stubOut).Count } else { 0 } }
$markerPath = Join-Path $lockDir "sentinel-$sentinel.buildslot"
$bundlePath = Join-Path $lockDir "bold-bundle-security.json"
$claimLog = Join-Path $tmp "claims.txt"
function Reset-State {
    Remove-Item $lockPath, $wmPath, $runLog, $stubOut, $markerPath, $bundlePath, $claimLog -Force -ErrorAction SilentlyContinue
    Remove-Item Env:STUB_EXIT -ErrorAction SilentlyContinue
}

Write-Host "=== Running sentinel pre-gate tests ==="
try {
    $tasksTree = (git -C $repoRoot rev-parse "HEAD:tasks")

    # ---- wrapper: first run launches, lock is held, contention backs off ---------------------
    Reset-State
    $c = Invoke-Wrapper
    Assert-Test "First run (no watermark) launches the agent once" ($c -eq 0 -and (Get-StubCalls) -eq 1) "exit=$c calls=$(Get-StubCalls)"
    $call = if (Test-Path $stubOut) { Get-Content $stubOut -Raw } else { "" }
    Assert-Test "Agent gets a one-line prompt naming the prompt file and sentinel" ($call -match "new-conversation" -and $call -match "sentinel-prompts/daily-security-sentinel\.md" -and $call -match [regex]::Escape($sentinel)) $call
    Assert-Test "Prompt has no shell metacharacters that break the .bat shim" (($call -split "`n")[0] -notmatch '[&|<>^%"]') $call
    Assert-Test "Lock stays held while the agent works" (Test-Path $lockPath)

    $c = Invoke-Wrapper
    Assert-Test "Second slot while the lock is held backs off without launching" ($c -eq 0 -and (Get-StubCalls) -eq 1 -and (Get-Decisions)[-1] -eq "locked") "decisions=$((Get-Decisions) -join ',')"

    # ---- -Complete writes the watermark and releases ---------------------------------------
    $c = Invoke-Wrapper @("-Complete")
    $wm = if (Test-Path $wmPath) { Get-Content $wmPath -Raw | ConvertFrom-Json } else { $null }
    Assert-Test "-Complete releases the lock" ($c -eq 0 -and -not (Test-Path $lockPath)) "exit=$c"
    Assert-Test "-Complete writes the current tree hash under the watch path key" ($wm -and $wm.tree_hashes.tasks -eq $tasksTree) "wm=$($wm | ConvertTo-Json -Compress)"
    Assert-Test "-Complete writes a fresh UTC timestamp" ($wm -and (([datetime]::Parse($wm.timestamp).ToUniversalTime() - (Get-Date).ToUniversalTime()).TotalMinutes -gt -2)) "ts=$($wm.timestamp)"

    # ---- next slot is idle: no agent, zero launches -----------------------------------------
    $c = Invoke-Wrapper
    Assert-Test "Slot after a clean completion is idle (no agent started)" ($c -eq 0 -and (Get-StubCalls) -eq 1 -and (Get-Decisions)[-1] -eq "idle") "decisions=$((Get-Decisions) -join ',')"
    Assert-Test "An idle slot leaves no lock behind" (-not (Test-Path $lockPath))
    $log = @(Get-Content $runLog | ForEach-Object { $_ | ConvertFrom-Json })
    Assert-Test "Run log lines are valid JSON with ts, sentinel, decision" (($log | Where-Object { $_.ts -and $_.sentinel -eq $sentinel -and $_.decision }).Count -eq $log.Count) "n=$($log.Count)"

    # ---- tree change launches ---------------------------------------------------------------
    @{ timestamp = (Get-Date).ToUniversalTime().ToString("o"); tree_hashes = @{ tasks = "0000000000000000000000000000000000000000" } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    $before = Get-StubCalls
    $c = Invoke-Wrapper
    Assert-Test "A changed watched tree launches the agent" ($c -eq 0 -and (Get-StubCalls) -eq $before + 1) "calls=$(Get-StubCalls)"
    Invoke-Wrapper @("-Abort") | Out-Null

    # ---- heartbeat --------------------------------------------------------------------------
    Reset-State
    @{ timestamp = (Get-Date).ToUniversalTime().AddHours(-10).ToString("o"); tree_hashes = @{ tasks = $tasksTree } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    $c = Invoke-Wrapper
    Assert-Test "Unchanged tree but watermark older than max_idle_hours launches (heartbeat)" ($c -eq 0 -and (Get-StubCalls) -eq 1) "calls=$(Get-StubCalls)"
    $oldStamp = (Get-Content $wmPath -Raw | ConvertFrom-Json).timestamp
    $c = Invoke-Wrapper @("-Abort")
    $afterAbort = (Get-Content $wmPath -Raw | ConvertFrom-Json).timestamp
    Assert-Test "-Abort releases the lock and leaves the watermark alone" ($c -eq 0 -and -not (Test-Path $lockPath) -and $afterAbort -eq $oldStamp) "old=$oldStamp new=$afterAbort"
    $c = Invoke-Wrapper
    Assert-Test "After an abort the next slot retries" ($c -eq 0 -and (Get-StubCalls) -eq 2) "calls=$(Get-StubCalls)"
    Invoke-Wrapper @("-Abort") | Out-Null

    Reset-State
    @{ timestamp = (Get-Date).ToUniversalTime().AddHours(-7).ToString("o"); tree_hashes = @{ tasks = $tasksTree } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    $c = Invoke-Wrapper
    Assert-Test "Watermark younger than max_idle_hours stays idle" ($c -eq 0 -and (Get-StubCalls) -eq 0) "calls=$(Get-StubCalls)"

    Reset-State
    $noBeat = Join-Path $tmp "no-heartbeat.json"
    New-Manifest $noBeat @{ max_idle_hours = 0 }
    @{ timestamp = (Get-Date).ToUniversalTime().AddHours(-500).ToString("o"); tree_hashes = @{ tasks = $tasksTree } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    $c = Invoke-Wrapper -ManifestPath $noBeat
    Assert-Test "max_idle_hours 0 never forces a heartbeat" ($c -eq 0 -and (Get-StubCalls) -eq 0) "calls=$(Get-StubCalls)"

    # ---- watermark merge keeps the agent's own fields ---------------------------------------
    Reset-State
    @{ timestamp = "2020-01-01T00:00:00Z"; pr_number = 78; status = "SHOWCASE_PR_PREPARED"; tree_hashes = @{ other = "abc123" } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    Invoke-Wrapper | Out-Null
    Invoke-Wrapper @("-Complete") | Out-Null
    $wm = Get-Content $wmPath -Raw | ConvertFrom-Json
    Assert-Test "-Complete keeps unrelated watermark fields and other tree keys" ($wm.pr_number -eq 78 -and $wm.status -eq "SHOWCASE_PR_PREPARED" -and $wm.tree_hashes.other -eq "abc123" -and $wm.tree_hashes.tasks -eq $tasksTree) ($wm | ConvertTo-Json -Compress)

    # ---- agent launch directory (agentapi uses the caller's working directory) ---------------
    Reset-State
    Push-Location $tmp
    try { $c = Invoke-Wrapper } finally { Pop-Location }
    $call = if (Test-Path $stubOut) { Get-Content $stubOut -Raw } else { "" }
    Assert-Test "Agent is started from the repo root, not the caller's directory" ($c -eq 0 -and $call -match [regex]::Escape("PWD=" + $repoRoot)) $call
    Invoke-Wrapper @("-Abort") | Out-Null

    # ---- manifest aliases ------------------------------------------------------------------
    Reset-State
    $aliasManifest = Join-Path $tmp "alias.json"
    New-Manifest $aliasManifest @{ aliases = @("rs-alias-name") }
    $c = Invoke-Wrapper -ManifestPath $aliasManifest -Name "rs-alias-name"
    Assert-Test "A manifest alias resolves to the canonical sentinel (same lock, same log name)" ($c -eq 0 -and (Test-Path $lockPath) -and (Get-StubCalls) -eq 1 -and (Get-Content $runLog | Select-Object -Last 1 | ConvertFrom-Json).sentinel -eq $sentinel) "exit=$c"
    $c = Invoke-Wrapper @("-Complete") -ManifestPath $aliasManifest -Name "rs-alias-name"
    Assert-Test "-Complete through the alias releases the canonical lock" ($c -eq 0 -and -not (Test-Path $lockPath) -and (Test-Path $wmPath)) "exit=$c"

    # ---- build slots: no watched change, but the board has bigger work -----------------------
    function Set-IdleWatermark {
        @{ timestamp = (Get-Date).ToUniversalTime().ToString("o"); tree_hashes = @{ tasks = $tasksTree } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    }
    $claimOk = "Add-Content '$claimLog' x; Write-Output BUNDLE-JSON"
    $buildYes = Join-Path $tmp "build-yes.json"
    New-Manifest $buildYes @{ build = @{ lane = "security"; probe = "exit 0"; claim = $claimOk } }
    $buildNo = Join-Path $tmp "build-no.json"
    New-Manifest $buildNo @{ build = @{ lane = "security"; probe = "exit 20"; claim = $claimOk } }
    $buildNoBundle = Join-Path $tmp "build-nobundle.json"
    New-Manifest $buildNoBundle @{ build = @{ lane = "security"; probe = "exit 0"; claim = "exit 20" } }
    function Get-Claims { if (Test-Path $claimLog) { @(Get-Content $claimLog).Count } else { 0 } }

    Reset-State
    Set-IdleWatermark
    $c = Invoke-Wrapper -ManifestPath $buildYes
    $last = if (Test-Path $runLog) { Get-Content $runLog | Select-Object -Last 1 | ConvertFrom-Json } else { $null }
    Assert-Test "Idle gate but the build probe finds work: the agent is launched as a build slot" ($c -eq 0 -and (Get-StubCalls) -eq 1 -and $last.decision -eq "launched" -and $last.detail -match "build slot") "calls=$(Get-StubCalls) last=$($last | ConvertTo-Json -Compress)"
    Assert-Test "A build slot holds the lock like any other run" (Test-Path $lockPath)
    Assert-Test "The wrapper claims the bundle once and hands the agent the bundle file" ((Get-Claims) -eq 1 -and (Test-Path $bundlePath) -and (Get-Content $bundlePath -Raw).Trim() -eq "BUNDLE-JSON") "claims=$(Get-Claims)"
    Assert-Test "A build slot leaves a marker so -Complete will not advance the watermark" (Test-Path $markerPath)
    $c = Invoke-Wrapper -ManifestPath $buildYes
    Assert-Test "A second slot during a build run backs off (the lock is still respected)" ($c -eq 0 -and (Get-StubCalls) -eq 1 -and (Get-Decisions)[-1] -eq "locked") "decisions=$((Get-Decisions) -join ',')"
    $stampBefore = (Get-Content $wmPath -Raw | ConvertFrom-Json).timestamp
    Start-Sleep -Milliseconds 1200
    $c = Invoke-Wrapper @("-Complete") -ManifestPath $buildYes
    $stampAfter = (Get-Content $wmPath -Raw | ConvertFrom-Json).timestamp
    Assert-Test "-Complete after a build slot releases the lock and keeps the watermark timestamp (heartbeat not reset)" ($c -eq 0 -and -not (Test-Path $lockPath) -and -not (Test-Path $markerPath) -and ("$stampAfter" -eq "$stampBefore")) "before=$stampBefore after=$stampAfter"
    Assert-Test "Completing a build slot is logged as such" ((Get-Content $runLog | Select-Object -Last 1 | ConvertFrom-Json).detail -match "build slot: watermark kept")

    Reset-State
    Set-IdleWatermark
    Invoke-Wrapper -ManifestPath $buildYes | Out-Null
    Invoke-Wrapper @("-Abort") -ManifestPath $buildYes | Out-Null
    Assert-Test "-Abort after a build slot clears the marker and the lock" (-not (Test-Path $markerPath) -and -not (Test-Path $lockPath))

    Reset-State
    Set-IdleWatermark
    $c = Invoke-Wrapper -ManifestPath $buildNoBundle
    Assert-Test "A failed claim leaves no bundle file (the agent skips the build round)" ($c -eq 0 -and (Get-StubCalls) -eq 1 -and -not (Test-Path $bundlePath)) "calls=$(Get-StubCalls)"
    Invoke-Wrapper @("-Abort") -ManifestPath $buildNoBundle | Out-Null

    Reset-State
    Set-IdleWatermark
    Set-Content $bundlePath "STALE" -Encoding utf8
    Invoke-Wrapper -ManifestPath $buildNoBundle | Out-Null
    Assert-Test "A stale bundle file from an earlier run is removed before the agent starts" (-not (Test-Path $bundlePath))
    Invoke-Wrapper @("-Abort") -ManifestPath $buildNoBundle | Out-Null

    Reset-State
    Set-IdleWatermark
    $c = Invoke-Wrapper -ManifestPath $buildNo
    Assert-Test "Idle gate and a probe that finds no work: nothing is launched, nothing is claimed" ($c -eq 0 -and (Get-StubCalls) -eq 0 -and (Get-Claims) -eq 0 -and (Get-Decisions)[-1] -eq "idle" -and -not (Test-Path $lockPath)) "decisions=$((Get-Decisions) -join ',') claims=$(Get-Claims)"

    Reset-State
    Set-IdleWatermark
    $c = Invoke-Wrapper @("-DryRun") -ManifestPath $buildYes
    Assert-Test "-DryRun claims nothing and writes no bundle or marker" ($c -eq 0 -and (Get-Claims) -eq 0 -and -not (Test-Path $bundlePath) -and -not (Test-Path $markerPath))

    Reset-State
    Set-IdleWatermark
    $c = Invoke-Wrapper
    Assert-Test "A sentinel without a build block stays idle when nothing changed" ($c -eq 0 -and (Get-StubCalls) -eq 0 -and (Get-Decisions)[-1] -eq "idle")

    Reset-State
    @{ timestamp = (Get-Date).ToUniversalTime().ToString("o"); tree_hashes = @{ tasks = "0000000000000000000000000000000000000000" } } | ConvertTo-Json | Set-Content $wmPath -Encoding utf8
    $c = Invoke-Wrapper -ManifestPath $buildNo
    $last = Get-Content $runLog | Select-Object -Last 1 | ConvertFrom-Json
    Assert-Test "A real change still launches normally (not labelled a build slot)" ($c -eq 0 -and (Get-StubCalls) -eq 1 -and $last.detail -notmatch "build slot") "detail=$($last.detail)"
    Assert-Test "A normal slot also claims its lane's bundle (the build round is part of every run)" ((Get-Claims) -eq 1 -and (Test-Path $bundlePath) -and -not (Test-Path $markerPath)) "claims=$(Get-Claims)"
    Invoke-Wrapper @("-Complete") -ManifestPath $buildNo | Out-Null
    $wmNow = Get-Content $wmPath -Raw | ConvertFrom-Json
    Assert-Test "-Complete after a normal slot still advances the watermark" ($wmNow.tree_hashes.tasks -eq $tasksTree)

    Reset-State
    Set-IdleWatermark
    $env:STUB_EXIT = "1"
    $c = Invoke-Wrapper -ManifestPath $buildYes
    Assert-Test "A launch failure in a build slot clears the marker and frees the lock" ($c -eq 4 -and -not (Test-Path $markerPath) -and -not (Test-Path $lockPath)) "exit=$c"
    Remove-Item Env:STUB_EXIT -ErrorAction SilentlyContinue

    # ---- failure paths ----------------------------------------------------------------------
    Reset-State
    $env:STUB_EXIT = "1"
    $c = Invoke-Wrapper
    Assert-Test "Agent launch failure exits 4, logs launch_failed and frees the lock" ($c -eq 4 -and (Get-Decisions)[-1] -eq "launch_failed" -and -not (Test-Path $lockPath)) "exit=$c lock=$(Test-Path $lockPath) decisions=$((Get-Decisions) -join ',')"

    Reset-State
    $badPrompt = Join-Path $tmp "bad-prompt.json"
    New-Manifest $badPrompt @{ prompt_file = "tasks/sentinel-prompts/does-not-exist.md" }
    $c = Invoke-Wrapper -ManifestPath $badPrompt
    Assert-Test "Missing prompt file exits 3 and frees the lock" ($c -eq 3 -and -not (Test-Path $lockPath) -and (Get-StubCalls) -eq 0) "exit=$c"

    Reset-State
    $c = Invoke-Wrapper -Name "not-in-manifest"
    Assert-Test "Unknown sentinel name exits 2" ($c -eq 2) "exit=$c"

    Reset-State
    $c = Invoke-Wrapper -ManifestPath (Join-Path $tmp "nope.json")
    Assert-Test "Missing manifest exits 2" ($c -eq 2) "exit=$c"

    # ---- dry run and sync tolerance ----------------------------------------------------------
    Reset-State
    $c = Invoke-Wrapper @("-DryRun")
    Assert-Test "-DryRun starts no agent, frees the lock and logs dry_run" ($c -eq 0 -and (Get-StubCalls) -eq 0 -and -not (Test-Path $lockPath) -and (Get-Decisions)[-1] -eq "dry_run") "exit=$c calls=$(Get-StubCalls) lock=$(Test-Path $lockPath) decisions=$((Get-Decisions) -join ',')"

    Reset-State
    & pwsh -NoProfile -File $wrapper -SentinelName $sentinel -ManifestFile $manifest -AgentCommand $stub -RunLog $runLog -SyncCommand "exit 3" *> $null
    $c = $LASTEXITCODE
    Assert-Test "A failing sync is logged but does not block the run" ($c -eq 0 -and (Get-StubCalls) -eq 1) "exit=$c calls=$(Get-StubCalls)"
    Invoke-Wrapper @("-Abort") | Out-Null

    # ---- gate flags used directly -------------------------------------------------------------
    Reset-State
    & pwsh -NoProfile -File $gate -SentinelName $sentinel -Release -WriteWatermark *> $null
    Assert-Test "-WriteWatermark without -WatermarkFile writes nothing and still exits 0" ($LASTEXITCODE -eq 0 -and -not (Test-Path $wmPath))

    "{ this is not json" | Set-Content $wmPath -Encoding utf8
    & pwsh -NoProfile -File $gate -SentinelName $sentinel -Release -WriteWatermark -WatermarkFile $wmPath -WatchPaths "tasks" *> $null
    $wm = Get-Content $wmPath -Raw | ConvertFrom-Json
    Assert-Test "A corrupt watermark is replaced by a valid one" ($LASTEXITCODE -eq 0 -and $wm.tree_hashes.tasks -eq $tasksTree)

    # ---- renderer ------------------------------------------------------------------------------
    $sidecarRoot = Join-Path $tmp "sidecars"
    $dir = Join-Path $sidecarRoot "test-sentinel"
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $sc = Join-Path $dir "sidecar.json"
    @{
        builtin = "schedule"
        args = @("CRON_TZ=America/Los_Angeles */10 * * * *", "agentapi", "new-conversation", "--", "old prompt")
        restart_policy = "always"
        display_name = "Old"
        description = "Old"
        agent_permissions = @{ access_grants = @("command(git)") }
    } | ConvertTo-Json -Depth 10 | Set-Content $sc -Encoding utf8
    $before = Get-Content $sc -Raw

    & pwsh -NoProfile -File $renderer -ManifestFile $manifest -SidecarRoot $sidecarRoot -RepoRoot $repoRoot *> $null
    Assert-Test "Renderer default mode writes nothing" ((Get-Content $sc -Raw) -eq $before)
    & pwsh -NoProfile -File $renderer -Check -ManifestFile $manifest -SidecarRoot $sidecarRoot -RepoRoot $repoRoot *> $null
    Assert-Test "Renderer -Check exits 1 on drift" ($LASTEXITCODE -eq 1) "exit=$LASTEXITCODE"
    & pwsh -NoProfile -File $renderer -Install -ManifestFile $manifest -SidecarRoot $sidecarRoot -RepoRoot $repoRoot *> $null
    $j = Get-Content $sc -Raw | ConvertFrom-Json
    Assert-Test "Renderer -Install sets cron, wrapper command and name from the manifest" ($j.args[0] -eq "CRON_TZ=America/Los_Angeles 0 */2 * * *" -and $j.args[1] -eq "pwsh" -and ($j.args -contains $sentinel) -and ($j.args | Where-Object { $_ -like "*tasks/run-sentinel.ps1" }) -and $j.display_name -eq "Test sentinel") ($j.args -join " | ")
    Assert-Test "Renderer -Install keeps permissions and restart policy" ($j.restart_policy -eq "always" -and $j.agent_permissions.access_grants[0] -eq "command(git)")
    Assert-Test "Renderer keeps a one-time backup of the old file" ((Test-Path "$sc.bak-pre-render") -and ((Get-Content "$sc.bak-pre-render" -Raw) -eq $before))
    & pwsh -NoProfile -File $renderer -Check -ManifestFile $manifest -SidecarRoot $sidecarRoot -RepoRoot $repoRoot *> $null
    Assert-Test "Renderer -Check exits 0 once the sidecar matches" ($LASTEXITCODE -eq 0) "exit=$LASTEXITCODE"
    Remove-Item $dir -Recurse -Force
    & pwsh -NoProfile -File $renderer -Check -ManifestFile $manifest -SidecarRoot $sidecarRoot -RepoRoot $repoRoot *> $null
    Assert-Test "Renderer -Check treats a missing sidecar as drift" ($LASTEXITCODE -eq 1) "exit=$LASTEXITCODE"

    # ---- the real manifest ------------------------------------------------------------------------
    $real = Get-Content $realManifestPath -Raw | ConvertFrom-Json
    $names = @($real.sentinels.PSObject.Properties.Name)
    Assert-Test "Real manifest lists the three sentinels" ($names.Count -eq 3) ($names -join ",")
    $minutes = @()
    foreach ($n in $names) {
        $c = $real.sentinels.$n
        $parts = @($c.cron -split '\s+')
        $minuteOk = $parts.Count -eq 5 -and $parts[0] -match '^\d+$'
        $hourStep = if ($parts[1] -match '^\*/(\d+)$') { [int]$Matches[1] } elseif ($parts[1] -match '^\d+$') { 24 } else { 0 }
        Assert-Test "$n cron has 5 fields, a single minute offset and runs at most every 2 hours" ($minuteOk -and $hourStep -ge 2) "cron=$($c.cron)"
        $minutes += $parts[0]
        $p = Join-Path $repoRoot $c.prompt_file
        $text = if (Test-Path $p) { Get-Content $p -Raw } else { "" }
        Assert-Test "$n prompt file exists and ends through run-sentinel -Complete / -Abort" ($text -match "run-sentinel\.ps1 -SentinelName $n -Complete" -and $text -match "-Abort") $c.prompt_file
        Assert-Test "$n prompt tells the agent not to rerun the gate (own lock would block it)" ($text -match 'Do NOT run `fast-sentinel-gate\.ps1`') $c.prompt_file
        Assert-Test "$n prompt never asks for a per-round handoff append" ($text -notmatch "(?i)append (a )?(per-round )?summary to" -and $text -match "(?i)only when") $c.prompt_file
        $cadenceMin = if ($c.cron -split '\s+' | Select-Object -Skip 1 -First 1 | ForEach-Object { $_ -match '^\*/(\d+)$' }) { [int]$Matches[1] * 60 } else { 1440 }
        Assert-Test "$n lock timeout is below the cadence (a hung run is reclaimed by the next slot)" ([int]$c.lock_timeout_minutes -lt $cadenceMin -and [int]$c.lock_timeout_minutes -ge 30) "timeout=$($c.lock_timeout_minutes) cadence=$cadenceMin"
        $lanes = @("security", "research", "showcase")
        Assert-Test "$n has a build lane the picker knows" ($c.build -and $lanes -contains $c.build.lane) "build=$($c.build | ConvertTo-Json -Compress)"
        Assert-Test "$n prompt has a build round that reads its own lane's bundle file (the wrapper claims it)" ($text -match "Build round" -and $text -match [regex]::Escape("bold-bundle-$($c.build.lane).json") -and $text -notmatch "pick_bold_task.py --lane \w+ --claim" -and $text -match "WHOLE bundle" -and $text -match "(?i)never merge") $c.prompt_file
        Assert-Test "$n prompt uses a branch field the worktree helper accepts" ($text -match [regex]::Escape("--branch <the branch field of the bundle file>")) $c.prompt_file
        Assert-Test "$n prompt never lets the build round touch human-only tasks" ($text -match "HUMAN-TASKS\.md") $c.prompt_file
        Assert-Test "$n has a watermark and at least one watch path" ($c.watermark -and @($c.watch_paths).Count -ge 1)
        Assert-Test "$n sidecar_dir is set" ([bool]$c.sidecar_dir)
    }
    Assert-Test "The documented security alias daily-site-security-sentinel is in the manifest" (@($real.sentinels."daily-security-sentinel".aliases) -contains "daily-site-security-sentinel")
    Assert-Test "Real sentinels run at different minute offsets" (@($minutes | Select-Object -Unique).Count -eq $minutes.Count) ($minutes -join ",")

    # No scheduled-* skill may still describe the retired 10-minute turbo cadence or a gate the agent runs itself.
    $stale = @(Get-ChildItem (Join-Path $repoRoot ".claude/skills") -Directory -Filter "scheduled-*" | ForEach-Object {
        $sk = Join-Path $_.FullName "SKILL.md"
        if ((Test-Path $sk) -and ((Get-Content $sk -Raw) -match '(?i)every 10 minutes|10-minute cadence|Turbo Mode Cadence|\*/10 \* \* \* \*|\d-59/10')) { $_.Name }
    })
    Assert-Test "No scheduled-* skill still documents the 10-minute turbo cadence" ($stale.Count -eq 0) ($stale -join ", ")
    # Every real watch path must resolve to a real tree hash (otherwise the gate never idles). Uses a
    # copy of the manifest with 'lint-' names and temp watermarks so no live lock or watermark is touched.
    # In standalone CI without sibling repos checked out, skip this section gracefully.
    $commonGit = (git -C $repoRoot rev-parse --path-format=absolute --git-common-dir 2>$null)
    $labMain = if ($commonGit) { Split-Path -Parent $commonGit } else { $repoRoot }
    $siblingsRoot = Split-Path -Parent $labMain
    $hasSiblings = (Test-Path (Join-Path $siblingsRoot "cf-research")) -and (Test-Path (Join-Path $siblingsRoot "cf-skills")) -and (Test-Path (Join-Path $siblingsRoot ".ai"))
    if (-not $hasSiblings) {
        Write-Host "SKIP: Real watch path resolution test needs the sibling repos (cf-research, cf-skills, .ai) next to cf-lab." -ForegroundColor Yellow
    } else {
        $lint = [ordered]@{ version = 1; timezone = $real.timezone; sentinels = [ordered]@{} }
        foreach ($n in $names) {
            $c = $real.sentinels.$n
            $lint.sentinels["lint-$n"] = [ordered]@{
                sidecar_dir = $c.sidecar_dir; display_name = $c.display_name; description = $c.description; cron = $c.cron
                prompt_file = $c.prompt_file; watermark = (Join-Path $tmp "lint-$n.json"); watch_paths = $c.watch_paths
                max_idle_hours = $c.max_idle_hours; lock_timeout_minutes = $c.lock_timeout_minutes
                build = @{ lane = $c.build.lane; probe = "exit 20"; claim = "exit 20" }
            }
        }
        $lintManifest = Join-Path $tmp "lint-manifest.json"
        $lint | ConvertTo-Json -Depth 10 | Set-Content $lintManifest -Encoding utf8
        foreach ($n in $names) {
            $ln = "lint-$n"
            $lintLock = Join-Path $lockDir "sentinel-$ln.lock"
            Remove-Item $lintLock -Force -ErrorAction SilentlyContinue
            $c1 = Invoke-Wrapper -ManifestPath $lintManifest -Name $ln
            $c2 = Invoke-Wrapper @("-Complete") -ManifestPath $lintManifest -Name $ln
            $w = $null
            $wf = Join-Path $tmp "lint-$n.json"
            if (Test-Path $wf) { $w = Get-Content $wf -Raw | ConvertFrom-Json }
            $missing = @($real.sentinels.$n.watch_paths | Where-Object { -not ($w -and $w.tree_hashes.$_) })
            Assert-Test "$n watch paths all resolve to a tree hash" ($missing.Count -eq 0) "unresolved: $($missing -join ', ')"
            $c3 = Invoke-Wrapper -ManifestPath $lintManifest -Name $ln
            Assert-Test "$n goes idle right after its own watermark is written" ($c3 -eq 0 -and (Get-Decisions)[-1] -eq "idle") "decisions=$((Get-Decisions) -join ',')"
            Remove-Item $lintLock -Force -ErrorAction SilentlyContinue
        }
    }
}
finally {
    Remove-Item $lockPath, $markerPath, $bundlePath -Force -ErrorAction SilentlyContinue
    foreach ($n in @("daily-security-sentinel", "daily-research-sentinel", "daily-site-showcase-sentinel")) {
        Remove-Item (Join-Path $lockDir "sentinel-lint-$n.lock") -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Env:STUB_OUT, Env:STUB_EXIT -ErrorAction SilentlyContinue
}

Write-Host "`nTest Summary: $pass passed, $fail failed."
if ($fail -gt 0) { exit 1 }
exit 0
