#Requires -Version 7
<#
.SYNOPSIS
  Render tasks/board.json to tasks/BOARD.md. Requires PowerShell 7+.

.DESCRIPTION
  board.json is the source of truth. This script sorts tasks by priority, then ROI index, then id,
  groups them by status, and writes a Markdown board a human can read in the repo.
  Run it after editing board.json. With -Check it exits 1 when BOARD.md is stale, so it
  can serve as a pre-commit or CI guard.

  Optional per-task fields: complexity (low, medium, high), recommended_route (local, cloud, frontier), route_rationale
  (required, non-empty, when a route is set), branch (git branch name for active worktree/branch coordination),
  persona (patients, care_teams, researchers, builders), discipline (structural_biology, rna_gene_editing, airway_delivery,
  microbiology_host, clinical_trials, ai_verification), work_kind (new, repair, maintenance), and
  evidence_package (structured object linking durable primary evidence packet, claims JSON, catalog sources, and answer tier).
  Other values are rejected with exit 2. Case-sensitive.

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
    [switch]$Check,
    [int]$MaxProposedP1 = 15
)

$ErrorActionPreference = 'Stop'
$here = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $BoardPath) { $BoardPath = Join-Path $here 'board.json' }
if (-not $OutPath)   { $OutPath   = Join-Path $here 'BOARD.md' }

$rawBytes = [System.IO.File]::ReadAllBytes($BoardPath)
if ($rawBytes.Length -ge 3 -and $rawBytes[0] -eq 0xEF -and $rawBytes[1] -eq 0xBB -and $rawBytes[2] -eq 0xBF) {
    Write-Error "$BoardPath begins with a UTF-8 byte-order mark (ef bb bf); save as UTF-8 without BOM" -ErrorAction Continue
    exit 2
}
$board = Get-Content -Raw -Path $BoardPath -Encoding UTF8 | ConvertFrom-Json

$requiredFields = 'id','title','repo','status','priority','created_at','created_by','source_evidence','effort_hours','roi','acceptance','review_tier'
$validPersonas = 'patients','care_teams','researchers','builders'
$validDisciplines = 'structural_biology','rna_gene_editing','airway_delivery','microbiology_host','clinical_trials','ai_verification'
$validWorkKinds = 'new','repair','maintenance'
$errors = @()
$ids = @{}
$byId = @{}
foreach ($t in $board.tasks) {
    foreach ($f in $requiredFields) {
        if (-not ($t.PSObject.Properties.Name -contains $f) -or $null -eq $t.$f) { $errors += "$($t.id): missing field '$f'" }
    }
    if ($ids.ContainsKey($t.id)) { $errors += "duplicate id $($t.id)" } else { $ids[$t.id] = $true; $byId[$t.id] = $t }
    if ($t.created_by.kind -notin 'model','human') { $errors += "$($t.id): created_by.kind must be model or human" }
    if ($t.created_by.kind -eq 'model' -and -not $t.created_by.model_id) { $errors += "$($t.id): model-created task needs model_id" }
    if ($t.status -notin 'proposed','ready','in_progress','blocked','done','dropped') { $errors += "$($t.id): bad status '$($t.status)'" }
    if ($t.priority -notmatch '^P[0-3]$') { $errors += "$($t.id): bad priority '$($t.priority)'" }
    if ($t.roi.benefit -lt 1 -or $t.roi.benefit -gt 5) { $errors += "$($t.id): roi.benefit must be 1-5" }
    if ($t.PSObject.Properties.Name -contains 'complexity' -and $null -ne $t.complexity -and $t.complexity -cnotin 'low', 'medium', 'high') { $errors += "$($t.id): complexity must be low, medium or high" }
    if ($t.PSObject.Properties.Name -contains 'recommended_route' -and $null -ne $t.recommended_route) {
        if ($t.recommended_route -cnotin 'local', 'cloud', 'frontier') { $errors += "$($t.id): recommended_route must be local, cloud or frontier" }
        elseif ([string]::IsNullOrWhiteSpace([string]$t.route_rationale)) { $errors += "$($t.id): route_rationale is required when recommended_route is set" }
    }
    if ($t.PSObject.Properties.Name -contains 'persona' -and $null -ne $t.persona -and [string]$t.persona -ne '') {
        if ([string]$t.persona -cnotin $validPersonas) {
            $errors += "$($t.id): persona must be patients, care_teams, researchers or builders"
        }
    }
    if ($t.PSObject.Properties.Name -contains 'discipline' -and $null -ne $t.discipline -and [string]$t.discipline -ne '') {
        if ([string]$t.discipline -cnotin $validDisciplines) {
            $errors += "$($t.id): discipline must be one of $($validDisciplines -join ', ')"
        }
    }
    if ($t.PSObject.Properties.Name -contains 'work_kind' -and $null -ne $t.work_kind -and [string]$t.work_kind -ne '') {
        if ([string]$t.work_kind -cnotin $validWorkKinds) {
            $errors += "$($t.id): work_kind must be new, repair or maintenance"
        }
    }
    if ($t.PSObject.Properties.Name -contains 'branch' -and $null -ne $t.branch -and [string]$t.branch -ne '') {
        $b = [string]$t.branch
        if ($b -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$' -or $b -match '\.\.|//|/$|\.lock$') {
            $errors += "$($t.id): bad branch '$b'"
        }
    }
    if ($t.PSObject.Properties.Name -contains 'evidence_package' -and $null -ne $t.evidence_package) {
        $ep = $t.evidence_package
        if (-not ($ep.PSObject.Properties.Name -contains 'packet_path') -or [string]::IsNullOrWhiteSpace($ep.packet_path)) {
            $errors += "$($t.id): evidence_package requires non-empty 'packet_path'"
        }
        if ($ep.PSObject.Properties.Name -contains 'answer_tier' -and $null -ne $ep.answer_tier -and $ep.answer_tier -cnotin 'T0','T1','T2','T3') {
            $errors += "$($t.id): evidence_package.answer_tier must be T0, T1, T2, or T3"
        }
    }
    if ($t.PSObject.Properties.Name -contains 'spec_path' -and $null -ne $t.spec_path -and [string]$t.spec_path -ne '') {
        $sp = [string]$t.spec_path
        if ($sp -notmatch '^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.md$' -or $sp -match '\.\.') {
            $errors += "$($t.id): bad spec_path '$sp'"
        }
    }
    if ($t.status -notin 'done','dropped' -and [string]$t.notes -match '(?:^|\|\s*|\r?\n)\s*(?:\d{4}-\d{2}-\d{2}[^:]*:\s*)?Done\b') {
        $errors += "$($t.id): notes say Done while status is '$($t.status)' (close the task or write 'Agent part done')"
    }
}
foreach ($t in $board.tasks) {
    foreach ($d in $t.depends_on) {
        if (-not $ids.ContainsKey($d)) {
            $errors += "$($t.id): depends_on unknown $d"
            continue
        }
        $dep = $byId[$d]
        if ($t.status -eq 'in_progress' -and $dep.status -ne 'done') {
            $errors += "$($t.id): in_progress task depends on $d ($($dep.status), not done)"
        }
        if ($t.status -notin 'done','dropped' -and $dep.status -notin 'done','dropped' -and [string]$t.priority -lt [string]$dep.priority) {
            $errors += "$($t.id) ($($t.priority)) has higher priority than unfinished dependency $d ($($dep.priority))"
        }
    }
}
$proposedP1 = @($board.tasks | Where-Object { $_.status -eq 'proposed' -and $_.priority -eq 'P1' }).Count
if ($proposedP1 -gt $MaxProposedP1) {
    $errors += "proposed P1 count ($proposedP1) exceeds MaxProposedP1 ($MaxProposedP1)"
}
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
# PowerShell 7 parses ISO timestamps in JSON to DateTime, Windows PowerShell 5.1 keeps them as strings, and a
# culture-formatted DateTime ([string] or .ToString()) differs between the two. Normalise either form to the UTC
# calendar date in culture-invariant ISO form, so both shells render byte-identical output.
function IsoDate($v) {
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    if ($null -eq $v) { return '' }
    if ($v -is [datetimeoffset]) { return $v.UtcDateTime.ToString('yyyy-MM-dd', $inv) }
    if ($v -is [datetime]) {
        $d = if ($v.Kind -eq [DateTimeKind]::Local) { $v.ToUniversalTime() } else { $v }
        return $d.ToString('yyyy-MM-dd', $inv)
    }
    $s = [string]$v
    $styles = [System.Globalization.DateTimeStyles]::AssumeUniversal
    $parsed = [datetimeoffset]::MinValue
    if ([datetimeoffset]::TryParse($s, $inv, $styles, [ref]$parsed)) { return $parsed.UtcDateTime.ToString('yyyy-MM-dd', $inv) }
    return $s
}

# id is the final tie-breaker: Sort-Object is stable in PowerShell 7 but not in 5.1, so ties need a fixed order.
$sorted = $board.tasks | Sort-Object @{Expression='priority'}, @{Expression={ -(RoiIndex $_) }}, @{Expression='id'}
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
    [void]$sb.AppendLine('| ID | P | Task | Repo | Hours | Benefit | ROI idx | Measured | Created by | Created | Review | Complexity | Route | Depends on | Branch |')
    [void]$sb.AppendLine('| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |')
    foreach ($t in $group) {
        $hours = "$($t.effort_hours.low)-$($t.effort_hours.high)"
        $deps = if ($t.depends_on) { ($t.depends_on -join ', ') } else { '' }
        $branch = if ($t.PSObject.Properties.Name -contains 'branch' -and $null -ne $t.branch) { Esc $t.branch } else { '' }
        $meas = if ($t.roi.measured) { 'yes' } else { 'no' }
        $date = IsoDate $t.created_at
        $evBadge = ''
        if ($t.PSObject.Properties.Name -contains 'evidence_package' -and $null -ne $t.evidence_package) {
            $tier = if ($t.evidence_package.PSObject.Properties.Name -contains 'answer_tier' -and $t.evidence_package.answer_tier) { $t.evidence_package.answer_tier } else { 'ev' }
            $evBadge = " `[$tier`]"
        }
        [void]$sb.AppendLine("| $($t.id) | $($t.priority) | $(Esc $t.title)$evBadge | $($t.repo) | $hours | $($t.roi.benefit) | $(RoiIndex $t) | $meas | $(Who $t) | $date | $($t.review_tier) | $($t.complexity) | $($t.recommended_route) | $deps | $branch |")
    }
    [void]$sb.AppendLine()
}

[void]$sb.AppendLine('## Detail')
[void]$sb.AppendLine()
foreach ($t in $sorted) {
    [void]$sb.AppendLine("### $($t.id) $(Esc $t.title)")
    [void]$sb.AppendLine()
    [void]$sb.AppendLine("- **Why / ROI rationale:** $(Esc $t.roi.rationale) *(confidence: $($t.roi.confidence))*")
    $axisParts = @()
    if ($t.PSObject.Properties.Name -contains 'persona' -and $t.persona) { $axisParts += "Persona: $($t.persona)" }
    if ($t.PSObject.Properties.Name -contains 'discipline' -and $t.discipline) { $axisParts += "Discipline: $($t.discipline)" }
    if ($t.PSObject.Properties.Name -contains 'work_kind' -and $t.work_kind) { $axisParts += "Kind: $($t.work_kind)" }
    if ($axisParts.Count -gt 0) { [void]$sb.AppendLine("- **Axis:** $($axisParts -join ' | ')") }
    if ($t.recommended_route) { [void]$sb.AppendLine("- **Route:** $($t.recommended_route) - $(Esc $t.route_rationale)") }
    if ($t.PSObject.Properties.Name -contains 'branch' -and $t.branch) { [void]$sb.AppendLine("- **Branch:** $(Esc $t.branch)") }
    [void]$sb.AppendLine("- **Acceptance:** $(Esc $t.acceptance)")
    [void]$sb.AppendLine("- **Evidence:** $(Esc $t.source_evidence)")
    if ($t.PSObject.Properties.Name -contains 'evidence_package' -and $null -ne $t.evidence_package) {
        $ep = $t.evidence_package
        $claimsNote = if ($ep.PSObject.Properties.Name -contains 'claims_file' -and $null -ne $ep.claims_file -and [string]$ep.claims_file) { " | Claims: ``$($ep.claims_file)``" } else { "" }
        $sourcesNote = if ($ep.PSObject.Properties.Name -contains 'catalog_sources' -and $null -ne $ep.catalog_sources -and $ep.catalog_sources.Count -gt 0) { " | Sources: $($ep.catalog_sources -join ', ')" } else { "" }
        $tierNote = if ($ep.PSObject.Properties.Name -contains 'answer_tier' -and $ep.answer_tier) { "Tier: $($ep.answer_tier)" } else { "Tier: unranked" }
        [void]$sb.AppendLine("- **Evidence Package:** ``$($ep.packet_path)`` *($tierNote$claimsNote$sourcesNote)*")
    }
    if ($t.PSObject.Properties.Name -contains 'spec_path' -and $t.spec_path) { [void]$sb.AppendLine("- **Spec:** ``$($t.spec_path)``") }
    if ($t.notes) { [void]$sb.AppendLine("- **Notes:** $(Esc $t.notes)") }
    if ($t.roi.measured) {
        $actual = if ($t.roi.PSObject.Properties.Name -contains 'actual_hours' -and $null -ne $t.roi.actual_hours) { $t.roi.actual_hours }
                  elseif ($t.roi.measured.PSObject.Properties.Name -contains 'actual_hours') { $t.roi.measured.actual_hours }
                  else { '' }
        $outc = if ($t.roi.PSObject.Properties.Name -contains 'measured_outcome' -and $null -ne $t.roi.measured_outcome) { $t.roi.measured_outcome }
                elseif ($t.roi.measured.PSObject.Properties.Name -contains 'notes') { $t.roi.measured.notes }
                else { '' }
        [void]$sb.AppendLine("- **Measured:** $actual h; $(Esc $outc)")
    }
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
