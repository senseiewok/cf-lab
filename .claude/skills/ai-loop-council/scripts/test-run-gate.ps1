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
} finally {
    Remove-Item -Recurse -Force $tmp, $tmp2, $msgDir -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
}
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
