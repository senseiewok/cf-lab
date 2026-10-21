<#
.SYNOPSIS
    Scheduler entry point for a sentinel: sync, gate, then start the agent only when there is work.

.DESCRIPTION
    The cron job runs this script instead of starting an agent conversation directly, so an idle
    slot costs a few git calls and zero model tokens (the old setup started a conversation every
    time and asked the model to run the gate, which spent tokens even when nothing had changed).

    Run mode (default):
      1. python sync-main.py (fast-forward only; a failure is logged, the run still goes on)
      2. tasks/fast-sentinel-gate.ps1 with the sentinel's watermark, watch paths, heartbeat
      3. exit 10 (lock held) or 20 (idle): log it and stop; exit 0: start the agent
         with a one-line prompt that points at the sentinel's prompt file
    -Complete  Success path, called by the agent as its last step: writes the watermark and
               releases the lock.
    -Abort     Failure path: releases the lock and leaves the watermark alone, so the next slot retries.

    Every decision is appended to .loop-logs/sentinel-runs.jsonl (launched, locked, idle,
    launch_failed, completed, aborted), one line per slot, so a person can see what ran.

    Test hooks: -ManifestFile, -AgentCommand, -SyncCommand, -NoSync, -RunLog, -DryRun.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SentinelName,

    [switch]$Complete,

    [switch]$Abort,

    [switch]$DryRun,

    [switch]$NoSync,

    [string]$ManifestFile = "",

    [string]$AgentCommand = "agentapi",

    [string]$SyncCommand = "",

    [string]$RunLog = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$gate = Join-Path $PSScriptRoot "fast-sentinel-gate.ps1"
if (-not $ManifestFile) { $ManifestFile = Join-Path $PSScriptRoot "sentinels.json" }
if (-not $RunLog) { $RunLog = Join-Path $repoRoot ".loop-logs/sentinel-runs.jsonl" }

function Write-RunLog([string]$Decision, [string]$Detail = "") {
    $full = [IO.Path]::GetFullPath($RunLog)
    $dir = Split-Path -Parent $full
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $line = [ordered]@{
        ts       = (Get-Date).ToUniversalTime().ToString("o")
        sentinel = $SentinelName
        decision = $Decision
        detail   = $Detail
    } | ConvertTo-Json -Compress
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($line + [Environment]::NewLine)
    for ($try = 1; $try -le 200; $try++) {
        try {
            $fs = [IO.File]::Open($full, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try { $fs.Write($bytes, 0, $bytes.Length) } finally { $fs.Dispose() }
            return
        } catch [IO.IOException] {
            if ($try -eq 200) { throw }
            Start-Sleep -Milliseconds (Get-Random -Minimum 5 -Maximum 40)
        }
    }
}

if (-not (Test-Path $ManifestFile)) {
    Write-Host "RUN-SENTINEL: manifest not found: $ManifestFile"
    exit 2
}
$manifest = Get-Content $ManifestFile -Raw | ConvertFrom-Json
$cfg = $manifest.sentinels.$SentinelName
if (-not $cfg) {
    # The skills document compatibility aliases (for example daily-site-security-sentinel). Resolve them
    # to the canonical name first so the lock, watermark and run log all use one name.
    foreach ($n in $manifest.sentinels.PSObject.Properties.Name) {
        if (@($manifest.sentinels.$n.aliases) -contains $SentinelName) {
            $SentinelName = $n
            $cfg = $manifest.sentinels.$n
            break
        }
    }
}
if (-not $cfg) {
    Write-Host "RUN-SENTINEL: '$SentinelName' is not in $ManifestFile"
    exit 2
}

function Get-GateArgs([switch]$NoDelta) {
    $a = @("-NoProfile", "-File", $gate, "-SentinelName", $SentinelName)
    if ($null -ne $cfg.lock_timeout_minutes) { $a += @("-LockTimeoutMinutes", [string]$cfg.lock_timeout_minutes) }
    # -NoDelta takes the lock without comparing watermarks (used when the board has work to build).
    if (-not $NoDelta) {
        if ($cfg.watermark) { $a += @("-WatermarkFile", [string]$cfg.watermark) }
        if ($cfg.watch_paths) { $a += @("-WatchPaths", (@($cfg.watch_paths) -join ",")) }
        if ($null -ne $cfg.max_idle_hours) { $a += @("-MaxIdleHours", [string]$cfg.max_idle_hours) }
    }
    return $a
}

# A build slot (started with no watched change) skipped the audit work, so finishing it must not advance
# the watermark: that would reset the heartbeat and starve the live-state checks. The marker file says so.
$safeName = $SentinelName -replace '[^a-zA-Z0-9_\-]', '_'
$markerPath = Join-Path $repoRoot ".loop-logs/sentinel-$safeName.buildslot"

if ($Complete -or $Abort) {
    $buildSlot = Test-Path $markerPath
    $a = Get-GateArgs
    $a += "-Release"
    if ($Complete -and -not $buildSlot) { $a += "-WriteWatermark" }
    & pwsh @a
    $code = $LASTEXITCODE
    Remove-Item $markerPath -Force -ErrorAction SilentlyContinue
    $detail = "gate release exit $code"
    if ($Complete -and $buildSlot) { $detail += " (build slot: watermark kept)" }
    Write-RunLog -Decision $(if ($Complete) { "completed" } else { "aborted" }) -Detail $detail
    exit $code
}

# 1. Sync (cheap, no tokens). Without it a merged pull request never changes HEAD and the gate stays idle.
if (-not $NoSync) {
    try {
        if ($SyncCommand) {
            & pwsh -NoProfile -Command $SyncCommand | Out-Null
        } else {
            $sync = Join-Path $repoRoot ".claude/skills/workspace-siblings/scripts/sync-main.py"
            & python $sync | Out-Null
        }
        if ($LASTEXITCODE -ne 0) { Write-Host "RUN-SENTINEL: sync exited $LASTEXITCODE; continuing." }
    } catch {
        Write-Host "RUN-SENTINEL: sync failed ($($_.Exception.Message)); continuing."
    }
}

# 2. Gate
$gateOut = & pwsh @(Get-GateArgs) 2>&1
$gateCode = $LASTEXITCODE
$gateOut | ForEach-Object { Write-Host $_ }

# Idle means no watched tree changed. A sentinel with a build lane may still have bigger work to do
# from the board's ready tasks (tasks/pick_bold_task.py), so ask before giving the slot up.
$buildRun = $false
if ($gateCode -eq 20 -and $cfg.build) {
    if ($cfg.build.probe) {
        & pwsh -NoProfile -Command ([string]$cfg.build.probe) *> $null
    } else {
        & python (Join-Path $PSScriptRoot "pick_bold_task.py") --lane ([string]$cfg.build.lane) --check *> $null
    }
    if ($LASTEXITCODE -eq 0) {
        $gateOut = & pwsh @(Get-GateArgs -NoDelta) 2>&1
        $gateCode = $LASTEXITCODE
        $gateOut | ForEach-Object { Write-Host $_ }
        $buildRun = $true
    }
}

if ($gateCode -eq 10) { Write-RunLog -Decision "locked"; exit 0 }
if ($gateCode -eq 20) { Write-RunLog -Decision "idle"; exit 0 }
if ($gateCode -ne 0) { Write-RunLog -Decision "gate_error" -Detail "exit $gateCode"; exit $gateCode }

# 3. Launch the agent with a one-line prompt (no shell metacharacters: agentapi is a .bat shim)
$promptPath = Join-Path $repoRoot ([string]$cfg.prompt_file)
if (-not (Test-Path $promptPath)) {
    Write-RunLog -Decision "launch_failed" -Detail "prompt file missing: $($cfg.prompt_file)"
    & pwsh @((Get-GateArgs) + "-Release") | Out-Null
    exit 3
}
$promptFwd = $promptPath.Replace('\', '/')
$prompt = "Read $promptFwd and carry out every step in it for $SentinelName."
$title = "$SentinelName $((Get-Date).ToString('yyyy-MM-dd HH:mm'))"

if ($DryRun) {
    Write-RunLog -Decision "dry_run" -Detail "would launch: $prompt"
    & pwsh @((Get-GateArgs) + "-Release") | Out-Null
    Write-Host "RUN-SENTINEL: dry run, would launch: $prompt"
    exit 0
}

# Build lane: the wrapper, not the agent, claims the bundle. The attempt is therefore counted even when the
# agent dies before doing anything (no retry storm), and the agent reads the exact bundle from a file.
Remove-Item $markerPath -Force -ErrorAction SilentlyContinue
if ($cfg.build -and $cfg.build.lane) {
    $bundleFile = Join-Path $repoRoot ".loop-logs/bold-bundle-$($cfg.build.lane).json"
    Remove-Item $bundleFile -Force -ErrorAction SilentlyContinue
    try {
        if ($cfg.build.claim) {
            $claimOut = & pwsh -NoProfile -Command ([string]$cfg.build.claim) 2>$null
        } else {
            $claimOut = & python (Join-Path $PSScriptRoot "pick_bold_task.py") --lane ([string]$cfg.build.lane) --claim 2>$null
        }
        if ($LASTEXITCODE -eq 0 -and $claimOut) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $bundleFile) -Force | Out-Null
            ($claimOut -join "`n") | Set-Content -Path $bundleFile -Encoding utf8
        }
    } catch {
        Write-Host "RUN-SENTINEL: build claim failed ($($_.Exception.Message)); the agent gets no bundle."
    }
}
if ($buildRun) { Set-Content -Path $markerPath -Value (Get-Date).ToUniversalTime().ToString("o") -Encoding utf8 }

try {
    # agentapi has no directory flag and starts the conversation in the caller's working directory;
    # the prompt files use repo-relative paths, so anchor the launch to this repo.
    Push-Location $repoRoot
    try {
        $env:LOCAL_WORKER_TAG = $SentinelName
        & $AgentCommand new-conversation "--title=$title" $prompt
        $agentExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($agentExit -ne 0) { throw "agent command exited $agentExit" }
    Write-RunLog -Decision "launched" -Detail $(if ($buildRun) { "$title (build slot, no watched change)" } else { $title })
    exit 0
} catch {
    Remove-Item $markerPath -Force -ErrorAction SilentlyContinue
    Write-RunLog -Decision "launch_failed" -Detail $_.Exception.Message
    & pwsh @((Get-GateArgs) + "-Release") | Out-Null
    exit 4
}
