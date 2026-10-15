<#
.SYNOPSIS
    Renders the sentinel sidecar.json files from tasks/sentinels.json.

.DESCRIPTION
    The manifest is the single source of truth for each sentinel's cadence, display name and the
    wrapper command. This script only touches args, display_name and description of each existing
    sidecar.json and keeps the rest (agent_permissions, restart_policy, ...).

      (default)  print what would change, write nothing
      -Check     exit 1 when any sidecar differs from the manifest (exit 0 when all match)
      -Install   write the changes; the first time, keep the old file as sidecar.json.bak-pre-render

    -SidecarRoot and -RepoRoot exist for tests. -RepoRoot is the checkout the cron job should run:
    by default the main checkout (never a worktree), found through the git common directory.
#>
[CmdletBinding()]
param(
    [switch]$Check,

    [switch]$Install,

    [string]$ManifestFile = "",

    [string]$SidecarRoot = "",

    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $PSScriptRoot
if (-not $ManifestFile) { $ManifestFile = Join-Path $PSScriptRoot "sentinels.json" }
if (-not $SidecarRoot) { $SidecarRoot = Join-Path $env:USERPROFILE ".gemini/config/sidecars" }
if (-not $RepoRoot) {
    $common = (git -C $here rev-parse --path-format=absolute --git-common-dir 2>$null)
    $RepoRoot = if ($common) { Split-Path -Parent $common } else { $here }
}

$manifest = Get-Content $ManifestFile -Raw | ConvertFrom-Json
$wrapper = (Join-Path $RepoRoot "tasks/run-sentinel.ps1").Replace('\', '/')
$drift = 0

foreach ($name in $manifest.sentinels.PSObject.Properties.Name) {
    $cfg = $manifest.sentinels.$name
    $file = Join-Path $SidecarRoot (Join-Path $cfg.sidecar_dir "sidecar.json")
    if (-not (Test-Path $file)) {
        Write-Host "MISSING  $name ($file) - create the sidecar once in the app, then re-run."
        $drift++
        continue
    }
    $j = Get-Content $file -Raw | ConvertFrom-Json
    $wantArgs = @(
        "CRON_TZ=$($manifest.timezone) $($cfg.cron)",
        "pwsh", "-NoProfile", "-File", $wrapper, "-SentinelName", $name
    )
    $sameArgs = (@($j.args) -join "`n") -eq ($wantArgs -join "`n")
    $same = $sameArgs -and ($j.display_name -eq $cfg.display_name) -and ($j.description -eq $cfg.description)
    if ($same) {
        Write-Host "OK       $name  ($($cfg.cron))"
        continue
    }
    $drift++
    Write-Host "DRIFT    $name"
    Write-Host "           now : $(@($j.args)[0])"
    Write-Host "           want: $($wantArgs[0])"
    if ($Install) {
        $bak = "$file.bak-pre-render"
        if (-not (Test-Path $bak)) { Copy-Item $file $bak }
        $j.args = $wantArgs
        $j.display_name = $cfg.display_name
        $j.description = $cfg.description
        $j | ConvertTo-Json -Depth 20 | Set-Content -Path $file -Encoding utf8
        Write-Host "           written."
    }
}

if ($Check -and $drift -gt 0) { exit 1 }
exit 0
