<#
.SYNOPSIS
  Render tasks/board.json to tasks/BOARD.md. No dependencies beyond PowerShell 5.1+.

.DESCRIPTION
  board.json is the source of truth. This script sorts tasks by priority then ROI index,
  groups them by status, and writes a Markdown board a human can read in the repo.
  Run it after editing board.json. With -Check it exits 1 when BOARD.md is stale, so it
  can serve as a pre-commit or CI guard.

  Optional per-task fields: complexity (low, medium, high), recommended_route (local, cloud, frontier) and route_rationale
  (required, non-empty, when a route is set). Other values are rejected with exit 2. Case-sensitive.

  ROI index = benefit * 10 / midpoint effort hours. It is a ranking aid computed from
  estimates, not a measurement. The `measured` flag on each task says whether anyone
  has recorded actual hours and an outcome yet.

.EXAMPLE
  pwsh -File tasks/render-board.ps1
  pwsh -File tasks/render-board.ps1 -Check
#>
[CmdletBinding()]
param(
    [string]$BoardPath,
    [string]$OutPath,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $BoardPath) { $BoardPath = Join-Path $here 'board.json' }
if (-not $OutPath)   { $OutPath   = Join-Path $here 'BOARD.md' }
$board = Get-Content -Raw -Path $BoardPath -Encoding UTF8 | ConvertFrom-Json

$requiredFields = 'id','title','repo','status','priority','created_at','created_by','source_evidence','effort_hours','roi','acceptance','review_tier'
$errors = @()
$ids = @{}
foreach ($t in $board.tasks) {
    foreach ($f in $requiredFields) {
        if (-not ($t.PSObject.Properties.Name -contains $f) -or $null -eq $t.$f) { $errors += "$($t.id): missing field '$f'" }
    }
    if ($ids.ContainsKey($t.id)) { $errors += "duplicate id $($t.id)" } else { $ids[$t.id] = $true }
    if ($t.created_by.kind -notin 'model','human') { $errors += "$($t.id): created_by.kind must be model or human" }
    if ($t.created_by.kind -eq 'model' -and -not $t.created_by.model_id) { $errors += "$($t.id): model-created task needs model_id" }
    if ($t.status -notin 'proposed','ready','in_progress','blocked','done','dropped') { $errors += "$($t.id): bad status '$($t.status)'" }
    if ($t.priority -notmatch '^P[0-3]$') { $errors += "$($t.id): bad priority '$($t.priority)'" }
    if ($t.roi.benefit -lt 1 -or $t.roi.benefit -gt 5) { $errors += "$($t.id): roi.benefit must be 1-5" }
    if ($t.PSObject.Properties.Name -contains 'complexity' -and $t.complexity -cnotin 'low', 'medium', 'high') { $errors += "$($t.id): complexity must be low, medium or high" }
    if ($t.PSObject.Properties.Name -contains 'recommended_route') {
        if ($t.recommended_route -cnotin 'local', 'cloud', 'frontier') { $errors += "$($t.id): recommended_route must be local, cloud or frontier" }
        elseif ([string]::IsNullOrWhiteSpace([string]$t.route_rationale)) { $errors += "$($t.id): route_rationale is required when recommended_route is set" }
    }
}
foreach ($t in $board.tasks) { foreach ($d in $t.depends_on) { if (-not $ids.ContainsKey($d)) { $errors += "$($t.id): depends_on unknown $d" } } }
if ($errors) { $errors | ForEach-Object { Write-Error $_ -ErrorAction Continue }; exit 2 }

function RoiIndex($t) {
    $mid = ([double]$t.effort_hours.low + [double]$t.effort_hours.high) / 2
    if ($mid -le 0) { return 0 }
    return [math]::Round(([double]$t.roi.benefit * 10) / $mid, 1)
}
function Who($t) {
    if ($t.created_by.kind -eq 'model') { return "model: $($t.created_by.model_id)" }
    return "human: $($t.created_by.name)"
}
function Esc($s) { return ([string]$s) -replace '\|', '\|' -replace "`r?`n", ' ' }

$sorted = $board.tasks | Sort-Object @{Expression='priority'}, @{Expression={ -(RoiIndex $_) }}
$statuses = 'in_progress','ready','proposed','blocked','done','dropped'
$total = $board.tasks.Count
$measured = @($board.tasks | Where-Object { $_.roi.measured }).Count
$byModel = @($board.tasks | Where-Object { $_.created_by.kind -eq 'model' }).Count
$lowSum = 0.0; $highSum = 0.0
foreach ($t in $board.tasks) { $lowSum += [double]$t.effort_hours.low; $highSum += [double]$t.effort_hours.high }

$sb = New-Object System.Text.StringBuilder
[void]$sb.AppendLine('# Task board')
[void]$sb.AppendLine()
[void]$sb.AppendLine('Generated from `board.json` by `render-board.ps1`. Edit the JSON, not this file.')
[void]$sb.AppendLine()
[void]$sb.AppendLine("$total tasks, $byModel created by a model, $measured with a measured outcome. Estimated effort $lowSum to $highSum hours in total. ROI index is benefit x 10 / midpoint hours: a ranking aid from estimates, not a result.")
[void]$sb.AppendLine()

foreach ($s in $statuses) {
    $group = @($sorted | Where-Object { $_.status -eq $s })
    if ($group.Count -eq 0) { continue }
    [void]$sb.AppendLine("## $($s.Replace('_',' ')) ($($group.Count))")
    [void]$sb.AppendLine()
    [void]$sb.AppendLine('| ID | P | Task | Repo | Hours | Benefit | ROI idx | Measured | Created by | Created | Review | Complexity | Route | Depends on |')
    [void]$sb.AppendLine('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    foreach ($t in $group) {
        $hours = "$($t.effort_hours.low)-$($t.effort_hours.high)"
        $deps = if ($t.depends_on) { ($t.depends_on -join ', ') } else { '' }
        $meas = if ($t.roi.measured) { 'yes' } else { 'no' }
        $date = ([string]$t.created_at).Substring(0,10)
        [void]$sb.AppendLine("| $($t.id) | $($t.priority) | $(Esc $t.title) | $($t.repo) | $hours | $($t.roi.benefit) | $(RoiIndex $t) | $meas | $(Who $t) | $date | $($t.review_tier) | $($t.complexity) | $($t.recommended_route) | $deps |")
    }
    [void]$sb.AppendLine()
}

[void]$sb.AppendLine('## Detail')
[void]$sb.AppendLine()
foreach ($t in $sorted) {
    [void]$sb.AppendLine("### $($t.id) $(Esc $t.title)")
    [void]$sb.AppendLine()
    [void]$sb.AppendLine("- **Why / ROI rationale:** $(Esc $t.roi.rationale) *(confidence: $($t.roi.confidence))*")
    if ($t.recommended_route) { [void]$sb.AppendLine("- **Route:** $($t.recommended_route) - $(Esc $t.route_rationale)") }
    [void]$sb.AppendLine("- **Acceptance:** $(Esc $t.acceptance)")
    [void]$sb.AppendLine("- **Evidence:** $(Esc $t.source_evidence)")
    if ($t.notes) { [void]$sb.AppendLine("- **Notes:** $(Esc $t.notes)") }
    if ($t.roi.measured) { [void]$sb.AppendLine("- **Measured:** $($t.roi.actual_hours) h; $(Esc $t.roi.measured_outcome)") }
    [void]$sb.AppendLine()
}

$rendered = $sb.ToString()
if ($Check) {
    $existing = if (Test-Path $OutPath) { Get-Content -Raw -Path $OutPath -Encoding UTF8 } else { '' }
    if ($existing -ne $rendered) { Write-Error 'BOARD.md is stale; run render-board.ps1' -ErrorAction Continue; exit 1 }
    Write-Output 'BOARD.md is current'; exit 0
}
[System.IO.File]::WriteAllText($OutPath, $rendered, (New-Object System.Text.UTF8Encoding $false))
Write-Output "wrote $OutPath ($total tasks)"
