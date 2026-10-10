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

    # -LocalReview with a FAKE review script (no model). It records the arguments it got in a marker outside the repo,
    # prints the given lines, and (unless told not to) writes review.json into the -OutDir the gate chose, with the
    # gate's run id (or a wrong one), then exits with the given code.
    function New-FakeReview([string] $name, [string[]] $lines, [int] $code, $json = $null, [switch] $WrongRunId) {
        $f = Join-Path $msgDir "$name.ps1"; $marker = Join-Path $msgDir "$name.args"
        $body = @('param([string] $RepoPath, [switch] $Staged, [string] $OutDir, [string] $RunId, [switch] $KeepOutDir, [switch] $ChallengerHandoff)',
            "Set-Content -LiteralPath '$marker' -Value (""RepoPath=`$RepoPath Staged=`$Staged OutDir=`$OutDir RunId=`$RunId Keep=`$KeepOutDir Handoff=`$ChallengerHandoff"")")
        foreach ($l in $lines) { $body += "Write-Host '" + ($l -replace "'", "''") + "'" }
        if ($null -ne $json) {
            $id = if ($WrongRunId) { "'" + ('f' * 32) + "'" } else { '$RunId' }
            $body += 'New-Item -ItemType Directory -Force -Path $OutDir | Out-Null'
            $body += "`$j = '" + (($json | ConvertTo-Json -Depth 5 -Compress) -replace "'", "''") + "'"
            $body += "Set-Content -LiteralPath (Join-Path `$OutDir 'review.json') -Value (`$j -replace '__RUNID__', $id) -Encoding utf8"
        }
        $body += "exit $code"
        Set-Content -LiteralPath $f -Value $body -Encoding utf8
        @{ Script = $f; Marker = $marker }
    }
    function Result([string] $status, [int] $code, [int] $survivors, [int] $inDiff, [int] $reviewed, [string[]] $rank0 = @(), $handoff = $null, [hashtable] $more = @{}) {
        $notRev = @($rank0 | ForEach-Object { @{ path = $_; reason = 'packet cap'; rank = 0 } })
        while ($notRev.Count -lt ($inDiff - $reviewed)) { $notRev += @{ path = "doc$($notRev.Count).md"; reason = 'exclude pattern'; rank = 3 } }
        @{ run_id = '__RUNID__'; status = $status; exit_code = $code; survivors_count = $survivors; files_in_diff = $inDiff; files_reviewed = $reviewed
            files_not_reviewed = $notRev; rank0_not_reviewed = $rank0; challenger_handoff = $handoff; masking = 'on' } | ForEach-Object {
            foreach ($k in $more.Keys) { $_[$k] = $more[$k] }
            $_
        }
    }
    $two = New-FakeReview 'two' @('== local diff review (staged) ==', ('bell' + [char]7 + 'esc' + [char]27 + '[31m'), 'SURVIVORS: 2') 10 (Result 'partial' 10 2 4 3 @('deploy.sh'))
    $nr = Run @('-Tier', 'routine', '-Expected', 'b.md', '-ReviewScript', $two.Script) $tmp2
    Check 'without -LocalReview the review script is not run' ($nr.Code -eq 0 -and -not (Test-Path $two.Marker) -and $nr.Out -notmatch 'local review') $nr.Out
    $lr = Run @('-Tier', 'routine', '-Expected', 'b.md', '-LocalReview', '-ReviewScript', $two.Script, '-MessageFile', $msg) $tmp2
    $rowsLr = ([regex]::Matches($lr.Out, '\[ \]')).Count
    $mk = Get-Content -Raw $two.Marker
    $gateOut = if ($mk -match 'OutDir=(\S+)') { $Matches[1] } else { '' }
    Check '-LocalReview runs on the staged diff with its own run id and folder; survivors do not block the commit' ($lr.Code -eq 0 -and $mk -match 'Staged=True' -and $mk -match 'RunId=[0-9a-f]{32}' -and $mk -match 'Keep=True' -and $lr.Out -match '(?m)^COMMITTED' -and (Commits $tmp2) -eq 2) $lr.Out
    Check 'the row gives coverage, the rank-0 files NOT reviewed and the survivor count, and stays open' ($lr.Out -match '\[ \] Local worker review of the diff .* -- local review partial: reviewed 3 of 4 files, 1 not reviewed \(deploy\.sh\); NOT reviewed, risk rank 0: deploy\.sh; 2 survivor\(s\) for a person to read' -and $rowsLr -eq $rows -and $lr.Last -eq "OPEN ROWS: $rows") $lr.Out
    Check 'the gate deletes the review folder it chose' ($gateOut -and -not (Test-Path -LiteralPath $gateOut)) "folder=$gateOut"
    # (the child pwsh may already strip a colour sequence when its output is redirected; the BEL must arrive as ?)
    Check 'control characters printed by the review are shown as ?' ($lr.Out.Contains('bell?esc') -and -not $lr.Out.Contains([string][char]27) -and -not $lr.Out.Contains([string][char]7)) $lr.Out
    Set-Content (Join-Path $tmp2 'c.md') 'c' -Encoding utf8; & git -C $tmp2 -c core.safecrlf=false add c.md 2>&1 | Out-Null
    $err = New-FakeReview 'err' @('error: the model call failed') 2
    $le = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $err.Script, '-MessageFile', $msg) $tmp2
    Check 'a review script error fails closed: no commit' ($le.Code -eq 1 -and $le.Out -match 'GATE FAILED: local-review' -and $le.Out -match 'NOT COMMITTED' -and (Commits $tmp2) -eq 2) $le.Out
    $spoof = New-FakeReview 'spoof' @('SURVIVORS: 0') 1
    $sp = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $spoof.Script) $tmp2
    Check 'a "SURVIVORS: 0" line with exit 1 and no review.json fails closed (stdout is never parsed)' ($sp.Code -eq 1 -and $sp.Out -match 'GATE FAILED: local-review') $sp.Out
    $stale = New-FakeReview 'stale' @() 0 (Result 'reviewed' 0 0 1 1) -WrongRunId
    $st = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $stale.Script) $tmp2
    Check 'a review.json with another run id fails closed' ($st.Code -eq 1 -and $st.Out -match 'GATE FAILED: local-review') $st.Out
    $incons = New-FakeReview 'incons' @() 0 (Result 'reviewed' 0 2 1 1)
    $ic = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $incons.Script) $tmp2
    Check 'exit 0 with survivors in review.json fails closed' ($ic.Code -eq 1 -and $ic.Out -match 'GATE FAILED: local-review') $ic.Out
    $nw = New-FakeReview 'nw' @('no local worker configured: nothing reviewed') 3
    $lw = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $nw.Script) $tmp2
    Check 'no local worker (exit 3) is printed on the row and does not block' ($lw.Code -eq 0 -and $lw.Out -match '-- local review not run: no local worker configured') $lw.Out
    $none = New-FakeReview 'none' @('NOTHING REVIEWED') 4 (Result 'nothing_reviewed' 4 0 2 0 @('a.ps1'))
    $ln = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $none.Script) $tmp2
    Check 'nothing reviewed (exit 4) reads as such, never as 0 survivors, and names the rank-0 files' ($ln.Code -eq 0 -and $ln.Out -match '-- local review saw nothing: reviewed 0 of 2 files, 2 not reviewed \(a\.ps1, doc1\.md\); NOT reviewed, risk rank 0: a\.ps1; read the diff yourself' -and $ln.Out -notmatch '0 survivor') $ln.Out
    $full = New-FakeReview 'full' @() 0 (Result 'reviewed' 0 0 1 1 @() @{ status = 'needs-review'; sha256 = ('AB' * 32) })
    $lf = Run @('-Tier', 'full', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $full.Script) $tmp2
    Check 'full tier asks for the challenger handoff and keeps the challenger row open' ($lf.Code -eq 0 -and (Get-Content -Raw $full.Marker) -match 'Handoff=True' -and $lf.Out -match 'different model family.*handoff packet sha256 ABABABABABAB\.\.\. made, not sent.*open until a challenger''s answer is recorded' -and $lf.Last -eq "OPEN ROWS: $fr") $lf.Out
    $bad = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', '-x.ps1') $tmp2
    Check 'a -ReviewScript value that starts with - is a usage error' ($bad.Code -eq 2) $bad.Out
    # second challenger review: partial (5), the row's lock files, hidden characters, model note, masking, bad codes
    $part = New-FakeReview 'part' @('PARTIAL') 5 (Result 'partial' 5 0 3 2 @() $null @{ files_not_reviewed = @(@{ path = 'package-lock.json'; reason = 'exclude pattern'; rank = 1 }); excluded_lock_files = @('package-lock.json'); hidden_chars_total = 2; boundary_lookalikes_total = 1 })
    $lp = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $part.Script) $tmp2
    Check 'M3: a partial review (exit 5) does not block and says partial, never "0 survivors" alone' ($lp.Code -eq 0 -and $lp.Out -match '-- local review partial: reviewed 2 of 3 files, 1 not reviewed \(package-lock\.json\); excluded: package-lock\.json \(lock file\); 2 hidden characters, 1 boundary lookalikes in the diff; no survivors in the reviewed part only') $lp.Out
    $partBad = New-FakeReview 'partbad' @() 0 (Result 'partial' 0 0 3 2)
    $pb = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $partBad.Script) $tmp2
    Check 'exit 0 with status partial is inconsistent and fails closed' ($pb.Code -eq 1 -and $pb.Out -match 'GATE FAILED: local-review') $pb.Out
    $odd = New-FakeReview 'odd' @() 7 (Result 'reviewed' 7 0 1 1)
    $od = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $odd.Script) $tmp2
    Check 'an exit code outside 0, 3, 4, 5 and 10 fails closed' ($od.Code -eq 1 -and $od.Out -match 'GATE FAILED: local-review') $od.Out
    $unus = New-FakeReview 'unus' @('NOTHING REVIEWED') 4 (Result 'nothing_reviewed' 4 0 1 0 @() $null @{ model_note = 'model reply unusable: the model call failed (exit 1)'; masking = 'unavailable' })
    $lu = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $unus.Script, '-MessageFile', $msg) $tmp2
    Check 'L7: an unusable model reply does not block the commit and is loud on the row' ($lu.Code -eq 0 -and $lu.Out -match 'model reply unusable: the model call failed' -and $lu.Out -match 'masking unavailable' -and $lu.Out -match '(?m)^COMMITTED') $lu.Out
    Set-Content (Join-Path $tmp2 'd.md') 'd' -Encoding utf8; & git -C $tmp2 -c core.safecrlf=false add d.md 2>&1 | Out-Null
    $off = Run @('-Tier', 'routine', '-Expected', 'd.md', '-ReviewScript', '-x.ps1') $tmp2
    Check 'L8: without -LocalReview a -ReviewScript value starting with - changes nothing' ($off.Code -eq 0) $off.Out
    Set-Content (Join-Path $tmp2 'stray.txt') 'left over' -Encoding utf8
    $skip = New-FakeReview 'skip' @() 0 (Result 'reviewed' 0 0 1 1)
    $ls = Run @('-Tier', 'routine', '-Expected', 'c.md', '-LocalReview', '-ReviewScript', $skip.Script) $tmp2
    Check 'the review is not run when a deterministic row failed' ($ls.Code -eq 1 -and -not (Test-Path $skip.Marker) -and $ls.Out -match 'not run: a deterministic row failed') $ls.Out
    Remove-Item (Join-Path $tmp2 'stray.txt')
} finally {
    Remove-Item -Recurse -Force $tmp, $tmp2, $msgDir -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
}
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
