<#
.SYNOPSIS
  Summarize distill-loop benchmark runs across all cases.

.DESCRIPTION
  Reads every case's attempts.jsonl, keeps attempts whose label starts with -LabelPrefix, and
  groups them into runs (label + model profile + case). Prints, per model profile:
  how many runs were accepted, the average attempt number at acceptance, total model seconds,
  and a per-case breakdown.

  Model seconds describe your machine; print them, don't commit them to a public repo.

.EXAMPLE
  ./bench-summary.ps1 -LabelPrefix bench3
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $LabelPrefix,
    [string] $CasesDir = (Join-Path $PSScriptRoot '../cases')
)

$ErrorActionPreference = 'Stop'
$records = foreach ($case in Get-ChildItem $CasesDir -Directory) {
    $log = Join-Path $case.FullName 'attempts.jsonl'
    if (-not (Test-Path $log)) { continue }
    foreach ($line in Get-Content $log) {
        $r = $line | ConvertFrom-Json
        if ($r.label -and $r.label.StartsWith($LabelPrefix)) {
            $r | Add-Member -NotePropertyName case -NotePropertyValue $case.Name -PassThru
        }
    }
}
if (-not $records) { "No attempts with a label starting '$LabelPrefix'."; return }

# One run = one label + profile + case.
$runs = $records | Group-Object label, model_profile, case | ForEach-Object {
    $attempts = @($_.Group | Sort-Object attempt)
    $acceptedAt = ($attempts | Where-Object result -eq 'accepted' | Select-Object -First 1).attempt
    $bestScore = ($attempts | Where-Object score | ForEach-Object { [int]($_.score -split '/')[0] } | Measure-Object -Maximum).Maximum
    [pscustomobject]@{
        profile    = $attempts[0].model_profile
        case       = $attempts[0].case
        label      = $attempts[0].label
        accepted   = [bool]$acceptedAt
        acceptedAt = $acceptedAt
        attempts   = $attempts.Count
        bestScore  = $bestScore
        seconds    = [math]::Round(($attempts | Measure-Object model_seconds -Sum).Sum, 0)
    }
}

'=== By model profile ==='
$runs | Group-Object profile | ForEach-Object {
    $g = @($_.Group); $acc = @($g | Where-Object accepted)
    [pscustomobject]@{
        profile          = $_.Name
        runs             = $g.Count
        accepted         = "$($acc.Count)/$($g.Count)"
        avg_attempt_when_accepted = if ($acc) { [math]::Round(($acc | Measure-Object acceptedAt -Average).Average, 2) } else { '-' }
        total_attempts   = ($g | Measure-Object attempts -Sum).Sum
        model_minutes    = [math]::Round(($g | Measure-Object seconds -Sum).Sum / 60, 1)
    }
} | Format-Table -AutoSize | Out-String -Width 200

'=== By case (accepted runs / runs) ==='
$runs | Group-Object case | ForEach-Object {
    $row = [ordered]@{ case = $_.Name }
    foreach ($p in ($runs.profile | Sort-Object -Unique)) {
        $g = @($_.Group | Where-Object profile -eq $p)
        $row[$p] = if ($g) { "$(@($g | Where-Object accepted).Count)/$($g.Count)" } else { '-' }
    }
    [pscustomobject]$row
} | Format-Table -AutoSize | Out-String -Width 200
