# Test for delegate-batch.ps1 with a stub worker. No model, Ollama or network.
param([string] $Script = (Join-Path $PSScriptRoot 'delegate-batch.ps1'))
$ErrorActionPreference = 'Stop'
$base = Join-Path ([IO.Path]::GetTempPath()) ('batch-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $base | Out-Null
$fail = @(); $n = 0
# keep the tests' outcome lines out of the real central log
$env:LOCAL_WORKER_OUTCOME_LOG = Join-Path $base 'outcomes.jsonl'
$env:LOCAL_WORKER_USAGE_LOG = Join-Path $base 'usage-central.jsonl'
$env:BATCH_STUB_DIR = $base
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }

# A stub worker: answers GOOD when the task text contains MAKE-GOOD, otherwise a reply the verifier rejects.
Set-Content (Join-Path $base 'stub.ps1') @'
param([string] $PromptFile, [string] $ProfileFile, [string] $Model, [string] $SystemFile, [int] $NumCtx, [int] $MaxOutputTokens, [string] $ThinkMode, [string] $ThinkingFile, [string] $LogFile, [string] $Tag, [int] $Attempt, [string] $Mode)
Add-Content (Join-Path $env:BATCH_STUB_DIR 'numctx.txt') "numctx=$NumCtx"
$p = Get-Content -Raw $PromptFile
$f = '```'
if ($p -match 'MAKE-GOOD') { "here:`n$f`nGOOD thing`n$f`n" } else { "here:`n$f`nnope`n$f`n" }
'@ -Encoding utf8
New-Item -ItemType Directory (Join-Path $base 'v') | Out-Null   # the verifier gets a folder of its own: delegate.ps1 freezes the verifier's whole folder (V2-02)
Set-Content (Join-Path $base 'v/verify.ps1') @'
param([string] $Script)
if ((Get-Content -Raw $Script) -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL candidate does not say GOOD'; Write-Output '0/1 passed'; exit 1
'@ -Encoding utf8
Set-Content (Join-Path $base 'good.md') 'MAKE-GOOD please' -Encoding utf8
Set-Content (Join-Path $base 'bad.md') 'write a thing' -Encoding utf8
$stub = Join-Path $base 'stub.ps1'

function Run([string] $json, [string[]] $extra = @()) {
    $b = Join-Path $base ('batch-' + [guid]::NewGuid().ToString('N').Substring(0, 6) + '.json')
    Set-Content $b $json -Encoding utf8
    $o = & pwsh -NoProfile -File $Script -Batch $b -InvokeScript $stub @extra 2>&1 | Out-String
    return @{ Code = $LASTEXITCODE; Out = $o; Batch = $b }
}
$item = { param($name, $task) "{ `"name`": `"$name`", `"task`": `"$task`", `"verify`": `"v/verify.ps1`", `"out`": `"out-$name.ps1`" }" }
try {
    # 1. one good, one never good, one with a missing task file: the batch goes on, exit 1, a results file, a log per item
    $json = '[' + (& $item 'one' 'good.md') + ',' + (& $item 'two' 'bad.md') + ',' + (& $item 'three' 'nothere.md') + ',' + (& $item 'four' 'good.md') + ']'
    $r = Run $json
    Check 'exit 1 when any item fails' ($r.Code -eq 1) "$($r.Code) $($r.Out)"
    Check 'the good item is accepted on attempt 1' ($r.Out -match 'one\s+accepted\s+\d+s\s+attempt 1') $r.Out
    Check 'the bad item is not accepted after 3 attempts' ($r.Out -match 'two\s+not accepted\s+\d+s\s+after 3 attempt') $r.Out
    Check 'a missing file is reported for that item only' ($r.Out -match 'three\s+error\s+\d+s\s+missing file: nothere.md') $r.Out
    Check 'the batch continues after a failure' ($r.Out -match 'four\s+accepted') $r.Out
    Check 'the summary line counts accepted items' ($r.Out -match '2 of 4 accepted') $r.Out
    $res = Get-Content -Raw ($r.Batch -replace '\.json$', '.results.json') | ConvertFrom-Json
    Check 'results.json lists four items in order' (@($res).Count -eq 4 -and $res[0].name -eq 'one' -and $res[3].status -eq 'accepted') ($res | Out-String)
    Check 'the accepted candidate was written' ((Get-Content -Raw (Join-Path (Split-Path $r.Batch) 'out-one.ps1')) -match 'GOOD thing')
    Check 'a log file is kept per item' (Test-Path (Join-Path (Split-Path $r.Batch) 'log-two.txt'))
    Check 'work folders are per item' ((Test-Path (Join-Path (Split-Path $r.Batch) 'work-one')) -and (Test-Path (Join-Path (Split-Path $r.Batch) 'work-two')))

    # 2. all good: exit 0
    $r = Run ('[' + (& $item 'a' 'good.md') + ',' + (& $item 'b' 'good.md') + ']')
    Check 'exit 0 when every item is accepted' ($r.Code -eq 0 -and $r.Out -match '2 of 2 accepted') "$($r.Code) $($r.Out)"

    # 3. -StopOnFail stops at the first failure
    $r = Run ('[' + (& $item 'x' 'bad.md') + ',' + (& $item 'y' 'good.md') + ']') @('-StopOnFail')
    Check '-StopOnFail does not run later items' ($r.Out -match 'stopping' -and $r.Out -notmatch '\sy\s+accepted') $r.Out
    Check '-StopOnFail still exits 1' ($r.Code -eq 1)

    # 3b. a SALVAGED outcome (exit 0 from delegate.ps1) is an accepted item that says so, not an error
    Set-Content (Join-Path $base 'salvage-delegate.ps1') 'Write-Host "SALVAGED on attempt 3 (thinking): the call hit the token cap, but a complete answer inside its thinking text passed the verifier"; exit 0' -Encoding utf8
    $r = Run ('[' + (& $item 's' 'good.md') + ']') @('-DelegateScript', (Join-Path $base 'salvage-delegate.ps1'))
    Check 'a salvaged answer is accepted and flagged, not reported as an error' ($r.Code -eq 0 -and $r.Out -match 's\s+accepted\s+\d+s\s+attempt 3 SALVAGED' -and $r.Out -notmatch 'error') "$($r.Code) $($r.Out)"

    # 3b2. V2-01: a CANCELLED run (a CANCEL file in an item's work folder) is reported as cancelled, not as an error, and the batch goes on
    Set-Content (Join-Path $base 'cancel-delegate.ps1') 'Write-Host "CANCELLED before attempt 2: a CANCEL file is in the work folder, so no further call was made."; exit 1' -Encoding utf8
    $r = Run ('[' + (& $item 'c1' 'good.md') + ',' + (& $item 'c2' 'good.md') + ']') @('-DelegateScript', (Join-Path $base 'cancel-delegate.ps1'))
    Check 'a cancelled item is reported as cancelled with the attempt it stopped before, not as an error' ($r.Out -match 'c1\s+cancelled\s+\d+s\s+before attempt 2' -and $r.Out -notmatch 'error') $r.Out
    Check 'a cancelled item does not stop the batch and the batch exits 1 (not every item was accepted)' ($r.Out -match 'c2\s+cancelled' -and $r.Code -eq 1 -and $r.Out -match '0 of 2 accepted') "$($r.Code) $($r.Out)"

    # 3b3. V2-02: a blocked run (exit 3: the verifier changed mid-run) and a refused one (exit 2 before the first call) are named, not reported as an error; the batch goes on
    Set-Content (Join-Path $base 'blocked-delegate.ps1') 'Write-Host "BLOCKED (verifier-changed) at attempt 1: nothing was accepted, and the output file was put back."; exit 3' -Encoding utf8
    Set-Content (Join-Path $base 'refused-delegate.ps1') 'Write-Host "REFUSED (preflight-cannot-fail): the verifier accepted an empty file (exit 0), so it cannot fail."; exit 2' -Encoding utf8
    $r = Run ('[' + (& $item 'k1' 'good.md') + ',' + (& $item 'k2' 'good.md') + ']') @('-DelegateScript', (Join-Path $base 'blocked-delegate.ps1'))
    Check 'a blocked item is reported as blocked with its reason, and the batch goes on' ($r.Out -match 'k1\s+blocked\s+\d+s\s+verifier-changed' -and $r.Out -match 'k2\s+blocked' -and $r.Out -notmatch 'error' -and $r.Code -eq 1) $r.Out
    $r = Run ('[' + (& $item 'f1' 'good.md') + ']') @('-DelegateScript', (Join-Path $base 'refused-delegate.ps1'))
    Check 'a refused item is reported as refused with its reason' ($r.Out -match 'f1\s+refused\s+\d+s\s+preflight-cannot-fail') $r.Out

    # 3b4. V2-02: an item's verifier_files reach delegate.ps1 as -VerifierFiles, resolved against the batch folder
    Set-Content (Join-Path $base 'args-delegate.ps1') 'param([string] $TaskFile, [string] $Verify, [string] $OutFile, [string] $WorkDir, [int] $MaxOutputTokens, [string[]] $VerifierFiles, [string] $InvokeScript); Set-Content (Join-Path (Split-Path -Parent $OutFile) "vf.txt") ($VerifierFiles -join "|"); Write-Host "ACCEPTED on attempt 1"; exit 0' -Encoding utf8
    $r = Run '[{ "name": "vf", "task": "good.md", "verify": "v/verify.ps1", "out": "out-vf.ps1", "verifier_files": ["data", "C:\\abs\\x"] }]' @('-DelegateScript', (Join-Path $base 'args-delegate.ps1'))
    $vfSeen = Get-Content -Raw (Join-Path (Split-Path $r.Batch) 'vf.txt')
    Check 'verifier_files reach delegate.ps1, a relative one resolved against the batch folder and an absolute one kept' ($r.Code -eq 0 -and $vfSeen.Trim() -eq ((Join-Path (Split-Path $r.Batch) 'data') + ',C:\abs\x')) "$vfSeen $($r.Out)"

    # 3c. V2-06a: -NumCtx reaches a worker only when the batch caller sets it (a profile's own num_ctx must not be overridden by a hidden default)
    $nc = Join-Path $base 'numctx.txt'
    Remove-Item $nc -ErrorAction SilentlyContinue
    $r = Run ('[' + (& $item 'n1' 'good.md') + ']')
    Check 'no -NumCtx on the batch: the worker is called with none' ($r.Code -eq 0 -and (Test-Path $nc) -and (Get-Content $nc) -contains 'numctx=0') "$($r.Code) $($r.Out)"
    Remove-Item $nc -ErrorAction SilentlyContinue
    $r = Run ('[' + (& $item 'n2' 'good.md') + ']') @('-NumCtx', '4096')
    Check 'an explicit -NumCtx 4096 on the batch reaches the worker' ($r.Code -eq 0 -and (Test-Path $nc) -and (Get-Content $nc) -contains 'numctx=4096') "$($r.Code) $($r.Out)"

    # 4. usage errors exit 2
    $r = Run '[]'
    Check 'an empty batch is a usage error' ($r.Code -eq 2) "$($r.Code) $($r.Out)"
    $r = Run 'not json'
    Check 'invalid JSON is a usage error' ($r.Code -eq 2 -and $r.Out -match 'not valid JSON') $r.Out
    $r = Run '[{ "name": "a", "task": "good.md", "verify": "v/verify.ps1" }]'
    Check 'an item without out is a usage error' ($r.Code -eq 2 -and $r.Out -match "missing 'out'") $r.Out
    $r = Run ('[' + (& $item 'dup' 'good.md') + ',' + (& $item 'dup' 'good.md') + ']')
    Check 'duplicate names are a usage error' ($r.Code -eq 2 -and $r.Out -match 'unique') $r.Out
    $r = Run ('[' + (& $item '../evil' 'good.md') + ']')
    Check 'a name with a path separator is a usage error' ($r.Code -eq 2 -and $r.Out -match 'may use only') $r.Out
    $o = & pwsh -NoProfile -File $Script -Batch (Join-Path $base 'nope.json') 2>&1 | Out-String
    Check 'a missing batch file is a usage error' ($LASTEXITCODE -eq 2) $o

    # 5. The queue: order, links, resume, subsets, a batch-level CANCEL, totals and -DryRun. A recording stub stands in for delegate.ps1: it appends
    # "<name> tag=.. attempts=.. tokens=.." to order.txt beside the batch, accepts a task that says MAKE-GOOD, copies the results file when the task
    # says SNAPSHOT (to see what an interrupted batch would keep) and creates the batch's CANCEL file when the task says MAKE-CANCEL.
    $rec = Join-Path $base 'rec-delegate.ps1'
    Set-Content $rec @'
param([string] $TaskFile, [string] $Verify, [string] $OutFile, [string] $WorkDir, [int] $MaxOutputTokens, [string] $Tag, [int] $MaxAttempts)
$bd = Split-Path -Parent $OutFile
$name = [IO.Path]::GetFileNameWithoutExtension($OutFile) -replace '^out-', ''
Add-Content (Join-Path $bd 'order.txt') "$name tag=$Tag attempts=$MaxAttempts tokens=$MaxOutputTokens"
$t = Get-Content -Raw $TaskFile
if ($t -match 'SNAPSHOT') { Get-ChildItem -LiteralPath $bd -Filter '*.results.json' | ForEach-Object { Copy-Item -LiteralPath $_.FullName (Join-Path $bd ('snap-' + $_.Name)) } }
if ($t -match 'MAKE-CANCEL') { Set-Content (Join-Path $bd 'CANCEL') 'stop' }
if ($t -match 'MAKE-GOOD') { Set-Content $OutFile 'GOOD'; Write-Host 'ACCEPTED on attempt 1'; exit 0 }
Write-Host 'NOT ACCEPTED after 3 attempt(s)'; exit 1
'@ -Encoding utf8
    # A fresh folder per batch, with its own task files and verifier folder, so order.txt, CANCEL and the results file belong to one test.
    function New-Batch([string] $json) {
        $d = Join-Path $base ('q-' + [guid]::NewGuid().ToString('N').Substring(0, 6))
        New-Item -ItemType Directory (Join-Path $d 'v') | Out-Null
        Copy-Item (Join-Path $base 'v/verify.ps1') (Join-Path $d 'v/verify.ps1')
        Set-Content (Join-Path $d 'good.md') 'MAKE-GOOD please' -Encoding utf8
        Set-Content (Join-Path $d 'bad.md') 'write a thing' -Encoding utf8
        Set-Content (Join-Path $d 'snap.md') 'MAKE-GOOD SNAPSHOT' -Encoding utf8
        Set-Content (Join-Path $d 'cancel.md') 'MAKE-GOOD MAKE-CANCEL' -Encoding utf8
        $b = Join-Path $d 'batch.json'
        Set-Content $b $json -Encoding utf8
        return $b
    }
    function RunB([string] $b, [string[]] $extra = @()) {
        $o = & pwsh -NoProfile -File $Script -Batch $b -DelegateScript $rec @extra 2>&1 | Out-String
        return @{ Code = $LASTEXITCODE; Out = $o; Batch = $b }
    }
    function Get-Order([string] $b) { $f = Join-Path (Split-Path $b) 'order.txt'; if (Test-Path $f) { @(Get-Content $f | ForEach-Object { ($_ -split ' ')[0] }) } else { @() } }
    function Get-Results([string] $b) { @(Get-Content -Raw ($b -replace '\.json$', '.results.json') | ConvertFrom-Json) }
    function J([string] $name, [string] $task, [string] $more = '') { "{ `"name`": `"$name`", `"task`": `"$task`", `"verify`": `"v/verify.ps1`", `"out`": `"out-$name.txt`"$more }" }

    # 5a. priority: lower first, default 100, ties keep file order; depends_on runs a dependency first whatever its priority
    $b = New-Batch ('[' + (J 'p1' 'good.md' ', "priority": 50') + ',' + (J 'p2' 'good.md') + ',' + (J 'p3' 'good.md' ', "priority": 10') + ',' + (J 'p4' 'good.md' ', "priority": 50') + ']')
    $r = RunB $b
    Check 'priority orders the items, lower first, default 100, ties in file order' ($r.Code -eq 0 -and ((Get-Order $b) -join ',') -eq 'p3,p1,p4,p2') "$((Get-Order $b) -join ',') $($r.Out)"
    $b = New-Batch ('[' + (J 'x' 'good.md' ', "priority": 1, "depends_on": ["y"]') + ',' + (J 'y' 'good.md' ', "priority": 100') + ']')
    $r = RunB $b
    Check 'an item runs after the item it depends on, whatever their priorities' ($r.Code -eq 0 -and ((Get-Order $b) -join ',') -eq 'y,x') "$((Get-Order $b) -join ',') $($r.Out)"

    # 5b. depends_on: an item whose dependency was not accepted is skipped and named; totals count it
    $b = New-Batch ('[' + (J 'a' 'bad.md') + ',' + (J 'b' 'good.md' ', "depends_on": ["a"]') + ']')
    $r = RunB $b
    Check 'an item whose dependency was not accepted is skipped, not run' ($r.Code -eq 1 -and $r.Out -match 'b\s+skipped \(dependency not accepted: a\)' -and ((Get-Order $b) -join ',') -eq 'a') "$((Get-Order $b) -join ',') $($r.Out)"
    Check 'the skipped status is written to the results file' ((Get-Results $b)[1].status -eq 'skipped (dependency not accepted: a)') ((Get-Results $b) | Out-String)
    Check 'the totals line counts each kind of status' ($r.Out -match 'totals: accepted 0, not accepted 1, blocked 0, refused 0, skipped 1, cancelled 0, other 0') $r.Out
    # a dependency accepted in an earlier run counts; the earlier row is kept in the results file
    $b = New-Batch ('[' + (J 'a' 'good.md') + ',' + (J 'b' 'good.md' ', "depends_on": ["a"]') + ']')
    $r = RunB $b @('-Only', 'a')
    Check '-Only runs only the named item' ($r.Code -eq 0 -and ((Get-Order $b) -join ',') -eq 'a' -and $r.Out -notmatch '\sb\s+') "$((Get-Order $b) -join ',') $($r.Out)"
    $r = RunB $b @('-Only', 'b')
    Check 'a dependency accepted in an earlier run lets the item run' ($r.Code -eq 0 -and ((Get-Order $b) -join ',') -eq 'a,b') "$((Get-Order $b) -join ',') $($r.Out)"
    $res = Get-Results $b
    Check 'the results file keeps the row of an item this run did not touch' ($res.Count -eq 2 -and $res[0].name -eq 'a' -and $res[0].status -eq 'accepted' -and $res[1].status -eq 'accepted') ($res | Out-String)

    # 5c. usage errors in the new fields, before anything runs
    $b = New-Batch ('[' + (J 'a' 'good.md') + ',' + (J 'b' 'good.md' ', "depends_on": ["nobody"]') + ']')
    $r = RunB $b
    Check 'an unknown depends_on name is a usage error and nothing runs' ($r.Code -eq 2 -and $r.Out -match 'nobody' -and -not (Get-Order $b).Count) $r.Out
    $b = New-Batch ('[' + (J 'a' 'good.md' ', "depends_on": ["b"]') + ',' + (J 'b' 'good.md' ', "depends_on": ["a"]') + ']')
    $r = RunB $b
    Check 'a depends_on cycle is a usage error and nothing runs' ($r.Code -eq 2 -and $r.Out -match 'cycle' -and -not (Get-Order $b).Count) $r.Out
    foreach ($bad in @(', "priority": "high"', ', "priority": 1.5', ', "max_attempts": 6', ', "max_attempts": 0', ', "max_output_tokens": 16385', ', "max_output_tokens": "big"')) {
        $b = New-Batch ('[' + (J 'a' 'good.md' $bad) + ']')
        $r = RunB $b
        Check "an out-of-range or non-integer field is a usage error ($($bad.Trim(', ')))" ($r.Code -eq 2 -and -not (Get-Order $b).Count) $r.Out
    }
    $r = RunB (New-Batch ('[' + (J 'a' 'good.md') + ']')) @('-Only', 'zz')
    Check '-Only with an unknown name is a usage error' ($r.Code -eq 2 -and $r.Out -match 'zz') $r.Out

    # 5d. tag, max_attempts and max_output_tokens reach delegate.ps1; tag defaults to the item name and tokens to the batch's -MaxOutputTokens
    $b = New-Batch ('[' + (J 't1' 'good.md' ', "tag": "my-tag", "max_attempts": 2, "max_output_tokens": 1234') + ',' + (J 't2' 'good.md') + ']')
    $r = RunB $b
    $lines = @(Get-Content (Join-Path (Split-Path $b) 'order.txt'))
    Check 'tag, max_attempts and max_output_tokens are passed through' ($lines[0] -eq 't1 tag=my-tag attempts=2 tokens=1234') ($lines -join ' | ')
    Check 'without them: tag is the item name, no -MaxAttempts, the batch tokens' ($lines[1] -eq 't2 tag=t2 attempts=0 tokens=8192') ($lines -join ' | ')

    # 5e. the results file is rewritten after every item, through a temporary file
    $b = New-Batch ('[' + (J 's1' 'good.md') + ',' + (J 's2' 'snap.md') + ']')
    $r = RunB $b
    $snap = Join-Path (Split-Path $b) 'snap-batch.results.json'
    $snapRows = if (Test-Path $snap) { @(Get-Content -Raw $snap | ConvertFrom-Json) } else { @() }
    Check 'the results file holds the first item before the second has finished' ($snapRows.Count -eq 1 -and $snapRows[0].name -eq 's1' -and $snapRows[0].status -eq 'accepted') "$(Test-Path $snap) $($r.Out)"
    Check 'no temporary results file is left behind' (-not @(Get-ChildItem (Split-Path $b) -Filter '*.tmp-*').Count)

    # 5f. -Resume skips accepted items whose output still exists; never one whose output is gone; -Force overrides it
    $b = New-Batch ('[' + (J 'r1' 'good.md') + ',' + (J 'r2' 'bad.md') + ']')
    $null = RunB $b
    $r = RunB $b @('-Resume')
    Check '-Resume skips an item accepted earlier and says so' ($r.Out -match 'r1\s+skipped \(accepted earlier\)' -and ((Get-Order $b) -join ',') -eq 'r1,r2,r2' -and $r.Code -eq 1) "$((Get-Order $b) -join ',') $($r.Out)"
    $r = RunB $b @('-Resume')
    Check 'a second -Resume still sees the item as accepted (the accepted row is kept)' ($r.Out -match 'r1\s+skipped \(accepted earlier\)' -and (Get-Results $b)[0].status -eq 'accepted') "$($r.Out)"
    Remove-Item (Join-Path (Split-Path $b) 'out-r1.txt')
    $r = RunB $b @('-Resume')
    Check '-Resume runs an accepted item again when its output file is gone' ($r.Out -match 'r1\s+accepted' -and ((Get-Order $b) -join ',') -eq 'r1,r2,r2,r2,r1,r2') "$((Get-Order $b) -join ',') $($r.Out)"
    $r = RunB $b @('-Resume', '-Force')
    Check '-Force overrides -Resume' ($r.Out -match 'r1\s+accepted' -and $r.Out -notmatch 'skipped \(' -and ((Get-Order $b) -join ',') -eq 'r1,r2,r2,r2,r1,r2,r1,r2') "$((Get-Order $b) -join ',') $($r.Out)"
    $b = New-Batch ('[' + (J 'g1' 'good.md') + ',' + (J 'g2' 'good.md') + ']')
    $null = RunB $b
    $r = RunB $b @('-Resume')
    Check 'a resumed batch with every item accepted earlier exits 0' ($r.Code -eq 0 -and $r.Out -match '2 of 2 accepted' -and ((Get-Order $b) -join ',') -eq 'g1,g2') "$($r.Code) $($r.Out)"

    # 5g. -MaxItems starts at most n items; with -Resume it takes the next unfinished one
    $b = New-Batch ('[' + (J 'm1' 'good.md') + ',' + (J 'm2' 'good.md') + ',' + (J 'm3' 'good.md') + ']')
    $r = RunB $b @('-MaxItems', '1')
    Check '-MaxItems 1 runs one item and says why it stopped' ($r.Code -eq 0 -and ((Get-Order $b) -join ',') -eq 'm1' -and $r.Out -match 'stopping: -MaxItems 1') "$((Get-Order $b) -join ',') $($r.Out)"
    $r = RunB $b @('-Resume', '-MaxItems', '1')
    Check '-Resume -MaxItems 1 runs the next unfinished item' (((Get-Order $b) -join ',') -eq 'm1,m2') "$((Get-Order $b) -join ',') $($r.Out)"

    # 5h. a CANCEL file next to the batch: before the batch, nothing runs; between items, the rest is cancelled
    $b = New-Batch ('[' + (J 'k1' 'good.md') + ',' + (J 'k2' 'good.md') + ']')
    Set-Content (Join-Path (Split-Path $b) 'CANCEL') 'stop'
    $r = RunB $b
    Check 'a CANCEL file before the batch: no item runs, each is cancelled, and it says so' ($r.Code -eq 1 -and -not (Get-Order $b).Count -and $r.Out -match 'k1\s+cancelled' -and $r.Out -match 'k2\s+cancelled' -and $r.Out -match 'CANCEL file is next to the batch') $r.Out
    $b = New-Batch ('[' + (J 'k1' 'cancel.md') + ',' + (J 'k2' 'good.md') + ',' + (J 'k3' 'good.md') + ']')
    $r = RunB $b
    Check 'a CANCEL file created between items stops the batch before the next item' ($r.Code -eq 1 -and ((Get-Order $b) -join ',') -eq 'k1' -and $r.Out -match 'k1\s+accepted' -and $r.Out -match 'k2\s+cancelled' -and $r.Out -match 'k3\s+cancelled' -and $r.Out -match 'cancelled 2') "$((Get-Order $b) -join ',') $($r.Out)"
    Check 'cancelled items are written to the results file' ((((Get-Results $b) | ForEach-Object { $_.status }) -join ',') -eq 'accepted,cancelled,cancelled') ((Get-Results $b) | Out-String)

    # 5i. -DryRun: the plan, no delegate.ps1 call, and the same verifier rules as delegate.ps1
    $b = New-Batch ('[' + (J 'd1' 'good.md') + ',' + (J 'd0' 'good.md' ', "priority": 5, "max_attempts": 2') + ']')
    $r = RunB $b @('-DryRun')
    Check '-DryRun of a runnable batch exits 0 and calls nothing' ($r.Code -eq 0 -and -not (Get-Order $b).Count -and -not (Test-Path ($b -replace '\.json$', '.results.json')) -and $r.Out -match '2 of 2 item\(s\) runnable') $r.Out
    Check '-DryRun prints order, task, verifier folder, output, work folder and caps' ($r.Out -match '1\. d0' -and $r.Out -match '2\. d1' -and $r.Out -match 'task\s+\S*good\.md' -and $r.Out -match 'verifier\s+\S*[\\/]v\s' -and $r.Out -match 'output\s+\S*out-d1\.txt' -and $r.Out -match 'work\s+\S*work-d1' -and $r.Out -match 'max attempts 2, max output tokens 8192') $r.Out
    $b = New-Batch ('[' + (J 'm1' 'nothere.md') + ',' + (J 'ok' 'good.md') + ']')
    $r = RunB $b @('-DryRun')
    Check '-DryRun flags a missing task and exits 1' ($r.Code -eq 1 -and $r.Out -match 'NOT RUNNABLE\s+missing task: nothere\.md' -and $r.Out -match '1 of 2 item\(s\) runnable') $r.Out
    $b = New-Batch '[{ "name": "mv", "task": "good.md", "verify": "v/gone.ps1", "out": "out-mv.txt" }]'
    $r = RunB $b @('-DryRun')
    Check '-DryRun flags a missing verifier' ($r.Code -eq 1 -and $r.Out -match 'NOT RUNNABLE\s+missing verifier: v/gone\.ps1') $r.Out
    $b = New-Batch '[{ "name": "oi", "task": "good.md", "verify": "v/verify.ps1", "out": "v/out-oi.txt" }]'
    $r = RunB $b @('-DryRun')
    Check '-DryRun flags an output file inside the verifier folder' ($r.Code -eq 1 -and $r.Out -match "NOT RUNNABLE\s+the output file is inside the verifier's folder") $r.Out
    $elsewhere = (Join-Path $base 'elsewhere/out-wi.txt') -replace '\\', '/'
    $b = New-Batch ('[{ "name": "wi", "task": "good.md", "verify": "flat.ps1", "out": "' + $elsewhere + '" }]')
    Copy-Item (Join-Path $base 'v/verify.ps1') (Join-Path (Split-Path $b) 'flat.ps1')
    $r = RunB $b @('-DryRun')
    Check '-DryRun flags a work folder inside the verifier folder' ($r.Code -eq 1 -and $r.Out -match "NOT RUNNABLE\s+the work folder is inside the verifier's folder") $r.Out
    $b = New-Batch '[{ "name": "big", "task": "good.md", "verify": "big/verify.ps1", "out": "out-big.txt" }]'
    $bigDir = Join-Path (Split-Path $b) 'big'
    New-Item -ItemType Directory $bigDir | Out-Null
    Copy-Item (Join-Path $base 'v/verify.ps1') (Join-Path $bigDir 'verify.ps1')
    1..500 | ForEach-Object { [IO.File]::WriteAllText((Join-Path $bigDir "f$_.txt"), 'x') }
    $r = RunB $b @('-DryRun')
    Check '-DryRun flags a verifier folder over the 500-file manifest cap' ($r.Code -eq 1 -and $r.Out -match 'NOT RUNNABLE\s+the verifier manifest has more than 500 files') $r.Out
    $b = New-Batch '[{ "name": "huge", "task": "good.md", "verify": "huge/verify.ps1", "out": "out-huge.txt" }]'
    $hugeDir = Join-Path (Split-Path $b) 'huge'
    New-Item -ItemType Directory $hugeDir | Out-Null
    Copy-Item (Join-Path $base 'v/verify.ps1') (Join-Path $hugeDir 'verify.ps1')
    [IO.File]::WriteAllBytes((Join-Path $hugeDir 'blob.bin'), [byte[]]::new(20971521))
    $r = RunB $b @('-DryRun')
    Check '-DryRun flags a verifier folder over the 20 MB manifest cap' ($r.Code -eq 1 -and $r.Out -match 'NOT RUNNABLE\s+the verifier manifest is larger than 20971520 bytes') $r.Out
    $b = New-Batch ('[' + (J 'a' 'good.md' ', "depends_on": ["nobody"]') + ']')
    $r = RunB $b @('-DryRun')
    Check '-DryRun still exits 2 on a usage error' ($r.Code -eq 2) $r.Out
    $example = Join-Path (Split-Path -Parent $Script) 'batch-example/batch.json'
    $o = & pwsh -NoProfile -File $Script -Batch $example -DryRun 2>&1 | Out-String
    Check 'the shipped batch-example passes -DryRun' ($LASTEXITCODE -eq 0 -and $o -match '1 of 1 item\(s\) runnable') $o
}
finally { Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
if ($fail.Count) { exit 1 }
