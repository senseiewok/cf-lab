<#
.SYNOPSIS
  Run the deterministic rows of a review-tier gate before a commit, print the rows that
  only a model or a human can do, and (with -MessageFile) commit only when the rows passed.

.DESCRIPTION
  Tiers are defined in AGENTS.md (routine, elevated, full). This script runs, in order:
    1. check-staged.ps1  - the staged set equals -Expected; no private detail is added;
                           every privacy pattern matches its canary.
       working tree      - `git status --porcelain` shows no file outside -Expected:
                           a modified tracked file or an untracked file, staged or not, is a
                           STRAY and fails the gate, so a file the plan did not name is seen.
    2. check-changed.ps1 - staged scripts and data parse; the owning checker passes.
  then prints the remaining rows for the tier as a checklist. It runs nothing that costs
  tokens and never marks a model or human row as done: a person or agent ticks those from
  real output. The last line is always `OPEN ROWS: n`, the number of unticked rows in
  section 3, so a filtered or tailed output still shows that rows remain.

  -Expected comes from the plan, never from `git diff --cached`. A list read back from the
  index after `git add -A` always equals the staged set, so the staged-set row can never
  fail. Name the files the plan said you would change, before staging.

  -MessageFile <path>: when given, the gate runs `git commit -F <path>` only if every
  deterministic row passed; otherwise it refuses (exit 1, no commit). The commit's own exit
  code is returned as is. Without -MessageFile the gate never commits.

  No opt-out for the stray check: agents work in their own worktree (AGENTS.md), where an
  unexpected file is a finding; ignored files (.gitignore) are not listed by git status.

  Exit 0 only when every deterministic row passed (and the commit, if asked, succeeded).
  1 when a row failed or the commit was refused, 2 for a usage error, otherwise the exit
  code of `git commit`. The checklist is printed either way.

.EXAMPLE
  pwsh -NoProfile -File run-gate.ps1 -Tier elevated -Expected README.md,tasks/board.json
  pwsh -NoProfile -File run-gate.ps1 -Tier elevated -Expected README.md -MessageFile ../msg.txt
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateSet('routine', 'elevated', 'full')] [string] $Tier,
    [Parameter(Mandatory)] [string[]] $Expected,
    [string] $RepoPath = '.',
    [string] $MessageFile
)
$ErrorActionPreference = 'Stop'
$skills = Split-Path -Parent $PSScriptRoot | Split-Path -Parent
$checkStaged = Join-Path $skills 'security-git/scripts/check-staged.ps1'
$checkChanged = Join-Path $PSScriptRoot 'check-changed.ps1'
foreach ($p in $checkStaged, $checkChanged) { if (-not (Test-Path -LiteralPath $p)) { Write-Host "error: missing $p"; exit 2 } }
if ($MessageFile) {
    if (-not (Test-Path -LiteralPath $MessageFile -PathType Leaf)) { Write-Host "error: message file not found: $MessageFile"; exit 2 }
    $MessageFile = (Resolve-Path -LiteralPath $MessageFile).Path
}
$repo = (& git -C $RepoPath rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repo) { Write-Host "error: not a git repository: $RepoPath"; exit 2 }

$expList = @($Expected | ForEach-Object { $_ -split ',' } | Where-Object { $_ } | ForEach-Object { ($_ -replace '\\', '/') -replace '^\./', '' })
$exp = $expList -join ','
$failed = @()
Write-Host "== gate: $Tier tier =="
Write-Host '-- 1. staged set, working tree and privacy'
& pwsh -NoProfile -File $checkStaged -RepoPath $RepoPath -Expected $exp
if ($LASTEXITCODE -ne 0) { $failed += 'check-staged' }
# Every changed or untracked path (staged or not) must be one the plan named.
$raw = & git -C $repo -c core.safecrlf=false status --porcelain=v1 -z --untracked-files=all --no-renames 2>$null
if ($LASTEXITCODE -ne 0) { Write-Host 'error: git status failed'; $failed += 'stray-files' }
else {
    $stray = 0
    foreach ($e in (($raw -join '') -split "`0" | Where-Object { $_.Length -gt 3 })) {
        $xy = $e.Substring(0, 2); $path = $e.Substring(3) -replace '\\', '/'
        if ($path -in $expList) { continue }
        $kind = if ($xy -eq '??') { 'untracked' } elseif ($xy[0] -ne ' ' -and $xy[1] -eq ' ') { 'staged' } else { 'modified, not staged' }
        Write-Host "STRAY: $path ($kind; not in -Expected)"; $stray++
    }
    if ($stray -gt 0) { $failed += 'stray-files' } else { Write-Host 'working tree: no changed or untracked file outside -Expected' }
}
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
$open = 0
Write-Host '-- 3. rows a model or a human must do (tick from real output, not from memory)'
foreach ($r in $rows) {
    if ($r.T -eq 'any' -or $order[$r.T] -le $order[$Tier]) { Write-Host ('  [ ] ' + $r.Text); $open++ }
}
$code = 0
if ($failed.Count -gt 0) {
    Write-Host "GATE FAILED: $($failed -join ', ')"
    if ($MessageFile) { Write-Host 'NOT COMMITTED: the gate failed' }
    $code = 1
} else {
    Write-Host 'deterministic rows passed'
    if ($MessageFile) {
        & git -C $repo commit -F $MessageFile
        $code = $LASTEXITCODE
        if ($code -eq 0) { Write-Host 'COMMITTED' } else { Write-Host "COMMIT FAILED: git commit exited $code" }
    }
}
Write-Host "OPEN ROWS: $open"
exit $code
