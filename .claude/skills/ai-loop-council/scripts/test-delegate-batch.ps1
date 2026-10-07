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
Set-Content (Join-Path $base 'verify.ps1') @'
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
$item = { param($name, $task) "{ `"name`": `"$name`", `"task`": `"$task`", `"verify`": `"verify.ps1`", `"out`": `"out-$name.ps1`" }" }
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
    $r = Run '[{ "name": "a", "task": "good.md", "verify": "verify.ps1" }]'
    Check 'an item without out is a usage error' ($r.Code -eq 2 -and $r.Out -match "missing 'out'") $r.Out
    $r = Run ('[' + (& $item 'dup' 'good.md') + ',' + (& $item 'dup' 'good.md') + ']')
    Check 'duplicate names are a usage error' ($r.Code -eq 2 -and $r.Out -match 'unique') $r.Out
    $r = Run ('[' + (& $item '../evil' 'good.md') + ']')
    Check 'a name with a path separator is a usage error' ($r.Code -eq 2 -and $r.Out -match 'may use only') $r.Out
    $o = & pwsh -NoProfile -File $Script -Batch (Join-Path $base 'nope.json') 2>&1 | Out-String
    Check 'a missing batch file is a usage error' ($LASTEXITCODE -eq 2) $o
}
finally { Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
if ($fail.Count) { exit 1 }
