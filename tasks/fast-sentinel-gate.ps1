<#
.SYNOPSIS
    Fast deterministic pre-flight gate for scheduled sentinels.
    Evaluates lock contention and git tree hash deltas in <100ms with ZERO token burn.

.DESCRIPTION
    Exits:
      0  - Lock acquired, real deltas detected (proceed with full workflow)
      10 - Lock held by another active sentinel (back off immediately)
      20 - Idle, zero git deltas since last watermark (terminate immediately)

    -MaxIdleHours N   Heartbeat: when the watermark is older than N hours, matching tree hashes no
                      longer count as idle, so checks of live state (production headers, registry
                      polls) still run now and then. 0 (default) means no heartbeat.
    -WriteWatermark   With -Release: record the current tree hash of every -WatchPaths entry and a
                      fresh timestamp in -WatermarkFile, keeping its other fields. Call it only after
                      a successful run so a failed run is retried.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SentinelName,

    [switch]$Release,

    [switch]$WriteWatermark,

    [int]$MaxIdleHours = 0,

    [switch]$Force,

    [string]$LockFile = "",

    [string]$WatermarkFile = "",

    [string[]]$WatchPaths = @(),

    [int]$LockTimeoutMinutes = 30,

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$ExtraPaths = @()
)

$ErrorActionPreference = "Stop"

# Normalize WatchPaths if passed as comma-separated or PowerShell array literal string
$WatchPaths = @($WatchPaths) + @($ExtraPaths)
if ($WatchPaths) {
    $WatchPaths = @($WatchPaths | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim().Trim('@(').Trim(')').Trim('"').Trim("'") } | Where-Object { $_ })
}

# Finding 1 Fix: $PSScriptRoot is '<repo>/tasks', so parent is repo root '<repo>'
$cfLab = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $cfLab "tasks/board.json"))) {
    # Fallback to current directory or parent if invoked abnormally
    if (Test-Path "tasks/board.json") {
        $cfLab = (Get-Location).Path
    } elseif (Test-Path "../tasks/board.json") {
        $cfLab = (Get-Item "..").FullName
    }
}

# Council Amendment: Scope lock file per sentinel name to prevent starvation (sanitized against path traversal)
if (-not $LockFile) {
    $SafeSentinelName = ($SentinelName -replace '[^a-zA-Z0-9_\-]', '_')
    $LockFile = ".loop-logs/sentinel-$SafeSentinelName.lock"
}

if ([System.IO.Path]::IsPathRooted($LockFile)) {
    $FullLockPath = $LockFile
} else {
    $FullLockPath = [System.IO.Path]::GetFullPath((Join-Path $cfLab $LockFile))
}

function ConvertTo-UtcDate($Value) {
    # ConvertFrom-Json already turns ISO-8601 strings into DateTime; parsing that DateTime again
    # through [datetime]::Parse(string) would lose its UTC marker and shift it by the local offset.
    if ($Value -is [datetime]) { return $Value.ToUniversalTime() }
    return [datetime]::Parse([string]$Value, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
}

function Resolve-WatchTarget([string]$wp) {
    # In a git worktree a '../<repo>' path would resolve beside the worktree (a different folder
    # than the real sibling repo), so look beside the repositories first.
    if ($wp -match '^\.\.[\\/]' -and $cfLab -like "*\.worktrees\*") {
        $wtParent = Split-Path -Parent $cfLab
        while ($wtParent -and (Split-Path -Leaf $wtParent) -ne ".worktrees") { $wtParent = Split-Path -Parent $wtParent }
        if ($wtParent) {
            $real = [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $wtParent) ($wp -replace '^(\.{1,2}[\\/])+', '')))
            if (Test-Path $real) { return $real }
        }
    }
    $Target = if ([System.IO.Path]::IsPathRooted($wp)) {
        $wp
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $cfLab $wp))
    }

    # Sibling repo fallback (when $wp refers to a sibling repo such as .ai or cf-research)
    if (-not (Test-Path $Target)) {
        $reposRoot = Split-Path -Parent $cfLab
        # Strip only leading './' and '../' segments. TrimStart('.') would also eat the dot of a
        # dot-named sibling repo such as '.ai' and resolve '.ai/src' to a nonexistent 'ai/src'.
        $strippedWp = $wp -replace '^(\.{1,2}[\\/])+', ''
        $SiblingTarget = [System.IO.Path]::GetFullPath((Join-Path $reposRoot $strippedWp))
        if (Test-Path $SiblingTarget) {
            $Target = $SiblingTarget
        } elseif ($cfLab -like "*\.worktrees*") {
            $parent = Split-Path -Parent $cfLab
            while ($parent -and (Split-Path -Leaf $parent) -ne ".worktrees") {
                $parent = Split-Path -Parent $parent
            }
            if ($parent) {
                $reposRoot = Split-Path -Parent $parent
                $WorktreeTarget = [System.IO.Path]::GetFullPath((Join-Path $reposRoot $strippedWp))
                if (Test-Path $WorktreeTarget) {
                    $Target = $WorktreeTarget
                }
            }
        }
    }
    return $Target
}

function Get-WatchTreeHash([string]$wp, [string]$Target) {
    $ParentDir = Split-Path -Parent $Target
    $BaseName = Split-Path -Leaf $Target
    # 'HEAD:./$BaseName' makes Git resolve relative to $ParentDir
    $CurrentTree = (git -C $ParentDir rev-parse "HEAD:./$BaseName" 2>$null)
    if (-not $CurrentTree) {
        # Fallback for full repo relative path
        $RelPath = $wp.Replace('\', '/')
        $CurrentTree = (git -C $cfLab rev-parse "HEAD:$RelPath" 2>$null)
    }
    return $CurrentTree
}

function Resolve-GatePath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }
    return [System.IO.Path]::GetFullPath((Join-Path $cfLab $Path))
}

function Write-GateWatermark {
    if (-not $WatermarkFile -or $WatchPaths.Count -eq 0) {
        Write-Warning "FAST-GATE: -WriteWatermark needs -WatermarkFile and -WatchPaths. Nothing written."
        return
    }
    $FullWatermarkPath = Resolve-GatePath $WatermarkFile
    $wm = [ordered]@{}
    if (Test-Path $FullWatermarkPath) {
        try {
            $existing = Get-Content $FullWatermarkPath -Raw | ConvertFrom-Json -AsHashtable
            if ($existing) { foreach ($k in $existing.Keys) { $wm[$k] = $existing[$k] } }
        } catch {
            Write-Warning "FAST-GATE: Existing watermark unreadable; replacing it."
        }
    }
    $hashes = @{}
    if ($wm.Contains('tree_hashes') -and $wm['tree_hashes'] -is [System.Collections.IDictionary]) {
        foreach ($k in $wm['tree_hashes'].Keys) { $hashes[$k] = $wm['tree_hashes'][$k] }
    }
    foreach ($wp in $WatchPaths) {
        $Target = Resolve-WatchTarget $wp
        if (-not (Test-Path $Target)) {
            Write-Warning "FAST-GATE: Watch path '$wp' does not exist; its hash is not recorded."
            continue
        }
        $tree = Get-WatchTreeHash $wp $Target
        if ($tree) { $hashes[$wp] = $tree }
    }
    $wm['sentinel_id'] = $SentinelName
    $wm['timestamp'] = (Get-Date).ToUniversalTime().ToString("o")
    $wm['tree_hashes'] = $hashes
    $dir = Split-Path -Parent $FullWatermarkPath
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $wm | ConvertTo-Json -Depth 10 | Set-Content -Path $FullWatermarkPath -Encoding utf8
    Write-Host "FAST-GATE: Watermark written for '$SentinelName' ($($hashes.Count) tree hashes)."
}

# Release mode
if ($Release) {
    if (Test-Path $FullLockPath) {
        try {
            $LockContent = Get-Content $FullLockPath -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
            if ($LockContent.held_by -eq $SentinelName -or -not $LockContent.held_by) {
                if ($WriteWatermark) { Write-GateWatermark }
                Remove-Item $FullLockPath -Force -ErrorAction SilentlyContinue
                Write-Host "FAST-GATE: Lock successfully released by '$SentinelName'."
            } else {
                Write-Host "FAST-GATE: Lock held by '$($LockContent.held_by)', not '$SentinelName'. Leaving lock intact."
            }
        } catch {
            if ($WriteWatermark) { Write-GateWatermark }
            Remove-Item $FullLockPath -Force -ErrorAction SilentlyContinue
            Write-Host "FAST-GATE: Corrupt lock removed."
        }
    } else {
        if ($WriteWatermark) { Write-GateWatermark }
        Write-Host "FAST-GATE: No lock to release."
    }
    exit 0
}

# 1. Fast Lock Check & Stale Lock Cleanup (Finding 4 Fix)
if (Test-Path $FullLockPath) {
    $IsStale = $false
    try {
        $LockContent = Get-Content $FullLockPath -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
        $AcquiredTime = ConvertTo-UtcDate $LockContent.acquired_at
        $AgeMinutes = ((Get-Date).ToUniversalTime() - $AcquiredTime).TotalMinutes
        if ($AgeMinutes -lt 0) { $AgeMinutes = 0 }

        if ($AgeMinutes -lt $LockTimeoutMinutes) {
            if ($Force) {
                Write-Host "FAST-GATE: -Force specified. Overriding lock held by '$($LockContent.held_by)'."
                $IsStale = $true
            } else {
                Write-Host "FAST-GATE: Lock actively held by '$($LockContent.held_by)' ($([math]::Round($AgeMinutes, 1)) min old < $LockTimeoutMinutes min). Backing off."
                exit 10
            }
        } else {
            $BrainDir = if ($env:ANTIGRAVITY_BRAIN_DIR) { $env:ANTIGRAVITY_BRAIN_DIR } else { Join-Path $HOME ".gemini\antigravity\brain" }
            $HasRecentBrainActivity = $false
            if (-not $Force -and $LockContent.host -eq $env:COMPUTERNAME -and $AgeMinutes -lt 55 -and (Test-Path $BrainDir)) {
                $RecentCutoff = (Get-Date).AddMinutes(-5)
                $ActiveLogs = Get-ChildItem -Path $BrainDir -Filter "transcript.jsonl" -Recurse -ErrorAction SilentlyContinue |
                    Where-Object { $_.LastWriteTime -gt $RecentCutoff }
                if ($ActiveLogs) { $HasRecentBrainActivity = $true }
            }
            if ($HasRecentBrainActivity) {
                Write-Host "FAST-GATE: Lock held by '$($LockContent.held_by)' is $([math]::Round($AgeMinutes, 1)) min old (>= $LockTimeoutMinutes min), but active brain session transcript modified within 5 min on $($env:COMPUTERNAME). Backing off."
                exit 10
            }
            Write-Host "FAST-GATE: Lock held by '$($LockContent.held_by)' is stale ($([math]::Round($AgeMinutes, 1)) min old >= $LockTimeoutMinutes min). Removing stale lock."
            $IsStale = $true
        }
    } catch {
        # Corrupt lock file
        $IsStale = $true
    }

    if ($IsStale) {
        Remove-Item $FullLockPath -Force -ErrorAction SilentlyContinue
    }
}

# 2. Fast Delta Check (F-01, F-02, F-03: Multi-candidate key lookup & worktree sibling path resolution)
if (-not $Force -and $WatermarkFile -and ($WatchPaths.Count -gt 0)) {
    # Ensure remote changes are fetched so HEAD comparison does not miss remote PR merges
    git -C $cfLab fetch origin --quiet 2>$null
    $FullWatermarkPath = if ([System.IO.Path]::IsPathRooted($WatermarkFile)) {
        $WatermarkFile
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $cfLab $WatermarkFile))
    }

    if (Test-Path $FullWatermarkPath) {
        try {
            $Watermark = Get-Content $FullWatermarkPath -Raw | ConvertFrom-Json
            $AllMatch = $true
            
            foreach ($wp in $WatchPaths) {
                $Target = Resolve-WatchTarget $wp

                if (-not (Test-Path $Target)) {
                    Write-Warning "FAST-GATE: Watch path '$wp' resolved to '$Target' which does not exist. Treating as delta to avoid silent lockouts."
                    $AllMatch = $false
                    break
                }

                if (Test-Path $Target) {
                    $ParentDir = Split-Path -Parent $Target
                    $BaseName = Split-Path -Leaf $Target
                    
                    $CurrentTree = Get-WatchTreeHash $wp $Target

                    # F-01: Multi-candidate key lookup for watermark compatibility (including repo-relative paths)
                    $RepoRootOfTarget = (git -C $ParentDir rev-parse --show-toplevel 2>$null)
                    $RelToRepo = if ($RepoRootOfTarget) { [System.IO.Path]::GetRelativePath($RepoRootOfTarget, $Target).Replace('\', '/') } else { $null }
                    $RelToRepoClean = if ($RelToRepo) { $RelToRepo.Replace('/', '_').Replace('.', '_') } else { $null }
                    $KeyClean = $wp.Replace('/', '_').Replace('\\', '_').Replace('.', '_')
                    $KeyAlt = $wp.Replace('/', '_').Replace('\\', '_')
                    $BaseClean = $BaseName.Replace('.', '_')

                    $SavedTree = $null
                    if ($Watermark.tree_hashes.$wp) {
                        $SavedTree = $Watermark.tree_hashes.$wp
                    } elseif ($RelToRepo -and $Watermark.tree_hashes.$RelToRepo) {
                        $SavedTree = $Watermark.tree_hashes.$RelToRepo
                    } elseif ($RelToRepoClean -and $Watermark.tree_hashes.$RelToRepoClean) {
                        $SavedTree = $Watermark.tree_hashes.$RelToRepoClean
                    } elseif ($Watermark.tree_hashes.$BaseName) {
                        $SavedTree = $Watermark.tree_hashes.$BaseName
                    } elseif ($Watermark.tree_hashes.$BaseClean) {
                        $SavedTree = $Watermark.tree_hashes.$BaseClean
                    } elseif ($Watermark.tree_hashes.$KeyClean) {
                        $SavedTree = $Watermark.tree_hashes.$KeyClean
                    } elseif ($Watermark.tree_hashes.$KeyAlt) {
                        $SavedTree = $Watermark.tree_hashes.$KeyAlt
                    }

                    if (-not $SavedTree -or ($SavedTree -ne $CurrentTree)) {
                        $AllMatch = $false
                        break
                    }
                }
            }
            
            if ($AllMatch -and $MaxIdleHours -gt 0) {
                $Stamp = $null
                try { $Stamp = ConvertTo-UtcDate $Watermark.timestamp } catch { }
                if (-not $Stamp) { $Stamp = (Get-Item $FullWatermarkPath).LastWriteTimeUtc }
                $IdleHours = ((Get-Date).ToUniversalTime() - $Stamp).TotalHours
                if ($IdleHours -ge $MaxIdleHours) {
                    Write-Host "FAST-GATE: Heartbeat due (watermark $([math]::Round($IdleHours, 1)) h old >= $MaxIdleHours h). Proceeding although no tree changed."
                    $AllMatch = $false
                }
            }

            if ($AllMatch) {
                Write-Host "FAST-GATE: Zero git tree deltas across watch paths compared to watermark ($WatermarkFile). Clean idle exit."
                exit 20
            }
        } catch {
            # On error in delta parsing, fall through to acquire lock
        }
    }
}

# 3. Atomic Lock Acquisition (Finding 3 Fix: Prevents TOCTOU Race Condition)
$ParentLockDir = Split-Path -Parent $FullLockPath
if (-not (Test-Path $ParentLockDir)) {
    New-Item -ItemType Directory -Path $ParentLockDir -Force | Out-Null
}

$LockPayload = @{
    sentinel_id = $SentinelName
    held_by     = $SentinelName
    acquired_at = (Get-Date).ToString("o")
    pid         = $PID
    host        = $env:COMPUTERNAME
} | ConvertTo-Json

try {
    # Atomic file creation: fails if file already exists
    $FileStream = [System.IO.File]::Open(
        $FullLockPath,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None
    )
    $Writer = New-Object System.IO.StreamWriter($FileStream, [System.Text.Encoding]::UTF8)
    $Writer.Write($LockPayload)
    $Writer.Flush()
    $Writer.Close()
    $FileStream.Close()
    Write-Host "FAST-GATE: Lock atomically acquired for '$SentinelName'. Proceeding with workflow."
    exit 0
} catch [System.IO.IOException] {
    if ($Force) {
        Set-Content -Path $FullLockPath -Value $LockPayload -Encoding utf8
        Write-Host "FAST-GATE: Lock forced for '$SentinelName' (-Force override). Proceeding with workflow."
        exit 0
    }
    # Another sentinel acquired the lock between check and create
    Write-Host "FAST-GATE: Lock acquisition collision (another process acquired simultaneously). Backing off."
    exit 10
} catch {
    # Fallback write if permissions allow
    Set-Content -Path $FullLockPath -Value $LockPayload -Encoding utf8
    Write-Host "FAST-GATE: Lock acquired for '$SentinelName' (fallback). Proceeding with workflow."
    exit 0
}
