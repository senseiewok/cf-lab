<#
.SYNOPSIS
  Run the deterministic rows of a review-tier gate before a commit, and print the rows that
  only a model or a human can do.

.DESCRIPTION
  Tiers are defined in AGENTS.md (routine, elevated, full). This script runs, in order:
    1. check-staged.ps1  - the staged set equals -Expected; no private detail is added;
                           every privacy pattern matches its canary.
    2. check-changed.ps1 - staged scripts and data parse; the owning checker passes.
  then prints the remaining rows for the tier as a checklist. It runs nothing that costs
  tokens, never commits, and never marks a model or human row as done: a person or agent
  ticks those from real output.

  Exit 0 only when every deterministic row passed. The checklist is printed either way.

.EXAMPLE
  pwsh -NoProfile -File run-gate.ps1 -Tier elevated -Expected README.md,tasks/board.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateSet('routine', 'elevated', 'full')] [string] $Tier,
    [Parameter(Mandatory)] [string[]] $Expected,
    [string] $RepoPath = '.'
)
$ErrorActionPreference = 'Stop'
$skills = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
$checkStaged = Join-Path $skills 'security-git/scripts/check-staged.ps1'
$checkChanged = Join-Path $PSScriptRoot 'check-changed.ps1'
foreach ($p in $checkStaged, $checkChanged) { if (-not (Test-Path -LiteralPath $p)) { Write-Host "error: missing $p"; exit 2 } }

$exp = @($Expected | ForEach-Object { $_ -split ',' } | Where-Object { $_ }) -join ','
$failed = @()
Write-Host "== gate: $Tier tier =="
Write-Host '-- 1. staged set and privacy'
& pwsh -NoProfile -File $checkStaged -RepoPath $RepoPath -Expected $exp
if ($LASTEXITCODE -ne 0) { $failed += 'check-staged' }
Write-Host '-- 2. staged files parse; owning checkers'
& pwsh -NoProfile -File $checkChanged -RepoPath $RepoPath
if ($LASTEXITCODE -ne 0) { $failed += 'check-changed' }

$rows = @(
    @{ T = 'routine'; Text = 'Local worker review of the diff (findings schema, 2 fast samples) when the diff is over about 20 lines; verify each finding against the file' },
    @{ T = 'elevated'; Text = 'Claim ledger: each factual claim has a type, a check and an evidence id; counts come from checker output, not typed' },
    @{ T = 'elevated'; Text = 'Re-read the complete sentences behind every "only / none / every / differs / absent" claim; search raw text for each year or file in scope' },
    @{ T = 'elevated'; Text = 'Local worker thinking pass over the claim ledger: which claims does the quoted evidence not support? (verify each finding)' },
    @{ T = 'elevated'; Text = 'Blind different-family review when the artifact is public-facing or a factual claim changed (proposal; see the loop design)' },
    @{ T = 'full'; Text = 'Blind challenger from a different model family reviewed the same packet before seeing any other findings; unavailable means blocked' },
    @{ T = 'full'; Text = 'No secret material, PHI or deployment specifics were sent to any model' },
    @{ T = 'any'; Text = 'A human reads the printed staged list and approves the commit (full tier: reads the diff)' }
)
$order = @{ routine = 1; elevated = 2; full = 3 }
Write-Host '-- 3. rows a model or a human must do (tick from real output, not from memory)'
foreach ($r in $rows) {
    if ($r.T -eq 'any' -or $order[$r.T] -le $order[$Tier]) { Write-Host ('  [ ] ' + $r.Text) }
}
if ($failed.Count -gt 0) { Write-Host "GATE FAILED: $($failed -join ', ')"; exit 1 }
Write-Host 'deterministic rows passed'
exit 0
