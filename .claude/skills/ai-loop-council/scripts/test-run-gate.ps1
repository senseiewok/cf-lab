# Test for run-gate.ps1: deterministic rows decide the exit code; the checklist follows the tier;
# a stray file fails; -MessageFile commits only on a pass; the last line counts the open rows.
param([string] $Script = (Join-Path $PSScriptRoot 'run-gate.ps1'))
$ErrorActionPreference = 'Stop'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('gate-test-' + [guid]::NewGuid().ToString('N'))
$tmp2 = Join-Path ([IO.Path]::GetTempPath()) ('gate-test2-' + [guid]::NewGuid().ToString('N'))
$msgDir = Join-Path ([IO.Path]::GetTempPath()) ('gate-msg-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $tmp, $tmp2, $msgDir | Out-Null
$fail = @(); $n = 0
function Run([string[]] $a, [string] $repo = $tmp) { $o = & pwsh -NoProfile -File $Script -RepoPath $repo @a 2>&1; @{ Code = $LASTEXITCODE; Out = ($o | Out-String); Last = (@($o | ForEach-Object { "$_" } | Where-Object { $_.Trim() }) | Select-Object -Last 1) } }
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }
function Commits([string] $repo) { $c = & git -C $repo rev-list --count HEAD 2>$null; if ($LASTEXITCODE -ne 0) { 0 } else { [int]$c } }
try {
    $env:GIT_AUTHOR_NAME = 't'; $env:GIT_AUTHOR_EMAIL = 't@example.invalid'; $env:GIT_COMMITTER_NAME = 't'; $env:GIT_COMMITTER_EMAIL = 't@example.invalid'
    & git -C $tmp init -q 2>&1 | Out-Null
    Set-Content (Join-Path $tmp 'a.md') 'plain' -Encoding utf8; Set-Content (Join-Path $tmp 'ok.json') '{"a":1}' -Encoding utf8
    & git -C $tmp -c core.safecrlf=false add a.md ok.json 2>&1 | Out-Null
    $r = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json')
    Check 'clean staged set passes' ($r.Code -eq 0 -and $r.Out -match 'deterministic rows passed') $r.Out
    $rows = ([regex]::Matches($r.Out, '\[ \]')).Count
    Check 'routine tier prints 2 checklist rows' ($rows -eq 2) "rows=$rows"
    Check 'the last line is OPEN ROWS with the unticked count' ($r.Last -eq "OPEN ROWS: $rows") "last=$($r.Last)"
    $e = Run @('-Tier', 'elevated', '-Expected', 'a.md,ok.json'); $er = ([regex]::Matches($e.Out, '\[ \]')).Count
    Check 'elevated tier prints more rows than routine' ($er -gt $rows) "routine=$rows elevated=$er"
    Check 'elevated OPEN ROWS matches its checklist' ($e.Last -eq "OPEN ROWS: $er") "last=$($e.Last)"
    $f = Run @('-Tier', 'full', '-Expected', 'a.md,ok.json'); $fr = ([regex]::Matches($f.Out, '\[ \]')).Count
    Check 'full tier prints more rows than elevated' ($fr -gt $er) "elevated=$er full=$fr"
    Check 'full tier requires the challenger and the no-secrets row' ($f.Out -match 'different model family' -and $f.Out -match 'No secret material')
    $x = Run @('-Tier', 'routine', '-Expected', 'a.md')
    Check 'an extra staged file fails the gate and still prints the checklist' ($x.Code -eq 1 -and $x.Out -match 'UNEXPECTED STAGED: ok.json' -and $x.Out -match 'GATE FAILED: check-staged' -and $x.Out -match '\[ \]')
    Check 'a failed gate still ends with OPEN ROWS' ($x.Last -eq "OPEN ROWS: $rows") "last=$($x.Last)"
    # a stray untracked file outside -Expected fails even though the staged set is right
    Set-Content (Join-Path $tmp 'stray.txt') 'left over' -Encoding utf8
    $s = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json')
    Check 'a stray untracked file fails the gate' ($s.Code -eq 1 -and $s.Out -match 'STRAY: stray.txt \(untracked' -and $s.Out -match 'GATE FAILED: stray-files' -and $s.Out -match 'staged set equals the expected set') $s.Out
    Remove-Item (Join-Path $tmp 'stray.txt')
    Set-Content (Join-Path $tmp 'bad.json') '{"a":1,}' -Encoding utf8; & git -C $tmp -c core.safecrlf=false add bad.json 2>&1 | Out-Null
    $b = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json,bad.json')
    Check 'a broken staged json fails the gate (the Test-Json case)' ($b.Code -eq 1 -and $b.Out -match 'FAIL bad.json' -and $b.Out -match 'GATE FAILED: check-changed') $b.Out
    Set-Content (Join-Path $tmp 'a.md') ('see ' + 'C:' + '\Users\someone\x') -Encoding utf8; & git -C $tmp -c core.safecrlf=false add a.md 2>&1 | Out-Null
    $pv = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json,bad.json')
    Check 'a private path fails the gate' ($pv.Code -eq 1 -and $pv.Out -match 'PRIVACY: a.md' ) $pv.Out

    # second repo: -Expected derived from the index, and -MessageFile
    & git -C $tmp2 init -q 2>&1 | Out-Null
    Set-Content (Join-Path $tmp2 'a.md') 'plain' -Encoding utf8; Set-Content (Join-Path $tmp2 'stray.txt') 'left over' -Encoding utf8
    & git -C $tmp2 -c core.safecrlf=false add a.md 2>&1 | Out-Null
    $derived = @(& git -C $tmp2 diff --cached --name-only) -join ','
    $d = Run @('-Tier', 'routine', '-Expected', $derived) $tmp2
    Check 'derived -Expected (from git diff --cached) with a stray file fails' ($derived -eq 'a.md' -and $d.Code -eq 1 -and $d.Out -match 'STRAY: stray.txt' -and $d.Out -match 'GATE FAILED: stray-files') $d.Out
    Remove-Item (Join-Path $tmp2 'stray.txt')
    $msg = Join-Path $msgDir 'msg.txt'; Set-Content $msg "gate test commit`n`nbody line" -Encoding utf8
    $c = Run @('-Tier', 'routine', '-Expected', 'a.md', '-MessageFile', $msg) $tmp2
    $subject = & git -C $tmp2 log -1 --format=%s 2>$null
    Check '-MessageFile commits on a pass' ($c.Code -eq 0 -and $c.Out -match 'COMMITTED' -and (Commits $tmp2) -eq 1 -and $subject -eq 'gate test commit' -and $c.Last -match '^OPEN ROWS: \d+$') $c.Out
    Set-Content (Join-Path $tmp2 'b.md') 'next' -Encoding utf8; & git -C $tmp2 -c core.safecrlf=false add b.md 2>&1 | Out-Null
    Set-Content (Join-Path $tmp2 'stray.txt') 'left over' -Encoding utf8
    $nc = Run @('-Tier', 'routine', '-Expected', 'b.md', '-MessageFile', $msg) $tmp2
    $stillStaged = @(& git -C $tmp2 diff --cached --name-only) -join ','
    Check '-MessageFile does not commit on a fail' ($nc.Code -eq 1 -and $nc.Out -match 'NOT COMMITTED' -and $nc.Out -notmatch '(?m)^COMMITTED' -and (Commits $tmp2) -eq 1 -and $stillStaged -eq 'b.md' -and $nc.Last -match '^OPEN ROWS: \d+$') $nc.Out
    Remove-Item (Join-Path $tmp2 'stray.txt')
    Set-Content (Join-Path $tmp2 'a.md') 'edited, not staged' -Encoding utf8
    $m = Run @('-Tier', 'routine', '-Expected', 'b.md', '-MessageFile', $msg) $tmp2
    Check 'a modified tracked file left unstaged is a stray and blocks the commit' ($m.Code -eq 1 -and $m.Out -match 'STRAY: a.md \(modified, not staged' -and (Commits $tmp2) -eq 1) $m.Out
    & git -C $tmp2 checkout -q -- a.md
    $u = Run @('-Tier', 'routine', '-Expected', 'b.md', '-MessageFile', (Join-Path $msgDir 'missing.txt')) $tmp2
    Check 'a missing message file is a usage error, no commit' ($u.Code -eq 2 -and (Commits $tmp2) -eq 1) $u.Out

    # -LocalReview with a FAKE review script (no model). It records its arguments and whether a dummy secret variable
    # reached it in a marker outside the repo, prints the given lines, runs any extra lines, and (unless told not to)
    # writes review.json into the -OutDir the gate chose, with the gate's run id and tree id (or wrong ones).
    function New-FakeReview([string] $name, [string[]] $lines, [int] $code, $json = $null, [switch] $WrongRunId, [switch] $WrongTree, [string[]] $extra = @()) {
        $f = Join-Path $msgDir "$name.ps1"; $marker = Join-Path $msgDir "$name.args"
        $body = @('param([string] $RepoPath, [switch] $Staged, [string] $OutDir, [string] $RunId, [string] $TreeId, [switch] $KeepOutDir, [switch] $ChallengerHandoff)',
            "Set-Content -LiteralPath '$marker' -Value (""RepoPath=`$RepoPath Staged=`$Staged OutDir=`$OutDir RunId=`$RunId TreeId=`$TreeId Keep=`$KeepOutDir Handoff=`$ChallengerHandoff Dummy=`$([bool]`$env:GATE_TEST_DUMMY_KEY) Worker=`$env:LOCAL_WORKER_MODEL"")")
        foreach ($l in $lines) { $body += "Write-Host '" + ($l -replace "'", "''") + "'" }
        if ($null -ne $json) {
            $id = if ($WrongRunId) { "'" + ('f' * 32) + "'" } else { '$RunId' }
            $tree = if ($WrongTree) { "'" + ('e' * 40) + "'" } else { '$TreeId' }
            $body += 'New-Item -ItemType Directory -Force -Path $OutDir | Out-Null'
            $jt = ($json | ConvertTo-Json -Depth 5 -Compress).Replace('__HI__', '\' + 'ud800').Replace('__LO__', '\' + 'udc00').Replace('__ANN__', '\' + 'ufff9')
            $body += "`$j = '" + ($jt -replace "'", "''") + "'"
            $body += "Set-Content -LiteralPath (Join-Path `$OutDir 'review.json') -Value ((`$j -replace '__RUNID__', $id) -replace '__TREEID__', $tree) -Encoding utf8"
        }
        $body += $extra
        $body += "exit $code"
        Set-Content -LiteralPath $f -Value $body -Encoding utf8
        @{ Script = $f; Marker = $marker }
    }
    function Result([string] $status, [int] $code, [int] $survivors, [int] $inDiff, [int] $reviewed, [string[]] $rank0 = @(), $handoff = $null, [hashtable] $more = @{}) {
        $notRev = @($rank0 | ForEach-Object { @{ path = $_; reason = 'packet cap'; rank = 0 } })
        while ($notRev.Count -lt ($inDiff - $reviewed)) { $notRev += @{ path = "doc$($notRev.Count).md"; reason = 'exclude pattern'; rank = 3 } }
        $h = @{ run_id = '__RUNID__'; tree_id = '__TREEID__'; status = $status; exit_code = $code; survivors_count = $survivors; files_in_diff = $inDiff
            files_reviewed = $reviewed; files_not_reviewed = $notRev; rank0_not_reviewed = $rank0; excluded_lock_files = @(); hidden_chars_total = 0
            boundary_lookalikes_total = 0; model_note_code = $null; masking = 'on'; challenger_handoff = $handoff }
        foreach ($k in $more.Keys) { $h[$k] = $more[$k] }
        return $h
    }
    function Stage([string[]] $names) { foreach ($nm in $names) { Set-Content (Join-Path $tmp2 $nm) $nm -Encoding utf8; & git -C $tmp2 -c core.safecrlf=false add $nm 2>&1 | Out-Null } }

    # four staged files: one review that is partial with survivors and a rank-0 file not reviewed, then a commit
    Stage @('deploy.sh', 'x1.md', 'x2.md')
    $four = 'b.md,deploy.sh,x1.md,x2.md'
    $two = New-FakeReview 'two' @('== local diff review (staged) ==', ('bell' + [char]7 + 'esc' + [char]27 + '[31m'), 'SURVIVORS: 2') 10 (Result 'partial' 10 2 4 3 @('deploy.sh'))
    $nr = Run @('-Tier', 'routine', '-Expected', $four, '-ReviewScript', $two.Script) $tmp2
    Check 'without -LocalReview the review script is not run' ($nr.Code -eq 0 -and -not (Test-Path $two.Marker) -and $nr.Out -notmatch 'local review') $nr.Out
    $env:GATE_TEST_DUMMY_KEY = 'dummy-not-a-secret'
    $lr = Run @('-Tier', 'routine', '-Expected', $four, '-LocalReview', '-ReviewScript', $two.Script, '-MessageFile', $msg) $tmp2
    Remove-Item Env:GATE_TEST_DUMMY_KEY
    $rowsLr = ([regex]::Matches($lr.Out, '\[ \]')).Count
    $mk = Get-Content -Raw $two.Marker
    $gateOut = if ($mk -match 'OutDir=(\S+)') { $Matches[1] } else { '' }
    Check '-LocalReview runs on the staged diff with its own run id, tree id and folder; survivors do not block the commit' ($lr.Code -eq 0 -and $mk -match 'Staged=True' -and $mk -match 'RunId=[0-9a-f]{32}' -and $mk -match 'TreeId=[0-9a-f]{40}' -and $mk -match 'Keep=True' -and $lr.Out -match '(?m)^COMMITTED' -and (Commits $tmp2) -eq 2) $lr.Out
    Check 'the row gives partial coverage with names, the rank-0 files NOT reviewed and the survivor count, and stays open' ($lr.Out -match '\[ \] Local worker review of the diff .* -- local review partial: reviewed 3 of 4 files, 1 not reviewed \(deploy\.sh\); NOT reviewed, risk rank 0: deploy\.sh; 2 survivor\(s\) for a person to read' -and $rowsLr -eq $rows -and $lr.Last -eq "OPEN ROWS: $rows") $lr.Out
    Check 'the gate deletes the review folder it chose' ($gateOut -and -not (Test-Path -LiteralPath $gateOut)) "folder=$gateOut"
    Check 'control characters printed by the review are shown as ?' ($lr.Out.Contains('bell?esc') -and -not $lr.Out.Contains([string][char]27) -and -not $lr.Out.Contains([string][char]7)) $lr.Out
    Check 'G9: the review script runs without the caller''s other environment variables' ($mk -match 'Dummy=False') $mk

    # from here one staged file, c.md
    Stage @('c.md')
    $err = New-FakeReview 'err' @('error: the model call failed') 2
    $le = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $err.Script, '-MessageFile', $msg) $tmp2
    Check 'a review script error fails closed: no commit' ($le.Code -eq 1 -and $le.Out -match 'GATE FAILED: local-review' -and $le.Out -match 'NOT COMMITTED' -and (Commits $tmp2) -eq 2) $le.Out
    function Fails([string] $name, $fake, [string] $tier = 'routine') {
        $o = Run @('-Tier', $tier, '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $fake.Script) $tmp2
        $script:LastFail = $o
        Check $name ($o.Code -eq 1 -and $o.Out -match 'GATE FAILED: local-review') $o.Out
    }
    Fails 'a "SURVIVORS: 0" line with exit 1 and no review.json fails closed (stdout is never parsed)' (New-FakeReview 'spoof' @('SURVIVORS: 0') 1)
    Fails 'a review.json with another run id fails closed' (New-FakeReview 'stale' @() 0 (Result 'reviewed' 0 0 1 1) -WrongRunId)
    Fails 'exit 0 with survivors in review.json fails closed' (New-FakeReview 'incons' @() 0 (Result 'reviewed' 0 2 1 1))
    # G1: exit 3 needs its own review.json
    Fails 'G1: exit 3 without review.json fails closed' (New-FakeReview 'nw' @('no local worker configured: nothing reviewed') 3)
    $nwOk = New-FakeReview 'nwok' @('no local worker configured: nothing reviewed') 3 @{ run_id = '__RUNID__'; tree_id = '__TREEID__'; status = 'no_worker'; exit_code = 3; model_note_code = $null }
    $lw = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $nwOk.Script) $tmp2
    Check 'G1: exit 3 with a valid no_worker review.json is printed on the row and does not block' ($lw.Code -eq 0 -and $lw.Out -match '-- local review not run: no local worker configured') $lw.Out
    Fails 'G1: a no_worker review.json with exit 0 fails closed' (New-FakeReview 'nwbad' @() 0 @{ run_id = '__RUNID__'; tree_id = '__TREEID__'; status = 'no_worker'; exit_code = 0; model_note_code = $null })
    # G2: the review must not change what gets committed, and must name the same tree
    Fails 'G2: a review.json that names another tree fails closed' (New-FakeReview 'tree' @() 0 (Result 'reviewed' 0 0 1 1) -WrongTree)
    Fails 'G2: a review script that stages a file fails closed' (New-FakeReview 'stages' @() 0 (Result 'reviewed' 0 0 1 1) -extra @('Set-Content -LiteralPath (Join-Path $RepoPath ''sneak.md'') ''x''', '& git -C $RepoPath add sneak.md 2>&1 | Out-Null'))
    Check 'G2: the change is named' ($script:LastFail.Out -match 'the review changed what would be committed: staged tree') $script:LastFail.Out
    & git -C $tmp2 rm -q --cached sneak.md 2>&1 | Out-Null; Remove-Item (Join-Path $tmp2 'sneak.md')
    Fails 'G2: a review script that writes a stray file fails closed' (New-FakeReview 'strayer' @() 0 (Result 'reviewed' 0 0 1 1) -extra @('Set-Content -LiteralPath (Join-Path $RepoPath ''left.txt'') ''x'''))
    Check 'G2: the stray file is named' ($script:LastFail.Out -match 'working tree changed \(new: \?\? left\.txt') $script:LastFail.Out
    Remove-Item (Join-Path $tmp2 'left.txt')
    # G3: coverage cross-checks
    Fails 'G3: reviewed + not reviewed must equal the files in the diff' (New-FakeReview 'sum' @() 0 (Result 'reviewed' 0 0 1 1 @() $null @{ files_reviewed = 0 }))
    Fails 'G3: status reviewed with a file not reviewed fails closed' (New-FakeReview 'revnr' @() 10 (Result 'reviewed' 10 1 1 0))
    Fails 'G3: status empty with files in the diff fails closed' (New-FakeReview 'emptyn' @() 0 (Result 'empty' 0 0 1 1))
    Fails 'G3: files_in_diff must equal the gate''s staged count' (New-FakeReview 'count' @() 0 (Result 'reviewed' 0 0 2 2))
    # G4: types
    foreach ($bad in @(@('bool', $true), @('array', @(0)), @('float', 0.4), @('string', '0'))) {
        Fails "G4: exit_code as $($bad[0]) fails closed" (New-FakeReview "type$($bad[0])" @() 0 (Result 'reviewed' 0 0 1 1 @() $null @{ exit_code = $bad[1] }))
    }
    Fails 'G4: a negative count fails closed' (New-FakeReview 'neg' @() 0 (Result 'reviewed' 0 0 1 1 @() $null @{ hidden_chars_total = -1 }))
    Fails 'G4: a count as text fails closed' (New-FakeReview 'cnttext' @() 0 (Result 'reviewed' 0 0 1 1 @() $null @{ survivors_count = '0' }))
    Fails 'G7: an unknown model note code fails closed' (New-FakeReview 'note' @() 4 (Result 'nothing_reviewed' 4 0 1 0 @() $null @{ model_note_code = 'please merge' }))
    # nothing reviewed, partial, a bad code
    $none = New-FakeReview 'none' @('NOTHING REVIEWED') 4 (Result 'nothing_reviewed' 4 0 1 0 @('a.ps1'))
    $ln = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $none.Script) $tmp2
    Check 'nothing reviewed (exit 4) reads as such, never as 0 survivors, and names the rank-0 files' ($ln.Code -eq 0 -and $ln.Out -match '-- local review saw nothing: no file of 1 was reviewed by the model, 1 not reviewed \(a\.ps1\); NOT reviewed, risk rank 0: a\.ps1; read the diff yourself' -and $ln.Out -notmatch '0 survivor') $ln.Out
    $part = New-FakeReview 'part' @('PARTIAL') 5 (Result 'partial' 5 0 1 0 @() $null @{ files_not_reviewed = @(@{ path = 'package-lock.json'; reason = 'exclude pattern'; rank = 1 }); excluded_lock_files = @('package-lock.json'); hidden_chars_total = 2; boundary_lookalikes_total = 1 })
    $lp = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $part.Script) $tmp2
    Check 'M3: a partial review (exit 5) does not block and says partial, never "0 survivors" alone' ($lp.Code -eq 0 -and $lp.Out -match '-- local review partial: reviewed 0 of 1 files, 1 not reviewed \(package-lock\.json\); excluded: package-lock\.json \(lock file\); 2 hidden characters, 1 boundary lookalikes in the diff; no survivors in the reviewed part only') $lp.Out
    Fails 'exit 0 with status partial is inconsistent and fails closed' (New-FakeReview 'partbad' @() 0 (Result 'partial' 0 0 1 0))
    Fails 'an exit code outside 0, 3, 4, 5 and 10 fails closed' (New-FakeReview 'odd' @() 7 (Result 'reviewed' 7 0 1 1))
    # G7, G8: long and hostile names are capped and made terminal-safe
    $long = 'n' + ([string][char]27) + '[2J' + ('x' * 10000) + '.md'
    $odd2 = 'a__HI__b__ANN__c__LO__d.md'  # replaced by JSON escapes for a lone high surrogate, U+FFF9 and a lone low surrogate
    $names = @($long, $odd2) + @(1..12 | ForEach-Object { "f$_.md" })
    $hostile = New-FakeReview 'hostile' @() 5 (Result 'partial' 5 0 1 0 @() $null @{ files_in_diff = 1; files_reviewed = 0; files_not_reviewed = @(@{ path = $long; reason = 'x'; rank = 0 }); rank0_not_reviewed = $names })
    $lh = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $hostile.Script) $tmp2
    $row = @($lh.Out -split "`r?`n" | Where-Object { $_ -match '\[ \] Local worker review' })[0]
    Check 'G7: a 10,000-character name is cut to 120 characters, control characters shown as ?, lists capped at 10' ($lh.Code -eq 0 -and $row -match 'n\?\[2Jx{110,113}\.\.\.' -and $row -notmatch 'x{200}' -and $row -match 'and 4 more' -and -not $row.Contains([string][char]27)) $row
    Check 'G8: lone surrogates and interlinear annotation characters are shown as ?' ($row.Contains('a?b?c?d.md')) $row
    # L7, masking unavailable
    $unus = New-FakeReview 'unus' @('NOTHING REVIEWED') 4 (Result 'nothing_reviewed' 4 0 1 0 @() $null @{ model_note_code = 'model_call_failed'; masking = 'unavailable' })
    $lu = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $unus.Script, '-MessageFile', $msg) $tmp2
    Check 'L7: an unusable model reply does not block the commit and is loud on the row (fixed sentence from the code)' ($lu.Code -eq 0 -and $lu.Out -match 'model reply unusable: the model call failed' -and $lu.Out -match 'masking unavailable' -and $lu.Out -match '(?m)^COMMITTED') $lu.Out
    Stage @('d.md')
    $full = New-FakeReview 'full' @() 0 (Result 'reviewed' 0 0 1 1 @() @{ status = 'needs-review'; sha256 = ('AB' * 32) })
    $lf = Run @('-Tier', 'full', '-Expected', 'd.md', '-LocalReview', '-ReviewScript', $full.Script) $tmp2
    Check 'full tier asks for the challenger handoff and keeps the challenger row open' ($lf.Code -eq 0 -and (Get-Content -Raw $full.Marker) -match 'Handoff=True' -and $lf.Out -match 'different model family.*handoff packet sha256 ABABABABABAB\.\.\. made, not sent.*open until a challenger''s answer is recorded' -and $lf.Last -eq "OPEN ROWS: $fr") $lf.Out
    $bad = Run @('-Tier', 'routine', '-Expected', 'd.md', '-LocalReview', '-ReviewScript', '-x.ps1') $tmp2
    Check 'a -ReviewScript value that starts with - is a usage error' ($bad.Code -eq 2) $bad.Out
    $off = Run @('-Tier', 'routine', '-Expected', 'd.md', '-ReviewScript', '-x.ps1') $tmp2
    Check 'L8: without -LocalReview a -ReviewScript value starting with - changes nothing' ($off.Code -eq 0) $off.Out
    # G5: positional values are not bound
    $pos = & pwsh -NoProfile -File $Script 'routine' 'd.md' 2>&1 | Out-String
    Check 'G5: the gate takes no positional arguments' ($LASTEXITCODE -ne 0 -and $pos -notmatch 'deterministic rows passed') $pos
    # G10: a temp folder inside the repository is refused before any write
    $inner = Join-Path $tmp2 'tmp-inside'; New-Item -ItemType Directory $inner | Out-Null
    $savedTemp = @{ TEMP = $env:TEMP; TMP = $env:TMP; TMPDIR = $env:TMPDIR }
    $env:TEMP = $inner; $env:TMP = $inner; $env:TMPDIR = $inner
    try { $ti = Run @('-Tier', 'routine', '-Expected', 'd.md', '-LocalReview', '-ReviewScript', $full.Script) $tmp2 }
    finally { foreach ($k in $savedTemp.Keys) { if ($savedTemp[$k]) { Set-Item "Env:$k" $savedTemp[$k] } else { Remove-Item "Env:$k" -ErrorAction SilentlyContinue } } }
    Check 'G10: a temp folder inside the repository is refused (exit 2) before any write' ($ti.Code -eq 2 -and $ti.Out -match 'temp folder .* is inside the repository' -and @(Get-ChildItem -Force $inner -Filter 'gate-review-*').Count -eq 0) $ti.Out
    Remove-Item -Recurse -Force $inner
    # G6: a review folder that cannot be deleted is named on the row (Windows: a file held open by another process)
    if ($IsWindows) {
        $pidFile = Join-Path $msgDir 'locker.pid'
        $lockLines = @("`$lock = Join-Path `$OutDir 'held.bin'", "Set-Content -LiteralPath `$lock 'x'",
            "`$p = Start-Process -PassThru -WindowStyle Hidden -FilePath (Get-Process -Id `$PID).Path -ArgumentList @('-NoProfile', '-Command', ""Set-Variable -Name h -Value ([IO.File]::Open('`$lock', 'Open', 'ReadWrite', 'None')); Start-Sleep -Seconds 40"")",
            "Set-Content -LiteralPath '$pidFile' `$p.Id", 'Start-Sleep -Seconds 3')
        $locker = New-FakeReview 'locker' @() 0 (Result 'reviewed' 0 0 1 1) -extra $lockLines
        $lk = Run @('-Tier', 'routine', '-Expected', 'd.md', '-LocalReview', '-ReviewScript', $locker.Script) $tmp2
        if (Test-Path $pidFile) { Stop-Process -Id ([int](Get-Content $pidFile)) -Force -ErrorAction SilentlyContinue; Start-Sleep -Milliseconds 500 }
        Check 'G6: a review folder that could not be deleted is named on the review row' ($lk.Out -match '\[ \] Local worker review .*WARNING: the review folder \(it holds diff text\) could not be deleted') $lk.Out
        Get-ChildItem ([IO.Path]::GetTempPath()) -Directory -Filter 'gate-review-*' | Where-Object { Test-Path (Join-Path $_.FullName 'held.bin') } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
    # the real review-diff.ps1 with no local worker: its review.json (no_worker, run id, tree id) satisfies the gate
    $savedWorker = @{ m = $env:LOCAL_WORKER_MODEL; p = $env:LOCAL_WORKER_PROFILE }
    Remove-Item Env:LOCAL_WORKER_MODEL, Env:LOCAL_WORKER_PROFILE -ErrorAction SilentlyContinue
    try { $real = Run @('-Tier', 'routine', '-Expected', 'd.md', '-LocalReview') $tmp2 }
    finally { if ($savedWorker.m) { $env:LOCAL_WORKER_MODEL = $savedWorker.m }; if ($savedWorker.p) { $env:LOCAL_WORKER_PROFILE = $savedWorker.p } }
    Check 'G1/G2: the real review script without a local worker passes the gate''s checks and says so on the row' ($real.Code -eq 0 -and $real.Out -match '-- local review not run: no local worker configured' -and $real.Out -notmatch 'GATE FAILED') $real.Out
    # G8 at the source: the replacement set of both scripts, taken from their syntax trees (JSON and pipes turn a lone
    # surrogate into U+FFFD before it can reach the regex, so this is the only place a lone one can be tested)
    foreach ($src in (Join-Path $PSScriptRoot 'run-gate.ps1'), (Join-Path $PSScriptRoot 'review-diff.ps1')) {
        $tk = $null; $er = $null
        $ast = [Management.Automation.Language.Parser]::ParseFile($src, [ref]$tk, [ref]$er)
        $assign = $ast.Find({ param($x) $x -is [Management.Automation.Language.AssignmentStatementAst] -and $x.Left.Extent.Text -eq '$script:Unprintable' }, $true)
        $re = & ([scriptblock]::Create($assign.Right.Extent.Text))
        $sample = 'a' + [char]0xD800 + 'b' + [char]0xFFF9 + 'c' + [char]0xDC00 + 'd' + [char]0xFFFD + 'e' + [char]0xD83D + [char]0xDE00 + 'f'
        $got = $re.Replace($sample, '?')
        Check "G8: $(Split-Path -Leaf $src) shows lone surrogates, U+FFF9 and U+FFFD as ? and keeps a valid pair" ($got -ceq ('a?b?c?d?e' + [char]0xD83D + [char]0xDE00 + 'f')) $got
    }
    Set-Content (Join-Path $tmp2 'stray.txt') 'left over' -Encoding utf8
    $skip = New-FakeReview 'skip' @() 0 (Result 'reviewed' 0 0 1 1)
    $ls = Run @('-Tier', 'routine', '-Expected', 'd.md', '-LocalReview', '-ReviewScript', $skip.Script) $tmp2
    Check 'the review is not run when a deterministic row failed' ($ls.Code -eq 1 -and -not (Test-Path $skip.Marker) -and $ls.Out -match 'not run: a deterministic row failed') $ls.Out
    Remove-Item (Join-Path $tmp2 'stray.txt')
} finally {
    Remove-Item -Recurse -Force $tmp, $tmp2, $msgDir -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
}
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
