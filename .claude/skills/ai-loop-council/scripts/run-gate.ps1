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

  -LocalReview (opt-in, default off): after the deterministic rows pass and before any commit, run review-diff.ps1 on
  the staged diff (the local worker, two fast samples, findings checked for exact quotes) and print its count on the
  "Local worker review of the diff" row: "reviewed X of Y files" (or "partial: ..., Z not reviewed (names)"), the
  risk-rank-0 files NOT reviewed, the lock files excluded, the hidden-character and boundary-lookalike counts, and the
  survivor count. The result is read from review.json in a fresh temp folder the gate chose and tagged with the gate's
  own run id (never from the console text); the folder is deleted afterwards and a failed delete is reported. Valid
  review exit codes are 0 (reviewed or empty), 5 (partial), 10 (survivors), 4 (nothing reviewed, including an unusable
  model reply) and 3 (no local worker); each must agree with review.json. None of these blocks the commit: the row
  stays open and says what was and was not reviewed. Any other exit code (2 for a script error; 1 when PowerShell
  could not even bind the parameters), or a missing, stale or inconsistent review.json, fails the gate closed (no
  commit, exit 1). On the full tier it also asks for a blind challenger handoff packet (made, never sent); the
  challenger row stays open until a challenger's answer is recorded. -ReviewScript replaces review-diff.ps1 (tests pass
  a fake one). The privacy scan of section 1 runs before the review, and the review only runs when every deterministic
  row passed. Without -LocalReview the gate behaves exactly as before.
  Before the review the gate records the staged tree (git write-tree), the working-tree status and the staged file
  list, and passes the tree id to the review; afterwards any change, or a review.json naming another tree, fails the
  gate (the review must not change what gets committed). review.json is type-checked (integers are integers, status is
  a known word) and cross-checked: reviewed + not reviewed = files in the diff = the gate's staged count; exit 3 needs a
  review.json with status no_worker. Every name from review.json is cut to 120 characters, lists to 10 names, and made
  terminal-safe; the model note is a fixed code mapped to a fixed sentence. The review runs in a child process with a
  minimal environment (PATH, temp, profile and system folders, OLLAMA_* and LOCAL_WORKER_*; no API keys) and a 3600 s
  timeout. A temp folder inside the repository is refused (exit 2) before any write. A review folder that could not be
  deleted is named on the row. Parameters are name-only (Positional binding is off).

  No opt-out for the stray check: agents work in their own worktree (AGENTS.md), where an
  unexpected file is a finding; ignored files (.gitignore) are not listed by git status.

  Exit 0 only when every deterministic row passed (and the commit, if asked, succeeded).
  1 when a row failed or the commit was refused, 2 for a usage error, otherwise the exit
  code of `git commit`. The checklist is printed either way.

.EXAMPLE
  pwsh -NoProfile -File run-gate.ps1 -Tier elevated -Expected README.md,tasks/board.json
  pwsh -NoProfile -File run-gate.ps1 -Tier elevated -Expected README.md -MessageFile ../msg.txt
#>
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory)] [ValidateSet('routine', 'elevated', 'full')] [string] $Tier,
    [Parameter(Mandatory)] [string[]] $Expected,
    [string] $RepoPath = '.',
    [string] $MessageFile,
    [switch] $LocalReview,
    [string] $ReviewScript = (Join-Path $PSScriptRoot 'review-diff.ps1')
)
$ErrorActionPreference = 'Stop'
# Text from the review is shown on a terminal: C0 and C1 controls, DEL, line separators, bidi, zero-width, variation
# selectors, tag characters and other default-ignorable characters become '?'.
$script:Unprintable = [regex]::new('[\x00-\x1F\x7F-\x9F\u00ad\u034f\u061c\u115f\u1160\u17b4\u17b5\u180b-\u180f\u200b-\u200f\u2028-\u202e\u2060-\u206f\u3164\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufffd]|[' + [char]0xD82F + [char]0xD834 + '][' + [char]0xDC00 + '-' + [char]0xDFFF + ']|[' + [char]0xDB40 + '-' + [char]0xDB43 + '][' + [char]0xDC00 + '-' + [char]0xDFFF + ']|[' + [char]0xD800 + '-' + [char]0xDBFF + '](?![' + [char]0xDC00 + '-' + [char]0xDFFF + '])|(?<![' + [char]0xD800 + '-' + [char]0xDBFF + '])[' + [char]0xDC00 + '-' + [char]0xDFFF + ']')
# review-diff.ps1 writes a note code, never free text, for the row; the gate maps it to a fixed sentence.
$script:NoteText = @{ model_call_failed = 'model reply unusable: the model call failed'; model_call_timeout = 'model reply unusable: the model call timed out'
    no_usable_sample = 'model reply unusable: no sample gave a usable reply'; some_samples_unusable = 'a model sample was unusable' }
function Get-Printable([object] $Value) { return $script:Unprintable.Replace([string]$Value, '?') }
# One value from review.json for the row: at most 120 characters, then made terminal-safe.
function Get-Short([object] $Value) {
    $t = [string]$Value
    if ($t.Length -gt 120) { $t = $t.Substring(0, 117) + '...' }
    return Get-Printable $t
}
# A list of names for the row: each one shortened, at most 10, then "and N more".
function Format-Names($List) {
    $n = @(@($List) | Where-Object { $null -ne $_ } | ForEach-Object { Get-Short $_ })
    if ($n.Count -gt 10) { return ($n[0..9] -join ', ') + ", and $($n.Count - 10) more" }
    return ($n -join ', ')
}
function Test-Inside([string] $Child, [string] $Parent) {
    $sep = [IO.Path]::DirectorySeparatorChar
    return ($Child.TrimEnd('\', '/') + $sep).StartsWith($Parent.TrimEnd('\', '/') + $sep, [StringComparison]::OrdinalIgnoreCase)
}
# The real path: every existing component that is a link (symbolic link or junction) is replaced by its final target.
function Resolve-RealPath([string] $Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $root = [IO.Path]::GetPathRoot($full)
    $cur = $root
    foreach ($part in $full.Substring($root.Length).Split([char[]]@('\', '/'), [StringSplitOptions]::RemoveEmptyEntries)) {
        $cur = [IO.Path]::Combine($cur, $part)
        if ([IO.Directory]::Exists($cur)) {
            $target = ([IO.DirectoryInfo]::new($cur)).ResolveLinkTarget($true)
            if ($null -ne $target) { $cur = [IO.Path]::GetFullPath($target.FullName) }
        }
    }
    return $cur
}
# What the commit would contain and what the working tree shows, to compare before and after the review.
function Get-RepoSnapshot([string] $Repo) {
    $t = & git -C $Repo -c core.fsmonitor=false write-tree 2>$null
    $tc = $LASTEXITCODE
    $s = (& git -C $Repo -c core.fsmonitor=false -c core.safecrlf=false status --porcelain=v1 -z --untracked-files=all --no-renames 2>$null) -join ''
    $sc = $LASTEXITCODE
    $d = (& git -C $Repo -c core.fsmonitor=false diff --cached --name-only -z -M --no-ext-diff 2>$null) -join ''
    $dc = $LASTEXITCODE
    return [pscustomobject]@{ Ok = ($tc -eq 0 -and $sc -eq 0 -and $dc -eq 0); Tree = ([string]$t).Trim()
        Status = @($s -split "`0" | Where-Object { $_ }); Staged = @($d -split "`0" | Where-Object { $_ }) }
}
# Run the review script with a minimal environment (no API keys or other variables a wrapper may have loaded) and a
# timeout. Kept: what pwsh, git, Python and Ollama need, and the local-worker settings.
function Invoke-Child([string[]] $Arguments, [int] $TimeoutSec) {
    $psi = [Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
    foreach ($a in $Arguments) { $psi.ArgumentList.Add($a) }
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.RedirectStandardInput = $true
    $psi.StandardOutputEncoding = [Text.UTF8Encoding]::new($false); $psi.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $keep = @('PATH', 'PATHEXT', 'TEMP', 'TMP', 'TMPDIR', 'SystemRoot', 'SystemDrive', 'windir', 'ComSpec', 'USERPROFILE', 'HOME',
        'HOMEDRIVE', 'HOMEPATH', 'LOCALAPPDATA', 'APPDATA', 'ProgramData', 'ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432',
        'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE', 'OS', 'LANG', 'LC_ALL', 'LOCAL_WORKER_MODEL', 'LOCAL_WORKER_PROFILE', 'LOCAL_WORKER_TAG')
    $envNow = [Environment]::GetEnvironmentVariables()
    $pass = @{}
    foreach ($k in $envNow.Keys) { if ($k -in $keep -or $k -like 'OLLAMA_*') { $pass[$k] = $envNow[$k] } }
    $psi.Environment.Clear()
    foreach ($k in $pass.Keys) { $psi.Environment[$k] = $pass[$k] }
    $p = [Diagnostics.Process]::Start($psi)
    $p.StandardInput.Close()
    $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
    $done = $p.WaitForExit($TimeoutSec * 1000)
    if (-not $done) { try { $p.Kill($true) } catch { $null = $_ }; $null = $p.WaitForExit(10000) } else { $p.WaitForExit() }
    $out = ''; $err = ''
    try { $out = $o.GetAwaiter().GetResult(); $err = $e.GetAwaiter().GetResult() } catch { $null = $_ }
    return [pscustomobject]@{ Code = $(if ($done) { $p.ExitCode } else { $null }); TimedOut = -not $done; Out = $out; Err = $err }
}
function Test-Count($Value) { return ($Value -is [long] -or $Value -is [int]) -and $Value -ge 0 }
function Test-StringList($Value) { return $null -eq $Value -or (@($Value | Where-Object { $_ -isnot [string] }).Count -eq 0) }
# Checks review.json against the gate's own facts. Returns '' when it is consistent, otherwise what is wrong.
function Test-ReviewResult($Rj, [string] $RunId, [string] $Tree, [int] $Code, [int] $StagedCount) {
    if ($Rj -isnot [pscustomobject]) { return 'review.json is missing, not JSON or not an object' }
    if ($Rj.run_id -isnot [string] -or $RunId -cne $Rj.run_id) { return 'review.json is not from this run (run id)' }
    if (-not ($Rj.exit_code -is [long] -or $Rj.exit_code -is [int])) { return 'exit_code in review.json is not an integer' }
    if ($Code -ne $Rj.exit_code) { return "the exit code ($Code) and review.json ($([long]$Rj.exit_code)) disagree" }
    if ($Rj.status -isnot [string] -or $Rj.status -cnotin @('empty', 'reviewed', 'partial', 'nothing_reviewed', 'no_worker')) { return 'status in review.json is not a known value' }
    if ($Rj.tree_id -isnot [string] -or $Tree -cne $Rj.tree_id) { return 'review.json names another staged tree than the one the gate recorded' }
    if ($null -ne $Rj.model_note_code -and ($Rj.model_note_code -isnot [string] -or $Rj.model_note_code -cnotin $script:NoteText.Keys)) { return 'model_note_code in review.json is not a known code' }
    if ('no_worker' -ceq $Rj.status) { if (3 -ne $Code) { return 'status no_worker needs exit 3' }; return '' }
    foreach ($f in 'files_in_diff', 'files_reviewed', 'survivors_count', 'hidden_chars_total', 'boundary_lookalikes_total') {
        if (-not (Test-Count $Rj.$f)) { return "$f in review.json is not a whole number of 0 or more" }
    }
    if ($null -ne $Rj.files_not_reviewed -and @($Rj.files_not_reviewed | Where-Object { $_ -isnot [pscustomobject] -or $_.path -isnot [string] }).Count) { return 'files_not_reviewed in review.json is malformed' }
    foreach ($f in 'rank0_not_reviewed', 'excluded_lock_files') { if (-not (Test-StringList $Rj.$f)) { return "$f in review.json is not a list of names" } }
    if ($Rj.masking -isnot [string] -or $Rj.masking -cnotin @('on', 'unavailable')) { return 'masking in review.json is not a known value' }
    $nr = @($Rj.files_not_reviewed | Where-Object { $null -ne $_ }).Count
    if ([long]$Rj.files_in_diff -ne [long]$Rj.files_reviewed + $nr) { return "coverage does not add up: $([long]$Rj.files_reviewed) reviewed + $nr not reviewed is not $([long]$Rj.files_in_diff) files" }
    if ($StagedCount -ne [long]$Rj.files_in_diff) { return "review.json counts $([long]$Rj.files_in_diff) files in the diff, the gate counts $StagedCount staged files" }
    $s = [string]$Rj.status
    $ok = switch ($Code) {
        0 { ('empty' -ceq $s -and 0 -eq $Rj.files_in_diff) -or ('reviewed' -ceq $s -and 0 -eq $Rj.survivors_count -and 0 -eq $nr) }
        5 { 'partial' -ceq $s -and 0 -eq $Rj.survivors_count }
        10 { (('reviewed' -ceq $s -and 0 -eq $nr) -or 'partial' -ceq $s) -and 0 -lt $Rj.survivors_count }
        4 { 'nothing_reviewed' -ceq $s }
        default { $false }
    }
    if ('reviewed' -ceq $s -and 0 -ne $nr) { return 'status reviewed with files not reviewed' }
    if (-not $ok) { return "exit $Code does not match status '$s' and its counts" }
    return ''
}
if ($LocalReview) {
    # Values handed on to the review script must not be read as options; checked only when the review runs.
    foreach ($pair in @(@('RepoPath', $RepoPath), @('MessageFile', $MessageFile), @('ReviewScript', $ReviewScript))) {
        if ($pair[1] -and $pair[1].StartsWith('-')) { Write-Host "error: -$($pair[0]) must not start with '-'"; exit 2 }
    }
}
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
if ($LocalReview) {
    # Review files hold diff text: refuse before any write when the temp folder is inside the repository.
    $tempReal = Resolve-RealPath ([IO.Path]::GetTempPath())
    if (Test-Inside $tempReal (Resolve-RealPath $repo)) { Write-Host "error: the temp folder ($(Get-Printable $tempReal)) is inside the repository: refusing to write review files there"; exit 2 }
}

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

$reviewNote = ''; $challengerNote = ''
if ($LocalReview) {
    Write-Host '-- 2b. local worker review of the staged diff (review-diff.ps1; never blocks on findings)'
    if ($failed.Count -gt 0) { $reviewNote = ' -- local review not run: a deterministic row failed'; Write-Host 'not run: a deterministic row failed' }
    elseif (-not (Test-Path -LiteralPath $ReviewScript -PathType Leaf)) { Write-Host "error: missing $ReviewScript"; $failed += 'local-review' }
    else {
        # The result is read from review.json in a fresh folder the gate chose, tagged with the gate's own run id and the
        # staged tree it recorded; the console output is shown, never parsed. The folder is always deleted.
        $gid = [guid]::NewGuid().ToString('N')
        $gOut = Join-Path ([IO.Path]::GetTempPath()) ('gate-review-' + $gid)
        $before = Get-RepoSnapshot $repo
        $deleteNote = ''
        try {
            if (-not $before.Ok -or $before.Tree -cnotmatch '^([0-9a-f]{40}|[0-9a-f]{64})$') { throw 'git could not record the staged tree before the review' }
            $rvArgs = @('-NoProfile', '-File', $ReviewScript, "-RepoPath:$repo", '-Staged', "-OutDir:$gOut", "-RunId:$gid", "-TreeId:$($before.Tree)", '-KeepOutDir')
            if ($Tier -eq 'full') { $rvArgs += '-ChallengerHandoff' }
            $child = Invoke-Child $rvArgs 3600
            @(($child.Out + $child.Err) -split "`r?`n" | Where-Object { $_ }) | ForEach-Object { Write-Host ('  ' + (Get-Printable $_)) }
            $after = Get-RepoSnapshot $repo
            $changed = @()
            if (-not $after.Ok) { $changed += 'git could not record the repository after the review' }
            if ($before.Tree -cne $after.Tree) { $changed += "staged tree $($before.Tree) became $(Get-Short $after.Tree)" }
            $gone = @($before.Status | Where-Object { $_ -cnotin $after.Status }); $new = @($after.Status | Where-Object { $_ -cnotin $before.Status })
            if ($gone.Count -or $new.Count) { $changed += "working tree changed (new: $(Format-Names $new); gone: $(Format-Names $gone))" }
            if (($before.Staged -join "`0") -cne ($after.Staged -join "`0")) { $changed += 'the staged file list changed' }
            if ($child.TimedOut) { Write-Host 'error: the review script did not finish within 3600 s'; $failed += 'local-review' }
            elseif ($changed.Count) { Write-Host ('error: the review changed what would be committed: ' + ($changed -join '; ')); $failed += 'local-review' }
            else {
                $rvCode = [int]$child.Code
                $rj = $null
                $rf = Join-Path $gOut 'review.json'
                if (Test-Path -LiteralPath $rf -PathType Leaf) { try { $rj = Get-Content -Raw -LiteralPath $rf | ConvertFrom-Json } catch { $rj = $null } }
                # Only 0, 3, 4, 5 and 10 are results; each must agree with review.json and with the gate's own facts.
                $why = Test-ReviewResult $rj $gid $before.Tree $rvCode $before.Staged.Count
                if ($why) { Write-Host "error: the review script failed or left no valid result for this run (exit $rvCode): $why"; $failed += 'local-review' }
                elseif ('no_worker' -ceq $rj.status) { $reviewNote = ' -- local review not run: no local worker configured' }
                else {
                    $inDiff = [int]$rj.files_in_diff; $done = [int]$rj.files_reviewed; $count = [int]$rj.survivors_count
                    $notList = @($rj.files_not_reviewed | Where-Object { $null -ne $_ } | ForEach-Object { $_.path })
                    $notText = if ($notList.Count) { ", $($notList.Count) not reviewed ($(Format-Names $notList))" } else { '' }
                    $extra = ''
                    $r0 = @($rj.rank0_not_reviewed | Where-Object { $null -ne $_ })
                    if ($r0.Count) { $extra += '; NOT reviewed, risk rank 0: ' + (Format-Names $r0) }
                    $locks = @($rj.excluded_lock_files | Where-Object { $null -ne $_ })
                    if ($locks.Count) { $extra += '; excluded: ' + (Format-Names $locks) + ' (lock file' + $(if ($locks.Count -gt 1) { 's' } else { '' }) + ')' }
                    $hid = [int]$rj.hidden_chars_total; $look = [int]$rj.boundary_lookalikes_total
                    if ($hid -gt 0 -or $look -gt 0) { $extra += "; $hid hidden characters, $look boundary lookalikes in the diff" }
                    if ($rj.model_note_code) { $extra += '; ' + $script:NoteText[[string]$rj.model_note_code] }
                    if ('on' -cne $rj.masking) { $extra += '; masking unavailable' }
                    $reviewNote = switch ([string]$rj.status) {
                        'empty' { ' -- local review: the staged diff is empty' }
                        'nothing_reviewed' { " -- local review saw nothing: no file of $inDiff was reviewed by the model$notText$extra; read the diff yourself" }
                        'partial' { " -- local review partial: reviewed $done of $inDiff files$notText$extra; $(if ($count) { "$count survivor(s) for a person to read (output above)" } else { 'no survivors in the reviewed part only' })" }
                        default { " -- local review: reviewed $done of $inDiff files$notText$extra; $count survivor(s) for a person to read (output above)" }
                    }
                    if ($Tier -eq 'full') {
                        $h = $rj.challenger_handoff
                        $sha = if ($h -and $h.sha256 -is [string]) { Get-Short $h.sha256 } else { '' }
                        if ($sha.Length -gt 12) { $sha = $sha.Substring(0, 12) }
                        $challengerNote = if ($h -and 'needs-review' -ceq $h.status) {
                            " -- handoff packet sha256 $sha... made, not sent (rerun review-diff.ps1 -Staged -ChallengerHandoff -KeepOutDir to keep it); open until a challenger's answer is recorded"
                        } else { ' -- no handoff packet was made; open until a challenger''s answer is recorded' }
                    }
                }
            }
        } catch {
            Write-Host ('error: ' + (Get-Printable $_.Exception.Message)); $failed += 'local-review'
        } finally {
            Remove-Item -LiteralPath $gOut -Recurse -Force -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $gOut) {
                Write-Host "warning: could not delete the review folder: $gOut"
                $deleteNote = " -- WARNING: the review folder (it holds diff text) could not be deleted: $gOut; delete it by hand"
            }
        }
        $reviewNote += $deleteNote
    }
}

$rows = @(
    @{ T = 'routine'; Text = 'Local worker review of the diff (findings schema, 2 fast samples) when the diff is over about 20 lines; verify each finding against the file' + $reviewNote },
    @{ T = 'elevated'; Text = 'Claim ledger: each factual claim has a type, a check and an evidence id; counts come from checker output, not typed' },
    @{ T = 'elevated'; Text = 'Re-read the complete sentences behind every "only / none / every / differs / absent" claim; search raw text for each year or file in scope' },
    @{ T = 'elevated'; Text = 'Local worker thinking pass over the claim ledger: which claims does the quoted evidence not support? (verify each finding)' },
    @{ T = 'elevated'; Text = 'Blind different-family review when the artifact is public-facing or a factual claim changed (proposal; see the loop design)' },
    @{ T = 'full'; Text = 'Blind challenger from a different model family reviewed the same packet before seeing any other findings; unavailable means blocked' + $challengerNote },
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
