# Test for the V2-02 verifier freeze in delegate.ps1 and verifier-freeze.ps1, with a stub standing in for the local worker. No model, Ollama or network.
param([string] $Script = (Join-Path $PSScriptRoot 'delegate.ps1'))
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'verifier-freeze.ps1')
$base = Join-Path ([IO.Path]::GetTempPath()) ('freeze-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $base | Out-Null
$fail = @(); $n = 0
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }

# The stub worker: reply-<i>.txt from $env:STUB_DIR; before it answers, mutate-<i>.ps1 (if there is one) runs, to change files while a run is in flight.
Set-Content (Join-Path $base 'stub.ps1') @'
param([string] $PromptFile, [string] $ProfileFile, [string] $Model, [string] $SystemFile, [int] $NumCtx, [int] $MaxOutputTokens, [string] $ThinkMode, [string] $ThinkingFile, [string] $LogFile, [string] $Tag, [int] $Attempt, [string] $Mode)
$d = $env:STUB_DIR
$cf = Join-Path $d 'count.txt'; $i = 1 + $(if (Test-Path $cf) { [int](Get-Content $cf) } else { 0 }); Set-Content $cf $i
if ($ThinkingFile) { Set-Content $ThinkingFile "stub thinking $i" }
if ($LogFile) { Add-Content $LogFile ('{"prompt_tokens":77,"output_tokens":123,"prompt_eval_duration":150000000,"eval_duration":900000000,"thinking_chars":45,"done_reason":"stop","attempt":' + $Attempt + ',"mode":"' + $Mode + '"}') }
$m = Join-Path $d "mutate-$i.ps1"; if (Test-Path $m) { & $m }
$r = Join-Path $d "reply-$i.txt"
if (Test-Path $r) { Get-Content -Raw $r } else { 'no scripted reply' }
'@ -Encoding utf8
Set-Content (Join-Path $base 'task.md') 'write a thing' -Encoding utf8

$stdVerifier = @'
param([string] $Script)
$expect = (Get-Content -Raw (Join-Path $PSScriptRoot 'fixtures\expect.txt')).Trim()
$t = Get-Content -Raw $Script
if ($t -match [regex]::Escape($expect)) { Write-Output '1/1 passed'; exit 0 }
Write-Output "FAIL candidate does not say $expect"; Write-Output '0/1 passed'; exit 1
'@
$fence = '```'
function NewCase([string[]] $replies) {
    $d = Join-Path $base ('case-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $d | Out-Null
    for ($i = 0; $i -lt $replies.Count; $i++) { Set-Content (Join-Path $d "reply-$($i + 1).txt") $replies[$i] -Encoding utf8 }
    return $d
}
# A verifier folder of its own: verify.ps1 and fixtures\expect.txt. Returns the folder.
function NewVd([string] $text = $stdVerifier) {
    $v = Join-Path $base ('vd-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory (Join-Path $v 'fixtures') -Force | Out-Null
    Set-Content (Join-Path $v 'verify.ps1') $text -Encoding utf8
    Set-Content (Join-Path $v 'fixtures\expect.txt') 'GOOD' -Encoding utf8
    return $v
}
function Run([string] $d, [string] $verifier, [string[]] $extra = @(), [string] $outName = 'out.ps1', [string] $work = 'work') {
    $env:STUB_DIR = $d
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task.md') -Verify $verifier -OutFile (Join-Path $d $outName) -InvokeScript (Join-Path $base 'stub.ps1') -WorkDir (Join-Path $d $work) -OutcomeLog (Join-Path $d 'outcomes.jsonl') -UsageLog (Join-Path $d 'central.jsonl') @extra 2>&1 | Out-String
    return @{ Code = $LASTEXITCODE; Out = $o; Dir = $d }
}
function Rows([string] $d) { $f = Join-Path $d 'outcomes.jsonl'; if (Test-Path $f) { return @(Get-Content $f | ForEach-Object { $_ | ConvertFrom-Json }) } else { return @() } }
function RunRow([string] $d) { return @(Rows $d | Where-Object { $_.kind -eq 'run' } | Select-Object -Last 1)[0] }
function Calls([string] $d) { $f = Join-Path $d 'count.txt'; if (Test-Path $f) { return [int](Get-Content $f) } else { return 0 } }
function SetMutation([string] $d, [int] $i, [string] $code) { Set-Content (Join-Path $d "mutate-$i.ps1") $code -Encoding utf8 }

try {
    # 1. a fixture the verifier reads is edited while the worker is answering: blocked, exit 3, no accepted row, the output file put back
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'ORIGINAL' -Encoding utf8
    SetMutation $c 1 'Add-Content (Join-Path $env:VD ''fixtures\expect.txt'') ''X'''
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1'); $row = RunRow $c; $att = @(Rows $c | Where-Object { $_.kind -eq 'attempt' })
    Check 'a fixture edited mid-run: exit 3 and BLOCKED, naming the file' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED \(verifier-changed\)' -and $r.Out -match 'fixtures/expect\.txt') $r.Out
    Check 'a blocked run has state blocked, a reason, no accepted row, and a BLOCKED attempt label' ($row.state -eq 'blocked' -and $row.reason -eq 'verifier-changed' -and @(Rows $c | Where-Object { $_.state -eq 'accepted' }).Count -eq 0 -and $att.Count -eq 1 -and $att[0].label -ceq 'BLOCKED') ((Rows $c | ConvertTo-Json -Compress -Depth 4))
    Check 'a blocked run puts the output file back as it was' ((Get-Content -Raw (Join-Path $c 'out.ps1')).Trim() -ceq 'ORIGINAL') (Get-Content -Raw (Join-Path $c 'out.ps1'))

    # 2. a file named with -VerifierFiles is edited mid-run
    $vd = NewVd; $extra = Join-Path $base ('extra-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $extra | Out-Null
    Set-Content (Join-Path $extra 'more.txt') 'data' -Encoding utf8
    $c = NewCase @("$fence`nGOOD`n$fence")
    SetMutation $c 1 'Add-Content (Join-Path $env:EX ''more.txt'') ''changed'''
    $env:EX = $extra
    $r = Run $c (Join-Path $vd 'verify.ps1') @('-VerifierFiles', (Join-Path $extra 'more.txt'))
    Check 'a -VerifierFiles file edited mid-run blocks the run' ($r.Code -eq 3 -and $r.Out -match 'more\.txt' -and -not (Test-Path (Join-Path $c 'out.ps1'))) $r.Out

    # 3. a new file appears in the verifier's folder mid-run
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    SetMutation $c 1 'Set-Content (Join-Path $env:VD ''sneaky.txt'') ''x'''
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a file added to the verifier folder mid-run blocks the run and is named as added' ($r.Code -eq 3 -and $r.Out -match 'added: sneaky\.txt') $r.Out

    # 4. a line-ending-only change still blocks (raw bytes decide), and is called what it is
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    SetMutation $c 1 '[IO.File]::WriteAllText((Join-Path $env:VD ''fixtures\expect.txt''), "GOOD`r`n")'
    [IO.File]::WriteAllText((Join-Path $vd 'fixtures\expect.txt'), "GOOD`n")
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a line-ending-only change blocks and says so' ($r.Code -eq 3 -and $r.Out -match 'line endings only') $r.Out

    # 5. the verifier itself is edited while the worker answers
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    SetMutation $c 1 'Add-Content (Join-Path $env:VD ''verify.ps1'') ''# edited'''
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'an edit to the verifier file itself blocks the run' ($r.Code -eq 3 -and $r.Out -match 'changed: verify\.ps1') $r.Out

    # 6. a verifier that edits a live fixture while it runs is caught after its run
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if ($t -match 'GOOD') { Add-Content (Join-Path $env:VD 'fixtures\expect.txt') 'Z'; Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    # it edits the live file only for a candidate that says GOOD, so the empty-stub pre-flight is untouched and only the check after the run can see it
    $c = NewCase @("$fence`nGOOD`n$fence")
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that edits a live fixture during its run is blocked (checked after the run too)' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED') $r.Out

    # 6b. a changed verifier is never run: with the fixture edited during the first call, the only verifier run is the pre-flight on the empty stub
    $vd = NewVd @'
param([string] $Script)
Add-Content (Join-Path $env:STUB_DIR 'verifier-runs.txt') 'ran'
$expect = (Get-Content -Raw (Join-Path $PSScriptRoot 'fixtures\expect.txt')).Trim()
if ((Get-Content -Raw $Script) -match [regex]::Escape($expect)) { Write-Output '1/1 passed'; exit 0 }
Write-Output "FAIL not $expect"; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence")
    SetMutation $c 1 'Add-Content (Join-Path $env:VD ''fixtures\expect.txt'') ''X'''
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier changed before its run is blocked without being run: one run only, the pre-flight' ($r.Code -eq 3 -and @(Get-Content (Join-Path $c 'verifier-runs.txt')).Count -eq 1) ($r.Out + (Get-Content (Join-Path $c 'verifier-runs.txt') -ErrorAction SilentlyContinue))

    # 6c. a verifier that edits one of its own files in the copy is caught: the next check sees the copy differ from the frozen hashes
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if ($t -match 'GOOD') { Add-Content (Join-Path $PSScriptRoot 'fixtures\expect.txt') 'tampered'; Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that edits its own file in the copy is blocked (the copy is checked too)' ($r.Code -eq 3 -and $r.Out -match 'the copy was changed: fixtures/expect\.txt') $r.Out

    # 6d. a verifier that edits a live fixture and then FAILS the candidate is blocked too: the check after the run is not only for accepted results
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if ($t) { Add-Content (Join-Path $env:VD 'fixtures\expect.txt') 'W' }
if ($t -match 'NEVER') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not NEVER'; exit 1
'@
    $c = NewCase @("$fence`nsomething else`n$fence")
    $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that edits a live fixture and then rejects the candidate is still blocked (the check after the run)' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED \(verifier-changed\)') $r.Out

    # 7. the candidate changing across attempts never blocks; the one that passes is accepted
    $vd = NewVd; $c = NewCase @("$fence`nnope one`n$fence", "$fence`nnope two`n$fence", "$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a candidate that changes on every attempt is not a verifier change: accepted on attempt 3' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED on attempt 3') $r.Out

    # 8. a verifier that edits the candidate after judging it: blocked before accepted
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if ($t -match 'GOOD') { Add-Content $Script '# changed after the verdict'; Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a candidate changed between the verifier run and acceptance blocks the run' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED \(candidate-changed\)') $r.Out

    # 9. a read outside the manifest is refused before the first call; naming the sibling lets the same verifier run
    $holder = Join-Path $base ('holder-' + [guid]::NewGuid().ToString('N').Substring(0, 6))
    $vdir = Join-Path $holder 'verifier'; $dataIn = Join-Path $holder 'data'
    New-Item -ItemType Directory $vdir, $dataIn | Out-Null
    Set-Content (Join-Path $dataIn 'expect.txt') 'GOOD' -Encoding utf8
    Set-Content (Join-Path $vdir 'verify.ps1') @'
param([string] $Script)
$expect = (Get-Content -Raw (Join-Path $PSScriptRoot '..\data\expect.txt')).Trim()
$t = Get-Content -Raw $Script
if ($t -match [regex]::Escape($expect)) { Write-Output '1/1 passed'; exit 0 }
Write-Output "FAIL candidate does not say $expect"; exit 1
'@ -Encoding utf8
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vdir 'verify.ps1')
    Check 'a verifier that reads a sibling folder it did not name is refused before the first call, naming the path' ($r.Code -eq 2 -and $r.Out -match 'REFUSED \(preflight-missing\)' -and $r.Out -match 'expect\.txt' -and (Calls $c) -eq 0) $r.Out
    Check 'a refusal is recorded as a blocked run row with a reason' ((RunRow $c).state -eq 'blocked' -and (RunRow $c).reason -eq 'preflight-missing') ((Rows $c) | ConvertTo-Json -Compress)
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vdir 'verify.ps1') @('-VerifierFiles', $dataIn)
    Check 'the same verifier with the sibling named in -VerifierFiles passes the pre-flight and accepts, in the same layout' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED' -and (Test-Path (Join-Path $c 'work\verifier-copy\verifier\verify.ps1')) -and (Test-Path (Join-Path $c 'work\verifier-copy\data\expect.txt'))) $r.Out

    # 9b. -VerifierFiles given as one comma-joined string (what pwsh -File delivers a list as) is split
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vdir 'verify.ps1') @('-VerifierFiles', "$dataIn,$dataIn")
    Check 'a comma-joined -VerifierFiles value is split into its paths' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out

    # 10. the limits, pinned: an absolute-path read and a loop over a missing folder are NOT refused
    $abs = Join-Path $base 'absolute.txt'; Set-Content $abs 'GOOD' -Encoding utf8
    $vd = NewVd @'
param([string] $Script)
$expect = (Get-Content -Raw $env:ABS_FILE).Trim()
$t = Get-Content -Raw $Script
if ($t -match [regex]::Escape($expect)) { Write-Output '1/1 passed'; exit 0 }
Write-Output "FAIL candidate does not say $expect"; exit 1
'@
    $env:ABS_FILE = $abs; $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'NEGATIVE (a stated limit): a verifier that reads an absolute path is not refused' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out
    $vd = NewVd @'
param([string] $Script)
if (-not (Get-Content -Raw $Script)) { Write-Output 'FAIL the candidate is empty'; exit 1 }
$bad = 0
foreach ($f in @(Get-ChildItem (Join-Path $PSScriptRoot 'missing-fixtures') -ErrorAction SilentlyContinue)) { $bad++ }
if ($bad) { Write-Output 'FAIL a fixture failed'; exit 1 }
Write-Output '0/0 fixtures'; exit 0
'@
    $c = NewCase @("$fence`nanything at all`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'NEGATIVE (a stated limit): a verifier that loops over a missing folder is not refused and passes with nothing checked' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out

    # 11. a verifier that writes a cache into its own folder does not block; a JSON verifier that tracebacks on an empty stub is not refused
    $vd = NewVd @'
param([string] $Script)
Set-Content (Join-Path $PSScriptRoot 'cache.tmp') 'x'
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot '__pycache__') | Out-Null
Set-Content (Join-Path $PSScriptRoot '__pycache__\v.pyc') 'x'
$t = Get-Content -Raw $Script
if ($t -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that writes caches into its own folder does not cause a block' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $vd = Join-Path $base ('vj-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $vd | Out-Null
        Set-Content (Join-Path $vd 'verify.py') "import json, sys`nd = json.load(open(sys.argv[1], encoding='utf-8'))`nsys.exit(0 if d.get('ok') is True else 1)`n" -Encoding utf8
        $c = NewCase @("$fence`n{`"ok`": true}`n$fence")
        $r = Run $c (Join-Path $vd 'verify.py') @() 'out.json'
        Check 'a JSON verifier that raises on an empty stub (JSONDecodeError) is not refused' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out
        $vd = Join-Path $base ('vm-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $vd | Out-Null
        Set-Content (Join-Path $vd 'verify.py') "import sys`nimport no_such_module_for_freeze_test`n" -Encoding utf8
        $c = NewCase @("$fence`n{}`n$fence")
        $r = Run $c (Join-Path $vd 'verify.py') @() 'out.json'
        Check 'a verifier that cannot import a module is refused before the first call, naming the module' ($r.Code -eq 2 -and $r.Out -match 'no_such_module_for_freeze_test' -and (Calls $c) -eq 0) $r.Out
    } else { Write-Output 'SKIP the python verifier tests (no python on PATH)' }

    # 12. a verifier that cannot fail is refused before the first call
    $vd = NewVd "param([string] `$Script)`nWrite-Output '1/1 passed'; exit 0`n"
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that passes an empty file is refused (exit 2) and no model call is made' ($r.Code -eq 2 -and $r.Out -match 'REFUSED \(preflight-cannot-fail\)' -and (Calls $c) -eq 0) $r.Out

    # 13. start-up refusals: the output file or the work folder inside the verifier's folder, a junction, the caps
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    $env:STUB_DIR = $c
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task.md') -Verify (Join-Path $vd 'verify.ps1') -OutFile (Join-Path $vd 'out.ps1') -InvokeScript (Join-Path $base 'stub.ps1') -WorkDir (Join-Path $c 'work') -OutcomeLog (Join-Path $c 'o.jsonl') -UsageLog (Join-Path $c 'u.jsonl') 2>&1 | Out-String
    Check 'an output file inside the verifier folder is refused at start (exit 2), with no model call' ($LASTEXITCODE -eq 2 -and $o -match 'output file is inside' -and (Calls $c) -eq 0) $o
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task.md') -Verify (Join-Path $vd 'verify.ps1') -OutFile (Join-Path $c 'out.ps1') -InvokeScript (Join-Path $base 'stub.ps1') -WorkDir (Join-Path $vd 'work') -OutcomeLog (Join-Path $c 'o.jsonl') -UsageLog (Join-Path $c 'u.jsonl') 2>&1 | Out-String
    Check 'a work folder inside the verifier folder is refused at start' ($LASTEXITCODE -eq 2 -and $o -match 'work folder is inside') $o
    $vd = NewVd; $tgt = Join-Path $base ('jt-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $tgt | Out-Null
    New-Item -ItemType Junction -Path (Join-Path $vd 'link') -Target $tgt | Out-Null
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a junction in the verifier folder is refused (exit 2), and the cleanup does not follow it' ($r.Code -eq 2 -and $r.Out -match 'symlink or junction' -and (Test-Path $tgt)) $r.Out
    $vd = NewVd; Set-Content (Join-Path $vd 'b.txt') 'b'; Set-Content (Join-Path $vd 'c.txt') 'c'
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1') @('-MaxManifestFiles', '2')
    Check 'a manifest over the file cap is refused and the message names the cap' ($r.Code -eq 2 -and $r.Out -match '-MaxManifestFiles' -and (Calls $c) -eq 0) $r.Out
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1') @('-MaxManifestBytes', '5')
    Check 'a manifest over the byte cap is refused and the message names the cap' ($r.Code -eq 2 -and $r.Out -match '-MaxManifestBytes') $r.Out
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1') @('-MaxManifestFiles', '4')
    Check 'a manifest exactly at the file cap is allowed' ($r.Code -eq 0) $r.Out

    # 14. later runs: a missing path inside the copy blocks (a hole in the manifest); a missing path elsewhere is feedback to the worker
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if ($t -match 'INSIDE') { Get-Content (Join-Path $PSScriptRoot '..\side-file.txt') -ErrorAction Stop | Out-Null }
if ($t -match 'NEITHER') { Get-Content (Join-Path $PSScriptRoot 'missing-live-as-well.txt') -ErrorAction Stop | Out-Null }
if ($t -match 'OUTSIDE') { Get-Content (Join-Path $env:TEMP 'freeze-test-surely-missing-file.txt') -ErrorAction Stop | Out-Null }
if ($t -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    Set-Content (Join-Path $base 'side-file.txt') 'beside the verifier folder' -Encoding utf8   # $vd is a folder of $base: this file is beside it, live, and not in the copy
    $c = NewCase @("$fence`nINSIDE`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a path that exists beside the live verifier but not in its copy, found only on a later run, blocks with manifest-incomplete' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED \(manifest-incomplete\)' -and $r.Out -match 'side-file\.txt') $r.Out
    $c = NewCase @("$fence`nNEITHER`n$fence", "$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a path missing in the copy and missing live as well is a fault of the verifier, not of the manifest: feedback, not a block' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED on attempt 2') $r.Out
    $c = NewCase @("$fence`nOUTSIDE`n$fence", "$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a missing path outside the copy is feedback, not a block: the next attempt can pass' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED on attempt 2') $r.Out

    # 15. the rows and the manifest file: hashes on every row, equal across them, paths and hashes only
    $vd = NewVd; Set-Content (Join-Path $vd 'fixtures\secret.txt') 'CANARY-FREEZE-7Q2' -Encoding utf8
    $c = NewCase @("$fence`nnope`n$fence", "$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1'); $rows = Rows $c
    $hashes = @($rows | ForEach-Object { $_.verifier_sha256 } | Select-Object -Unique)
    Check 'every attempt row and the run row carry the same raw and normalised manifest hash' ($r.Code -eq 0 -and $rows.Count -eq 3 -and $hashes.Count -eq 1 -and $hashes[0] -match '^[0-9a-f]{64}$' -and @($rows | Where-Object { $_.verifier_norm_sha256 -match '^[0-9a-f]{64}$' }).Count -eq 3 -and (RunRow $c).verifier_files -eq 3) ($rows | ConvertTo-Json -Compress)
    $mf = Get-Content -Raw (Join-Path $c 'work\manifest.json') | ConvertFrom-Json
    Check 'manifest.json lists paths and hashes, the interpreter version and the caps, and no file contents' ($mf.files.Count -eq 3 -and $mf.sha256 -eq $hashes[0] -and $mf.powershell -and $mf.caps.files -eq 500 -and (Get-Content -Raw (Join-Path $c 'work\manifest.json')) -notmatch 'CANARY-FREEZE' -and (Get-Content -Raw (Join-Path $c 'outcomes.jsonl')) -notmatch 'CANARY-FREEZE') (Get-Content -Raw (Join-Path $c 'work\manifest.json'))

    # 16. -ReverifyOf: after a deliberate edit, three proofs, no model call, a diff of paths and hashes, and only accepted-after-verifier-edit
    $vd = NewVd; $c = NewCase @("$fence`nbad one`n$fence", "$fence`nbad two`n$fence", "$fence`nbad three`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'GOOD original output' -Encoding utf8
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c; $callsBefore = Calls $c
    Check 'setup: a run that is not accepted leaves its rejected candidate and the original in the work folder' ($r1.Code -eq 1 -and (Test-Path (Join-Path $c 'work\best-candidate.txt')) -and (Test-Path (Join-Path $c 'work\out-before.txt'))) $r1.Out
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-a'
    Check 'an unchanged verifier is not re-verified: exit 2 and it says so' ($r2.Code -eq 2 -and $r2.Out -match 'nothing to re-verify') $r2.Out
    Add-Content (Join-Path $vd 'verify.ps1') '# a harmless edit'
    Set-Content (Join-Path $vd 'fixtures\extra.txt') 'new fixture' -Encoding utf8
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'; $row2 = RunRow $c
    Check 'the safe path ends in accepted-after-verifier-edit with exit 0 and makes no model call' ($r2.Code -eq 0 -and $row2.state -eq 'accepted-after-verifier-edit' -and (Calls $c) -eq $callsBefore -and $row2.reverify_of -eq $run1.run) $r2.Out
    Check 'both manifest hashes are recorded and they differ' ($row2.old_verifier_sha256 -eq $run1.verifier_sha256 -and $row2.verifier_sha256 -match '^[0-9a-f]{64}$' -and $row2.verifier_sha256 -ne $row2.old_verifier_sha256) ($row2 | ConvertTo-Json -Compress)
    $rv = Get-Content -Raw (Join-Path $c 'work-b\reverify.json') | ConvertFrom-Json
    Check 'all three proofs ran and passed' (@($rv.proofs | Where-Object { $_.status -eq 'passed' }).Count -eq 3) (($rv.proofs | ConvertTo-Json -Compress))
    Check 'the diff names the edited and the added file by path and hash prefix, and holds no contents' (($rv.diff -join '|') -match 'changed: verify\.ps1' -and ($rv.diff -join '|') -match 'added: fixtures/extra\.txt' -and (Get-Content -Raw (Join-Path $c 'work-b\reverify.json')) -notmatch 'new fixture|harmless edit') ($rv.diff -join '|')
    Check 'a re-verified run is never counted as an ordinary accept' (@(Rows $c | Where-Object { $_.state -eq 'accepted' }).Count -eq 0) ((Rows $c) | ConvertTo-Json -Compress)

    # 16b. a run blocked by a mid-run verifier edit, with an output file from before: that original is re-proved; the rejected-candidate proof is skipped (none yet)
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'GOOD original output' -Encoding utf8
    SetMutation $c 1 'Add-Content (Join-Path $env:VD ''verify.ps1'') ''# edited on purpose'''
    $env:VD = $vd
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'
    $rv = Get-Content -Raw (Join-Path $c 'work-b\reverify.json') | ConvertFrom-Json
    Check 'after a mid-run block, -ReverifyOf accepts the deliberate edit, re-proves the original and records the proof it had to skip' ($r1.Code -eq 3 -and $r2.Code -eq 0 -and @($rv.proofs | Where-Object { $_.status -eq 'skipped' }).Count -eq 1 -and @($rv.proofs | Where-Object { $_.status -eq 'passed' }).Count -eq 2) ($r1.Out + $r2.Out)

    # 16c. a run blocked at attempt 2 after attempt 1 was rejected keeps that rejected candidate (best-candidate.txt), so the third proof can run
    $vd = NewVd; $c = NewCase @("$fence`nbad one`n$fence", "$fence`nGOOD`n$fence")
    SetMutation $c 2 'Add-Content (Join-Path $env:VD ''verify.ps1'') ''# edited on purpose'''
    $env:VD = $vd
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'
    $rv = Get-Content -Raw (Join-Path $c 'work-b\reverify.json') | ConvertFrom-Json
    Check 'a blocked run keeps the candidate its old verifier rejected, and the edited verifier is re-proved against it' ($r1.Code -eq 3 -and (Test-Path (Join-Path $c 'work\best-candidate.txt')) -and $r2.Code -eq 0 -and (@($rv.proofs | Where-Object { $_.proof -match 'rejected' -and $_.status -eq 'passed' }).Count -eq 1)) ($r1.Out + $r2.Out)

    # 16d. nothing earlier to re-prove against: the empty stub alone is refused
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    SetMutation $c 1 'Add-Content (Join-Path $env:VD ''verify.ps1'') ''# edited on purpose'''
    $env:VD = $vd
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'
    Check 'with no original and no rejected candidate there is nothing to re-prove: refused (exit 2), not accepted-after-verifier-edit' ($r2.Code -eq 2 -and $r2.Out -match 'REFUSED \(reverify-nothing-to-prove\)' -and (RunRow $c).state -ne 'accepted-after-verifier-edit') $r2.Out

    # 16e. a different verifier, or a run with no manifest, cannot be re-verified against that run
    $vd = NewVd; $c = NewCase @("$fence`nbad one`n$fence", "$fence`nbad two`n$fence", "$fence`nbad three`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'GOOD original output' -Encoding utf8
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    $other = NewVd "param([string] `$Script)`nif ((Get-Content -Raw `$Script) -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }`nWrite-Output 'FAIL not GOOD'; exit 1`n"
    $r2 = Run $c (Join-Path $other 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'
    Check 'a different verifier (another folder) is refused as the subject of -ReverifyOf (exit 2)' ($r2.Code -eq 2 -and $r2.Out -match 'different verifier') $r2.Out
    Add-Content (Join-Path $c 'outcomes.jsonl') ('{"kind":"run","run":"fakerun00001","state":"budget exhausted","work_dir":"' + (Join-Path $c 'no-such-work').Replace('\', '\\') + '"}')
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', 'fakerun00001') 'out.ps1' 'work-c'
    Check 'a run whose manifest is gone is refused as the subject of -ReverifyOf (exit 2)' ($r2.Code -eq 2 -and $r2.Out -match 'no readable manifest') $r2.Out

    # 17. a weakened verifier (one that now accepts the rejected candidate) fails the third proof: blocked, exit 3
    $vd = NewVd; $c = NewCase @("$fence`nbad one`n$fence", "$fence`nbad two`n$fence", "$fence`nbad three`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'GOOD original output' -Encoding utf8
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    Set-Content (Join-Path $vd 'verify.ps1') "param([string] `$Script)`nif ((Get-Content -Raw `$Script)) { Write-Output '1/1 passed'; exit 0 }`nWrite-Output 'FAIL empty'; exit 1`n" -Encoding utf8
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'; $row2 = RunRow $c
    Check 'a verifier edited to accept the earlier rejected candidate is blocked by the third proof (exit 3, not accepted-after-verifier-edit)' ($r2.Code -eq 3 -and $row2.state -eq 'blocked' -and $row2.reason -eq 'reverify-failed' -and $r2.Out -match 'failed\s+previously rejected candidate still fails') $r2.Out

    # 17b. an edit that makes the unchanged original fail (the new verifier rejects what the old one accepted) fails the second proof
    $vd = NewVd; $c = NewCase @("$fence`nbad one`n$fence", "$fence`nbad two`n$fence", "$fence`nbad three`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'GOOD original output' -Encoding utf8
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    Set-Content (Join-Path $vd 'fixtures\expect.txt') 'SOMETHING ELSE' -Encoding utf8
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'; $row2 = RunRow $c
    Check 'a verifier edited so that the unchanged original now fails is blocked by the second proof' ($r2.Code -eq 3 -and $row2.reason -eq 'reverify-failed' -and $r2.Out -match 'failed\s+unchanged original keeps its verdict') $r2.Out

    # 18. an unknown run id is a usage error
    $vd = NewVd; $c = NewCase @(); $r = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', 'doesnotexist1')
    Check 'an unknown -ReverifyOf run id is a usage error (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'no run row') $r.Out

    # 18b. ordinary verifiers that fail on an empty stub with a missing function, an import error or a message that only mentions a file are not refused
    $vd = NewVd @'
param([string] $Script)
. $Script
if ((Get-Answer) -eq 42) { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL wrong answer'; exit 1
'@
    $c = NewCase @("$fence`nfunction Get-Answer { 42 }`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that calls a function the empty stub lacks (is not recognized) is not refused, and accepts a candidate that defines it' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $vp = Join-Path $base ('vi-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $vp | Out-Null
        Set-Content (Join-Path $vp 'verify.py') "import sys`nt = open(sys.argv[1], encoding='utf-8').read()`nif not t.strip():`n    raise ImportError(`"cannot import name 'solve' from 'candidate'`")`nsys.exit(0 if 'GOOD' in t else 1)`n" -Encoding utf8
        $c = NewCase @("$fence`nGOOD`n$fence")
        $r = Run $c (Join-Path $vp 'verify.py') @() 'out.txt'
        Check 'a Python verifier whose empty-stub failure is an ImportError is not refused' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out
    }
    $vd = NewVd @'
param([string] $Script)
if (-not (Get-Content -Raw $Script)) { Write-Output 'FAIL test_raises_FileNotFoundError: no file No such file or directory'; exit 1 }
Write-Output '1/1 passed'; exit 0
'@
    $c = NewCase @("$fence`nanything`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that only mentions a missing file in its own FAIL text is not refused' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out

    # 18c. what a verifier leaves in its working folder cannot reach the next look: a marker written by one run is gone before the next, and nothing is accepted on it
    $vd = NewVd @'
param([string] $Script)
$marker = Join-Path $PSScriptRoot 'cache\ok'
if (Test-Path $marker) { Write-Output '1/1 passed'; exit 0 }
New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'cache') | Out-Null
Set-Content $marker 'x'
Write-Output 'FAIL first look, no marker'; exit 1
'@
    $c = NewCase @("$fence`none`n$fence", "$fence`ntwo`n$fence", "$fence`nthree`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a marker the verifier writes in its folder is removed before the next run: three attempts, none accepted, nothing left in the copy' ($r.Code -eq 1 -and $r.Out -match 'NOT ACCEPTED' -and -not (Test-Path (Join-Path $c 'work\verifier-copy\cache'))) $r.Out

    # 18d. a verifier that removes the candidate after judging it blocks the run
    $vd = NewVd @'
param([string] $Script)
if ((Get-Content -Raw $Script) -match 'GOOD') { Remove-Item $Script; Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a candidate removed by the verifier blocks the run and is not reported as accepted' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED \(candidate-changed\)' -and $r.Out -match 'removed' -and $r.Out -cnotmatch 'ACCEPTED') $r.Out

    # 18e. a folder named twice (-VerifierFiles holding a subfolder of the verifier's own folder) is counted once against the cap
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Run $c (Join-Path $vd 'verify.ps1') @('-VerifierFiles', (Join-Path $vd 'fixtures'), '-MaxManifestFiles', '2')
    Check 'a file reached twice counts once against -MaxManifestFiles (two files, cap 2: accepted)' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out

    # 18f. a python verifier with no python on PATH is refused before the first call
    $vp = Join-Path $base ('vn-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $vp | Out-Null
    Set-Content (Join-Path $vp 'verify.py') "import sys`nsys.exit(1)`n" -Encoding utf8
    $c = NewCase @("$fence`nGOOD`n$fence")
    $oldPath = $env:PATH; $env:PATH = Split-Path -Parent (Get-Command pwsh).Source
    try { $r = Run $c (Join-Path $vp 'verify.py') @() 'out.txt' 
} finally { $env:PATH = $oldPath }
    Check 'a verifier whose interpreter cannot be started is refused (exit 2) before the first call, not a crash' ($r.Code -eq 2 -and $r.Out -match 'REFUSED \(preflight-no-interpreter\)' -and (Calls $c) -eq 0) $r.Out

    # 18g. -ReverifyOf is bracketed too: a verifier that edits a live file during a proof run blocks the re-verification
    $vd = NewVd @'
param([string] $Script)
Add-Content (Join-Path $env:STUB_DIR 'vruns.txt') 'r'
$t = Get-Content -Raw $Script
if ($env:EDIT_LIVE -and $t -match 'original') { Add-Content (Join-Path $env:VD 'fixtures\expect.txt') 'late' }
$expect = (Get-Content -Raw (Join-Path $PSScriptRoot 'fixtures\expect.txt')).Trim().Split("`n")[0].Trim()
if ($t -match [regex]::Escape($expect)) { Write-Output '1/1 passed'; exit 0 }
Write-Output "FAIL candidate does not say $expect"; exit 1
'@
    $c = NewCase @("$fence`nbad one`n$fence", "$fence`nbad two`n$fence", "$fence`nbad three`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'GOOD original output' -Encoding utf8
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    Add-Content (Join-Path $vd 'verify.ps1') '# a harmless edit'
    $runsBefore = @(Get-Content (Join-Path $c 'vruns.txt')).Count
    $env:VD = $vd; $env:EDIT_LIVE = '1'
    try { $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b' } finally { Remove-Item Env:EDIT_LIVE -ErrorAction SilentlyContinue }
    # two verifier runs only (the pre-flight and the proof that edited the file): the look after each proof stops the re-verification before the next one
    Check 'a live file edited while the re-verification runs blocks it at once, before the next proof, instead of ending in accepted-after-verifier-edit' ($r2.Code -eq 3 -and $r2.Out -match 'BLOCKED \(verifier-changed\)' -and (RunRow $c).state -eq 'blocked' -and (@(Get-Content (Join-Path $c 'vruns.txt')).Count - $runsBefore) -eq 2) $r2.Out

    # 18h. a verifier that edits a live file during the pre-flight is blocked before the first model call
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if (-not $t) { Add-Content (Join-Path $env:VD 'fixtures\expect.txt') 'pre' }
if ($t -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence"); $env:VD = $vd
    $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a live file edited during the pre-flight blocks the run at attempt 0, with no model call made' ($r.Code -eq 3 -and $r.Out -match 'BLOCKED \(verifier-changed\) at attempt 0' -and (Calls $c) -eq 0) $r.Out

    # 18i. the verifier's own folder reached through a junction is refused
    $vd = NewVd; $jv = Join-Path $base ('jv-' + [guid]::NewGuid().ToString('N').Substring(0, 6))
    New-Item -ItemType Junction -Path $jv -Target $vd | Out-Null
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $jv 'verify.ps1')
    Check 'a verifier whose own folder is a junction is refused at start (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'symlink or junction') $r.Out

    # 18j. a missing path on another drive is not a hole, and does not crash the matcher
    $holeText = "Cannot find path 'Z:\no\such\drive\x.txt' because it does not exist."
    $threw = $false; $holeOut = 'unset'
    try { $holeOut = Get-VfHole $holeText (Join-Path $base 'copy') $base $base @() } catch { $threw = $true }
    Check 'a missing path on another drive neither counts as a hole nor throws' (-not $threw -and $null -eq $holeOut) "threw=$threw out=$holeOut"

    # 18k. the original output file is re-proved by VERDICT, not by a pass: a stale draft that failed the old verifier must still fail the edited one
    $vd = NewVd; $c = NewCase @("$fence`nGOOD`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'a stale draft that never said the word' -Encoding utf8
    SetMutation $c 1 'Add-Content (Join-Path $env:VD ''verify.ps1'') ''# edited on purpose'''
    $env:VD = $vd
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'
    $rv = Get-Content -Raw (Join-Path $c 'work-b\reverify.json') | ConvertFrom-Json
    Check 'a stale draft that failed the old verifier and fails the edited one is not a false block: the verdict is the same' ($r1.Code -eq 3 -and $r2.Code -eq 0 -and @($rv.proofs | Where-Object { $_.proof -match 'original' -and $_.status -eq 'passed' -and $_.detail -match 'now fail, recorded fail' }).Count -eq 1) ($r1.Out + $r2.Out)

    # 18l. a script reached by a dot-source from a sibling folder is a hole too (the error names a path): refused at pre-flight, and accepted when named
    $lib = Join-Path $base 'lib-freeze-test.ps1'
    Set-Content $lib 'function Test-Good([string] $s) { return ($s -match ''GOOD'') }' -Encoding utf8
    $vd = NewVd @'
param([string] $Script)
. (Join-Path $PSScriptRoot '..\lib-freeze-test.ps1')
if (Test-Good (Get-Content -Raw $Script)) { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a verifier that dot-sources a sibling script it did not name is refused before the first call, naming it' ($r.Code -eq 2 -and $r.Out -match 'REFUSED \(preflight-missing\)' -and $r.Out -match 'lib-freeze-test\.ps1' -and (Calls $c) -eq 0) $r.Out
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1') @('-VerifierFiles', $lib)
    Check 'the same verifier with that script named in -VerifierFiles is accepted' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out

    # 18m. the re-verification proofs look for holes too: an edited verifier that now reaches a sibling on the rejected candidate's path fails that proof
    Set-Content (Join-Path $base 'side2.txt') 'beside the verifier folder' -Encoding utf8
    $vd = NewVd; $c = NewCase @("$fence`nbad one`n$fence", "$fence`nbad two`n$fence", "$fence`nbad three`n$fence")
    $r1 = Run $c (Join-Path $vd 'verify.ps1'); $run1 = RunRow $c
    Set-Content (Join-Path $vd 'verify.ps1') "param([string] `$Script)`n`$t = Get-Content -Raw `$Script`nif (`$t -match 'bad') { Get-Content (Join-Path `$PSScriptRoot '..\side2.txt') -ErrorAction Stop | Out-Null }`nif (`$t -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }`nWrite-Output 'FAIL not GOOD'; exit 1`n" -Encoding utf8
    $r2 = Run $c (Join-Path $vd 'verify.ps1') @('-ReverifyOf', $run1.run) 'out.ps1' 'work-b'
    Check 'a re-verification proof that hits a hole in the manifest fails instead of counting a crash as a rejection' ($r2.Code -eq 3 -and $r2.Out -match 'failed\s+previously rejected candidate still fails' -and $r2.Out -match 'beside the live verifier') $r2.Out

    # 18n. a verifier that looks beside the CANDIDATE is not mistaken for one with a hole, even when the same name exists beside the verifier's folder
    Set-Content (Join-Path $base 'expected.txt') 'GOOD' -Encoding utf8
    $vd = NewVd @'
param([string] $Script)
$t = Get-Content -Raw $Script
if (-not $t) { Get-Content (Join-Path (Split-Path -Parent $Script) 'expected.txt') -ErrorAction Stop | Out-Null }
if ($t -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL not GOOD'; exit 1
'@
    $c = NewCase @("$fence`nGOOD`n$fence"); $r = Run $c (Join-Path $vd 'verify.ps1')
    Check 'a path beside the candidate that happens to exist beside the live verifier too is not counted as a hole' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED') $r.Out

    # 19. the same tree with CRLF and with LF line endings: the raw hashes differ, the normalised hashes are equal; a binary file is never normalised
    $a = Join-Path $base 'tree-lf'; $b = Join-Path $base 'tree-crlf'
    foreach ($t in $a, $b) { New-Item -ItemType Directory (Join-Path $t 'sub') -Force | Out-Null }
    foreach ($f in 'verify.ps1', 'sub\fixture.txt') {
        [IO.File]::WriteAllText((Join-Path $a $f), "line one`nline two`n")
        [IO.File]::WriteAllText((Join-Path $b $f), "line one`r`nline two`r`n")
    }
    [IO.File]::WriteAllBytes((Join-Path $a 'sub\bin.dat'), [byte[]](1, 13, 10, 0, 2)); [IO.File]::WriteAllBytes((Join-Path $b 'sub\bin.dat'), [byte[]](1, 13, 10, 0, 2))
    $pa = Get-VerifierPlan (Join-Path $a 'verify.ps1') @() (Join-Path $base 'x.out') (Join-Path $base 'w1') 500 20971520
    $pb = Get-VerifierPlan (Join-Path $b 'verify.ps1') @() (Join-Path $base 'x.out') (Join-Path $base 'w1') 500 20971520
    $ha = Get-VfHashes $pa $null; $hb = Get-VfHashes $pb $null
    Check 'a CRLF checkout and an LF checkout of one tree: raw manifest hashes differ, normalised hashes are equal' ((Get-VfManifestHash $ha 'Raw') -ne (Get-VfManifestHash $hb 'Raw') -and (Get-VfManifestHash $ha 'Norm') -eq (Get-VfManifestHash $hb 'Norm')) ''
    Check 'a file with a NUL byte is binary: its normalised hash is its raw hash' ($ha['sub/bin.dat'].Raw -eq $ha['sub/bin.dat'].Norm) ''
    New-Item -ItemType Directory (Join-Path $a '__pycache__') -Force | Out-Null; Set-Content (Join-Path $a '__pycache__\v.cpython-313.pyc') 'x'; Set-Content (Join-Path $a 'old.pyc') 'x'; New-Item -ItemType Directory (Join-Path $a '.pytest_cache') -Force | Out-Null; Set-Content (Join-Path $a '.pytest_cache\x') 'x'
    $pa2 = Get-VerifierPlan (Join-Path $a 'verify.ps1') @() (Join-Path $base 'x.out') (Join-Path $base 'w1') 500 20971520
    Check 'caches and bytecode are not in the manifest' ((@($pa2.Files.Rel) -join ',') -eq 'sub/bin.dat,sub/fixture.txt,verify.ps1' -and $pa2.Root -eq $a) (@($pa2.Files.Rel) -join ',')
    # 18o. the hash sets compare names the way the file system does
    $plan = Get-VerifierPlan (Join-Path $a 'verify.ps1') @() (Join-Path $base 'x.out') (Join-Path $base 'w1') 500 20971520
    $hs = Get-VfHashes $plan $null
    Check 'the hash set is an ordered dictionary whose name comparison follows the platform (ignoring case on Windows only)' ($hs.GetType().Name -eq 'OrderedDictionary' -and ($hs.Contains('VERIFY.PS1') -eq [bool]$IsWindows)) ($hs.GetType().FullName)

} finally {
    Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue
    foreach ($k in 'STUB_DIR', 'VD', 'EX', 'ABS_FILE', 'EDIT_LIVE') { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
}
Write-Output "$($n - $fail.Count)/$n passed"
if ($fail.Count) { exit 1 }
Write-Output 'VERIFIED'
exit 0
