# Test for run-gate.ps1: deterministic rows decide the exit code; the checklist follows the tier.
param([string] $Script = (Join-Path $PSScriptRoot 'run-gate.ps1'))
$ErrorActionPreference = 'Stop'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('gate-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $tmp | Out-Null
$fail = @(); $n = 0
function Run([string[]] $a) { $o = & pwsh -NoProfile -File $Script -RepoPath $tmp @a 2>&1; @{ Code = $LASTEXITCODE; Out = ($o | Out-String) } }
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }
try {
    & git -C $tmp init -q 2>&1 | Out-Null
    Set-Content (Join-Path $tmp 'a.md') 'plain' -Encoding utf8; Set-Content (Join-Path $tmp 'ok.json') '{"a":1}' -Encoding utf8
    & git -C $tmp -c core.safecrlf=false add a.md ok.json 2>&1 | Out-Null
    $r = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json')
    Check 'clean staged set passes' ($r.Code -eq 0 -and $r.Out -match 'deterministic rows passed') $r.Out
    $rows = ([regex]::Matches($r.Out, '\[ \]')).Count
    Check 'routine tier prints 2 checklist rows' ($rows -eq 2) "rows=$rows"
    $e = Run @('-Tier', 'elevated', '-Expected', 'a.md,ok.json'); $er = ([regex]::Matches($e.Out, '\[ \]')).Count
    Check 'elevated tier prints more rows than routine' ($er -gt $rows) "routine=$rows elevated=$er"
    $f = Run @('-Tier', 'full', '-Expected', 'a.md,ok.json'); $fr = ([regex]::Matches($f.Out, '\[ \]')).Count
    Check 'full tier prints more rows than elevated' ($fr -gt $er) "elevated=$er full=$fr"
    Check 'full tier requires the challenger and the no-secrets row' ($f.Out -match 'different model family' -and $f.Out -match 'No secret material')
    $x = Run @('-Tier', 'routine', '-Expected', 'a.md')
    Check 'an extra staged file fails the gate and still prints the checklist' ($x.Code -eq 1 -and $x.Out -match 'UNEXPECTED STAGED: ok.json' -and $x.Out -match 'GATE FAILED: check-staged' -and $x.Out -match '\[ \]')
    Set-Content (Join-Path $tmp 'bad.json') '{"a":1,}' -Encoding utf8; & git -C $tmp -c core.safecrlf=false add bad.json 2>&1 | Out-Null
    $b = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json,bad.json')
    Check 'a broken staged json fails the gate (the Test-Json case)' ($b.Code -eq 1 -and $b.Out -match 'FAIL bad.json' -and $b.Out -match 'GATE FAILED: check-changed') $b.Out
    $p = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json,bad.json')
    Set-Content (Join-Path $tmp 'a.md') ('see ' + 'C:' + '\Users\someone\x') -Encoding utf8; & git -C $tmp -c core.safecrlf=false add a.md 2>&1 | Out-Null
    $pv = Run @('-Tier', 'routine', '-Expected', 'a.md,ok.json,bad.json')
    Check 'a private path fails the gate' ($pv.Code -eq 1 -and $pv.Out -match 'PRIVACY: a.md' ) $pv.Out
} finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
