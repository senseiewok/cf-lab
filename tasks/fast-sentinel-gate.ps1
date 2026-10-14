<#
.SYNOPSIS
    Fast deterministic pre-flight gate for scheduled sentinels.
    Evaluates lock contention and git tree hash deltas in <100ms with ZERO token burn.

.DESCRIPTION
    Exits:
      0  - Lock acquired, real deltas detected (proceed with full workflow)
      10 - Lock held by another active sentinel (back off immediately)
      20 - Idle, zero git deltas since last watermark (terminate immediately)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SentinelName,

    [switch]$Release,

    [string]$LockFile = ".loop-logs/sentinel.lock",

    [string]$WatermarkFile = "",

    [string[]]$WatchPaths = @(),

    [int]$LockTimeoutMinutes = 30
)

$ErrorActionPreference = "Stop"

# Normalize WatchPaths if passed as comma-separated or PowerShell array literal string
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

if ([System.IO.Path]::IsPathRooted($LockFile)) {
    $FullLockPath = $LockFile
} else {
    $FullLockPath = [System.IO.Path]::GetFullPath((Join-Path $cfLab $LockFile))
}

# Release mode
if ($Release) {
    if (Test-Path $FullLockPath) {
        try {
            $LockContent = Get-Content $FullLockPath -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
            if ($LockContent.held_by -eq $SentinelName -or -not $LockContent.held_by) {
                Remove-Item $FullLockPath -Force -ErrorAction SilentlyContinue
                Write-Host "FAST-GATE: Lock successfully released by '$SentinelName'."
            } else {
                Write-Host "FAST-GATE: Lock held by '$($LockContent.held_by)', not '$SentinelName'. Leaving lock intact."
            }
        } catch {
            Remove-Item $FullLockPath -Force -ErrorAction SilentlyContinue
            Write-Host "FAST-GATE: Corrupt lock removed."
        }
    } else {
        Write-Host "FAST-GATE: No lock to release."
    }
    exit 0
}

# 1. Fast Lock Check & Stale Lock Cleanup (Finding 4 Fix)
if (Test-Path $FullLockPath) {
    $IsStale = $false
    try {
        $LockContent = Get-Content $FullLockPath -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
        $AcquiredTime = [datetime]::Parse($LockContent.acquired_at)
        $AgeMinutes = ((Get-Date) - $AcquiredTime).TotalMinutes

        if ($AgeMinutes -lt $LockTimeoutMinutes) {
            Write-Host "FAST-GATE: Lock actively held by '$($LockContent.held_by)' ($([math]::Round($AgeMinutes, 1)) min old < $LockTimeoutMinutes min). Backing off."
            exit 10
        } else {
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
if ($WatermarkFile -and ($WatchPaths.Count -gt 0)) {
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
                $Target = if ([System.IO.Path]::IsPathRooted($wp)) {
                    $wp
                } else {
                    [System.IO.Path]::GetFullPath((Join-Path $cfLab $wp))
                }

                # F-02: Worktree sibling repo resolution fallback (when $cfLab is in .worktrees/<repo>/<topic>)
                if (-not (Test-Path $Target)) {
                    if ($cfLab -like "*\.worktrees*") {
                        $parent = Split-Path -Parent $cfLab
                        while ($parent -and (Split-Path -Leaf $parent) -ne ".worktrees") {
                            $parent = Split-Path -Parent $parent
                        }
                        if ($parent) {
                            $reposRoot = Split-Path -Parent $parent
                            $strippedWp = $wp.TrimStart('.').TrimStart('/').TrimStart('\')
                            $WorktreeTarget = [System.IO.Path]::GetFullPath((Join-Path $reposRoot $strippedWp))
                            if (Test-Path $WorktreeTarget) {
                                $Target = $WorktreeTarget
                            }
                        }
                    }
                }

                if (Test-Path $Target) {
                    $ParentDir = Split-Path -Parent $Target
                    $BaseName = Split-Path -Leaf $Target
                    
                    # 'HEAD:./$BaseName' makes Git resolve relative to $ParentDir
                    $CurrentTree = (git -C $ParentDir rev-parse "HEAD:./$BaseName" 2>$null)
                    if (-not $CurrentTree) {
                        # Fallback for full repo relative path
                        $RelPath = $wp.Replace('\', '/')
                        $CurrentTree = (git -C $cfLab rev-parse "HEAD:$RelPath" 2>$null)
                    }

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
    # Another sentinel acquired the lock between check and create
    Write-Host "FAST-GATE: Lock acquisition collision (another process acquired simultaneously). Backing off."
    exit 10
} catch {
    # Fallback write if permissions allow
    Set-Content -Path $FullLockPath -Value $LockPayload -Encoding utf8
    Write-Host "FAST-GATE: Lock acquired for '$SentinelName' (fallback). Proceeding with workflow."
    exit 0
}
