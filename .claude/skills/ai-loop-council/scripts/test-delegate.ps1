# Test for delegate.ps1 with a stub standing in for the local worker. No model, Ollama or network.
param([string] $Script = (Join-Path $PSScriptRoot 'delegate.ps1'))
$ErrorActionPreference = 'Stop'
$base = Join-Path ([IO.Path]::GetTempPath()) ('delegate-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $base | Out-Null
$fail = @(); $n = 0
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }

# The stub worker: reply-<n>.txt from $env:STUB_DIR, and a log of how it was called.
Set-Content (Join-Path $base 'stub.ps1') @'
param([string] $PromptFile, [string] $ProfileFile, [string] $Model, [string] $SystemFile, [int] $NumCtx, [int] $MaxOutputTokens, [string] $ThinkMode, [string] $ThinkingFile, [string] $LogFile, [string] $Tag, [int] $Attempt, [string] $Mode)
$d = $env:STUB_DIR
$cf = Join-Path $d 'count.txt'; $i = 1 + $(if (Test-Path $cf) { [int](Get-Content $cf) } else { 0 }); Set-Content $cf $i
Add-Content (Join-Path $d 'calls.txt') ("call=$i profile=$ProfileFile model=$Model think=$ThinkMode maxout=$MaxOutputTokens thinkingfile=$ThinkingFile logfile=$LogFile numctx=$NumCtx attempt=$Attempt mode=$Mode tag=$Tag")
if ($ThinkingFile) { Set-Content $ThinkingFile "stub thinking $i" }
if (Test-Path (Join-Path $d "nolog-$i.txt")) { throw 'connection refused (stub: this call writes no usage line)' }
if ($LogFile) { Add-Content $LogFile ('{"prompt_tokens":77,"output_tokens":123,"prompt_eval_duration":150000000,"eval_duration":900000000,"thinking_chars":45,"done_reason":"stop","attempt":' + $Attempt + ',"mode":"' + $Mode + '"}') }
if ($LogFile -and (Test-Path (Join-Path $d "cancel-after-$i.txt"))) { New-Item -ItemType File -Force (Join-Path (Split-Path $LogFile) 'CANCEL') | Out-Null }
Copy-Item $PromptFile (Join-Path $d "seen-prompt-$i.md")
$r = Join-Path $d "reply-$i.txt"
$reply = if (Test-Path $r) { Get-Content -Raw $r } else { 'no scripted reply' }
if ($reply.TrimStart().StartsWith('@@CAP@@')) {
    $tf = Join-Path $d "think-$i.txt"; if ($ThinkingFile -and (Test-Path $tf)) { Copy-Item $tf $ThinkingFile -Force }
    throw 'Generated-token limit reached (16384 output tokens; reasoning tokens count). Use a fast profile or raise -MaxOutputTokens.'
}
$reply
'@ -Encoding utf8
Set-Content (Join-Path $base 'verify.ps1') @'
param([string] $Script)
$t = Get-Content -Raw $Script
if ($t -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL candidate does not say GOOD'; Write-Output '0/1 passed'; exit 1
'@ -Encoding utf8
Set-Content (Join-Path $base 'verify-count.ps1') @'
param([string] $Script)
$lines = @(Get-Content $Script)
if (($lines -join "`n") -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
foreach ($l in $lines) { Write-Output "FAIL $l" }
exit 1
'@ -Encoding utf8
Set-Content (Join-Path $base 'verify-echo.ps1') @'
param([string] $Script)
$first = (Get-Content $Script | Select-Object -First 1)
if ($first -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output "FAIL expected GOOD, got $first"; exit 1
'@ -Encoding utf8
Set-Content (Join-Path $base 'task.md') 'write a thing' -Encoding utf8

function NewCase([string[]] $replies) {
    $d = Join-Path $base ('case-' + [guid]::NewGuid().ToString('N').Substring(0, 6)); New-Item -ItemType Directory $d | Out-Null
    for ($i = 0; $i -lt $replies.Count; $i++) { Set-Content (Join-Path $d "reply-$($i + 1).txt") $replies[$i] -Encoding utf8 }
    return $d
}
function Delegate([string] $d, [string[]] $extra = @(), [string] $verifier = 'verify.ps1') {
    $env:STUB_DIR = $d
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task.md') -Verify (Join-Path $base $verifier) -OutFile (Join-Path $d 'out.ps1') -InvokeScript (Join-Path $base 'stub.ps1') -WorkDir (Join-Path $d 'work') -OutcomeLog (Join-Path $d 'outcomes.jsonl') -UsageLog (Join-Path $d 'central.jsonl') @extra 2>&1 | Out-String
    return @{ Code = $LASTEXITCODE; Out = $o; Dir = $d }
}
$fence = '```'
try {
    # 1. accepted on the first attempt
    $c = NewCase @("here:`n$fence`nGOOD thing`n$fence`n")
    $r = Delegate $c
    Check 'accepted on attempt 1 and exits 0' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED on attempt 1') $r.Out
    Check 'the candidate file holds the extracted text' ((Get-Content -Raw (Join-Path $c 'out.ps1')) -match 'GOOD thing')
    Check 'the work files are outside the output folder logic (work dir used)' (Test-Path (Join-Path $c 'work\prompt-1.md'))

    # 2. first wrong, verifier feedback reaches attempt 2, accepted there
    $c = NewCase @("$fence`nnope`n$fence", "$fence`nGOOD now`n$fence")
    $r = Delegate $c
    Check 'accepted on attempt 2' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED on attempt 2') $r.Out
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md')
    Check 'attempt 2 carries the verifier failure line and the previous attempt' ($p2 -match 'FAIL candidate does not say GOOD' -and $p2 -match 'nope') $p2

    # 3. REGRESSION: a script that itself contains triple backticks must not be cut at the inner fence
    # The code contains a line that is exactly three backticks (as a script that writes Markdown would),
    # so stopping at the FIRST closing fence truncates it. Mid-line backticks alone would not.
    $inner = $fence + "`n`$x = 'GOOD'`n" + $fence + "`nmiddle`nWrite-Output done`n" + $fence
    $c = NewCase @($inner)
    $r = Delegate $c
    $out = Get-Content -Raw (Join-Path $c 'out.ps1')
    Check 'inner backticks do not truncate the extracted code' ($r.Code -eq 0 -and $out -match 'Write-Output done') "out=$out"

    # 4. never accepted: exit 1, no exception, after MaxAttempts calls
    $c = NewCase @("$fence`nbad1`n$fence", "$fence`nbad2`n$fence", "$fence`nbad3`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3')
    $calls = @(Get-Content (Join-Path $c 'calls.txt')).Count
    Check 'a worker that never passes: exit 1 after exactly 3 calls' ($r.Code -eq 1 -and $r.Out -match 'NOT ACCEPTED' -and $calls -eq 3) "calls=$calls $($r.Out)"

    # 5. reply with no fence is a failed attempt, not a crash
    $c = NewCase @('just prose, no code block', "$fence`nGOOD`n$fence")
    $r = Delegate $c
    Check 'a reply without a fenced block counts as a failed attempt and the next one can succeed' ($r.Code -eq 0 -and $r.Out -match 'no fenced block') $r.Out

    # 6. thinking profile only on the last of three attempts, fast profile before
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-FastProfile', 'FAST.json', '-ThinkingProfile', 'THINK.json')
    $log = Get-Content (Join-Path $c 'calls.txt')
    Check 'attempts 1 and 2 use the fast profile, attempt 3 the thinking profile' ($log[0] -match 'FAST.json' -and $log[1] -match 'FAST.json' -and $log[2] -match 'THINK.json') ($log -join ' | ')

    # 7. -NoFence: the whole reply is the candidate
    $c = NewCase @('GOOD plain text, no fence')
    $r = Delegate $c @('-NoFence')
    Check '-NoFence takes the reply as is' ($r.Code -eq 0) $r.Out

    # 8. cloud-only when nothing is configured (no stub override)
    foreach ($k in 'LOCAL_WORKER_MODEL', 'LOCAL_WORKER_PROFILE', 'LOCAL_WORKER_THINKING_PROFILE') { [Environment]::SetEnvironmentVariable($k, $null, 'Process') }
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task.md') -Verify (Join-Path $base 'verify.ps1') -OutFile (Join-Path $base 'x.ps1') 2>&1 | Out-String
    Check 'nothing configured: exit 2, says cloud-only, calls no model' ($LASTEXITCODE -eq 2 -and $o -match 'cloud-only') $o

    # 9. refuses to write inside .git
    $c = NewCase @("$fence`nGOOD`n$fence")
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task.md') -Verify (Join-Path $base 'verify.ps1') -OutFile (Join-Path $c '.git\hook.ps1') -InvokeScript (Join-Path $base 'stub.ps1') 2>&1 | Out-String
    Check 'refuses an output path inside .git' ($LASTEXITCODE -eq 2 -and $o -match '\.git') $o

    # 10. T-0059: a model-only setup (no profile) sends think off for the fast attempts and think on for the last one
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-Model', 'only-a-model')
    $log = Get-Content (Join-Path $c 'calls.txt')
    Check 'model only: attempts 1 and 2 send think=off, attempt 3 sends think=on' ($log[0] -match 'think=off' -and $log[1] -match 'think=off' -and $log[2] -match 'think=on') ($log -join ' | ')

    # 11. a fast profile governs the fast attempts (no override sent); with no thinking profile the last attempt still thinks
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-FastProfile', 'FAST.json')
    $log = Get-Content (Join-Path $c 'calls.txt')
    Check 'fast profile only: attempts 1 and 2 send no think override, attempt 3 sends think=on' ($log[0] -match 'think= ' -and $log[1] -match 'think= ' -and $log[2] -match 'think=on') ($log -join ' | ')

    # 12. with both profiles the profiles decide thinking on every attempt
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-FastProfile', 'FAST.json', '-ThinkingProfile', 'THINK.json')
    $log = Get-Content (Join-Path $c 'calls.txt')
    Check 'both profiles: no think override on any attempt' (@($log | Where-Object { $_ -match 'think= ' }).Count -eq 3) ($log -join ' | ')

    # 13. the token budget is a parameter that reaches the worker; the default stays 8192; an absurd value is refused
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxOutputTokens', '4000')
    Check '-MaxOutputTokens 4000 reaches the worker call' (@(Get-Content (Join-Path $c 'calls.txt'))[0] -match 'maxout=4000') @(Get-Content (Join-Path $c 'calls.txt'))[0]
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Delegate $c
    Check 'the default budget is 8192' (@(Get-Content (Join-Path $c 'calls.txt'))[0] -match 'maxout=8192') @(Get-Content (Join-Path $c 'calls.txt'))[0]
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxOutputTokens', '99999')
    Check 'an absurd -MaxOutputTokens is refused before any model call' ($r.Code -ne 0 -and -not (Test-Path (Join-Path $c 'calls.txt'))) $r.Out

    # 14. evaluation aids: each attempt gets its own thinking file in the work folder, a usage log of its own, and the attempt line shows tokens
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c
    $log = @(Get-Content (Join-Path $c 'calls.txt'))
    Check 'each attempt is told to save its thinking in the work folder' ($log[0] -match 'thinkingfile=.*work.thinking-1.txt' -and $log[1] -match 'thinkingfile=.*work.thinking-2.txt') ($log -join ' | ')
    Check 'the thinking text is kept per attempt' ((Test-Path (Join-Path $c 'work\thinking-1.txt')) -and (Test-Path (Join-Path $c 'work\thinking-2.txt')))
    Check 'the delegation uses its own usage log' ($log[0] -match 'logfile=.*work.usage.jsonl') ($log -join ' | ')
    Check 'the attempt line shows output tokens and thinking size' ($r.Out -match '123 tokens, thinking 45 chars') $r.Out

    # 14b. V2-06a: -NumCtx is passed only when the caller sets it, so a profile's own num_ctx (65,536) is not overridden by a hidden 32,768
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Delegate $c @('-FastProfile', 'FAST.json')
    Check 'no -NumCtx from the caller: none is passed to the worker (numctx stays unset)' (@(Get-Content (Join-Path $c 'calls.txt'))[0] -match 'numctx=0 ') @(Get-Content (Join-Path $c 'calls.txt'))[0]
    $c = NewCase @("$fence`nGOOD`n$fence")
    $r = Delegate $c @('-FastProfile', 'FAST.json', '-NumCtx', '4096')
    Check 'an explicit -NumCtx 4096 reaches the worker' (@(Get-Content (Join-Path $c 'calls.txt'))[0] -match 'numctx=4096 ') @(Get-Content (Join-Path $c 'calls.txt'))[0]

    # 14c. V2-06a: every attempt is written to the work-folder log AND to the central usage log, with equal token counts, and says which attempt and mode it was
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-Tag', 'unit-test')
    $wl = @(Get-Content (Join-Path $c 'work\usage.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
    $cl = @(Get-Content (Join-Path $c 'central.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
    Check 'one central line per attempt (3), as in the work-folder log' ($wl.Count -eq 3 -and $cl.Count -eq 3) "work=$($wl.Count) central=$($cl.Count)"
    Check 'the central log carries the same token counts as the work-folder log' ($cl.Count -eq 3 -and (@(0..2 | Where-Object { $cl[$_].output_tokens -ne $wl[$_].output_tokens }).Count -eq 0)) ($cl | ConvertTo-Json -Compress)
    Check 'the central lines say attempt 1, 2, 3 and mode default, default, thinking' ($cl.Count -eq 3 -and ($cl.attempt -join ',') -eq '1,2,3' -and ($cl.mode -join ',') -eq 'default,default,thinking') ($cl | ConvertTo-Json -Compress)
    Check 'the caller passes attempt and mode to the worker, so the work-folder log has them too' ($wl.Count -eq 3 -and ($wl.attempt -join ',') -eq '1,2,3' -and ($wl.mode -join ',') -eq 'default,default,thinking') ($wl | ConvertTo-Json -Compress)
    Check 'the central lines carry the tag' ($cl.Count -eq 3 -and @($cl | Where-Object { $_.tag -ne 'unit-test' }).Count -eq 0) ($cl | ConvertTo-Json -Compress)
    $centralText = Get-Content -Raw (Join-Path $c 'central.jsonl')
    Check 'the central log holds no prompt text, reply text or path' ($centralText -notmatch 'write a thing|GOOD|bad|work\\|case-') $centralText
    # a capped call still logged its usage (the worker logs before it checks the reply), so it counts once and the next attempt counts once
    $c = NewCase @('@@CAP@@', "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2')
    $cl = @(Get-Content (Join-Path $c 'central.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
    Check 'a capped attempt and the attempt after it each have one central line (attempts 1 and 2)' ($cl.Count -eq 2 -and ($cl.attempt -join ',') -eq '1,2') ($cl | ConvertTo-Json -Compress)
    # a call that fails before it writes any usage line adds nothing: the previous attempt's line must not be copied a second time
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    New-Item -ItemType File (Join-Path $c 'nolog-2.txt') | Out-Null
    $r = Delegate $c @('-MaxAttempts', '2')
    $cl = @(Get-Content (Join-Path $c 'central.jsonl') | ForEach-Object { $_ | ConvertFrom-Json })
    Check 'a call with no usage line adds no central line (only attempt 1 is there, no stale copy)' ($cl.Count -eq 1 -and $cl[0].attempt -eq 1) ($cl | ConvertTo-Json -Compress)

    # 14d. parallel delegations share one central log: no line may be lost to a file-lock collision (16 parallel runs lost 1 line before the fix)
    Set-Content (Join-Path $base 'stub-fast.ps1') @'
param([string] $PromptFile, [string] $ProfileFile, [string] $Model, [string] $SystemFile, [int] $NumCtx, [int] $MaxOutputTokens, [string] $ThinkMode, [string] $ThinkingFile, [string] $LogFile, [string] $Tag, [int] $Attempt, [string] $Mode)
if ($LogFile) { Add-Content $LogFile ('{"output_tokens":1,"attempt":' + $Attempt + ',"mode":"' + $Mode + '"}') }
'```' + "`nGOOD`n" + '```'
'@ -Encoding utf8
    $par = Join-Path $base 'parallel'; New-Item -ItemType Directory $par | Out-Null
    $parN = 24
    $procs = 1..$parN | ForEach-Object { Start-Process pwsh -ArgumentList '-NoProfile', '-File', $Script, '-TaskFile', (Join-Path $base 'task.md'), '-Verify', (Join-Path $base 'verify.ps1'), '-OutFile', (Join-Path $par "out$_.ps1"), '-InvokeScript', (Join-Path $base 'stub-fast.ps1'), '-WorkDir', (Join-Path $par "w$_"), '-OutcomeLog', (Join-Path $par "o$_.jsonl"), '-UsageLog', (Join-Path $par 'central.jsonl') -PassThru -WindowStyle Hidden }
    $procs | Wait-Process -Timeout 180
    $got = if (Test-Path (Join-Path $par 'central.jsonl')) { @(Get-Content (Join-Path $par 'central.jsonl')).Count } else { 0 }
    Check "$parN parallel delegations write $parN central usage lines (none lost to a lock collision)" ($got -eq $parN) "got $got"
    $bad = @(Get-Content (Join-Path $par 'central.jsonl') | Where-Object { try { $null = $_ | ConvertFrom-Json; $false } catch { $true } })
    Check 'every central line is whole, valid JSON (no interleaved writes)' ($bad.Count -eq 0) "$($bad.Count) bad lines"

    # 15. SALVAGE: the thinking attempt hits the token cap, but its thinking text holds a complete answer that passes the verifier
    $five = { param($w) (1..5 | ForEach-Object { "$w line $_" }) -join "`n" }
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') ("some reasoning`n$fence`n" + (& $five 'GOOD') + "`n$fence`nmore reasoning") -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3')
    $got = Get-Content -Raw (Join-Path $c 'out.ps1')
    Check 'a complete answer inside a capped thinking trace is salvaged when the verifier passes it' ($r.Code -eq 0 -and $r.Out -match 'SALVAGED on attempt 3' -and $got -match 'GOOD line 5') $r.Out
    # 15b. nothing in the thinking passes: not accepted, and the cap is named
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') ("$fence`n" + (& $five 'nope') + "`n$fence") -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3')
    Check 'a capped attempt whose thinking holds no passing answer is not accepted' ($r.Code -eq 1 -and $r.Out -notmatch 'SALVAGED' -and $r.Out -match 'token limit') $r.Out
    # 15c. several blocks: the last is tried first, but an earlier one that passes is still found; a short block is never tried
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') ("$fence`n" + (& $five 'GOOD') + "`n$fence`ntext`n$fence`n" + (& $five 'nope') + "`n$fence`n$fence`nGOOD`n$fence") -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3')
    Check 'an earlier passing block is found after a later failing one; a one-line block is ignored' ($r.Code -eq 0 -and $r.Out -match 'SALVAGED') $r.Out
    # 15d. a cap on a NON-final attempt is just a failed attempt (no salvage from a fast attempt that has no thinking)
    $c = NewCase @('@@CAP@@', "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2')
    Check 'a capped fast attempt with no thinking text is a failed attempt and the next can succeed' ($r.Code -eq 0 -and $r.Out -match 'ACCEPTED on attempt 2') $r.Out
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md')
    Check 'the next prompt tells the worker to write the answer first' ($p2 -match 'Write the complete answer FIRST') $p2

    # 16. BEST-SO-FAR ANCHOR: a later attempt that is worse is set aside; the next prompt shows the best one and says so
    $c = NewCase @("$fence`na1$fence", "$fence`nb1`nb2`nb3`n$fence", "$fence`nGOOD`n$fence")
    $c = NewCase @("$fence`na1`n$fence", "$fence`nb1`nb2`nb3`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3') 'verify-count.ps1'
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md'); $p3 = Get-Content -Raw (Join-Path $c 'seen-prompt-3.md')
    Check 'attempt 2 is shown the previous attempt' ($p2 -match 'Your previous attempt' -and $p2 -match 'a1') $p2
    Check 'attempt 3 is shown the BEST attempt (attempt 1), not the worse attempt 2, with a regression note' ($p3 -match 'best attempt so far \(attempt 1' -and $p3 -match 'MORE than the 1 of your best attempt' -and $p3 -match 'a1' -and $p3 -notmatch 'b3') $p3

    # 17. BOUNDED FEEDBACK: at most 12 failure lines, long lines cut from the end, and the number left out is stated
    $long = 'y' * 500
    $c = NewCase @(("$fence`n" + ((1..29 | ForEach-Object { "row$_" }) -join "`n") + "`n$long`n$fence"), "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2') 'verify-count.ps1'
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md')
    $failLines = @(($p2 -split "`r?`n") | Where-Object { $_ -match '^FAIL ' })
    Check 'at most 12 failure lines are fed back and the rest are counted' ($failLines.Count -le 12 -and $p2 -match '\(18 more failure lines omitted\)') "lines=$($failLines.Count)"
    $c = NewCase @(("$fence`n" + $long + "`n$fence"), "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2') 'verify-count.ps1'
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md')
    $fl = @(($p2 -split "`r?`n") | Where-Object { $_ -match '^FAIL ' })[0]
    Check 'a very long failure line is cut from the end, keeping its start' ($fl.StartsWith('FAIL ' + ('y' * 100)) -and $fl.Length -le 310 -and $fl.EndsWith('...')) "len=$($fl.Length)"

    # 18. IDENTICAL RESUBMISSION: named, not silently repeated; the next prompt says the feedback was not applied
    $c = NewCase @("$fence`nsame`n$fence", "$fence`nsame`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3')
    $p3 = Get-Content -Raw (Join-Path $c 'seen-prompt-3.md')
    Check 'an identical resubmission is named' ($r.Out -match 'attempt 2 \(default, [^)]*\): identical to the previous attempt') $r.Out
    Check 'the next prompt says the answer was identical and the feedback was not applied' ($p3 -match 'IDENTICAL' -and $r.Code -eq 0) $p3

    # 15e. the LAST block is tried first (only three are tried): four blocks, only the last passes
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') ("$fence`n" + (& $five 'n1') + "`n$fence`n$fence`n" + (& $five 'n2') + "`n$fence`n$fence`n" + (& $five 'n3') + "`n$fence`n$fence`n" + (& $five 'GOOD') + "`n$fence") -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3')
    Check 'blocks are tried last first, so a passing LAST block is found among four' ($r.Code -eq 0 -and $r.Out -match 'SALVAGED') $r.Out
    # 15f. a block shorter than 5 lines is never tried, even if it would pass
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') "$fence`nGOOD`nGOOD`n$fence" -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3')
    Check 'a block shorter than 5 lines is not tried' ($r.Code -eq 1 -and $r.Out -notmatch 'SALVAGED') $r.Out

    # 19. a candidate that does not parse never becomes the best attempt
    $c = NewCase @("$fence`np1`np2`n$fence", "$fence`nif (`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3') 'verify-count.ps1'
    $p3 = Get-Content -Raw (Join-Path $c 'seen-prompt-3.md')
    Check 'attempt 3 is anchored on the best verified attempt, not on the one that did not parse' ($p3 -match 'best attempt so far \(attempt 1' -and $p3 -match 'p1' -and $p3 -notmatch 'if \(') $p3

    # 15g. only the last THREE blocks are tried: five blocks where only the FIRST passes is not salvaged
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') ("$fence`n" + (& $five 'GOOD') + "`n$fence`n$fence`n" + (& $five 'n1') + "`n$fence`n$fence`n" + (& $five 'n2') + "`n$fence`n$fence`n" + (& $five 'n3') + "`n$fence`n$fence`n" + (& $five 'n4') + "`n$fence") -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3')
    Check 'at most three blocks are tried: a passing fifth-from-last block is not salvaged' ($r.Code -eq 1 -and $r.Out -notmatch 'SALVAGED') $r.Out

    # 20. VERIFIER SUSPECT: the same single check failing on two different candidates is named; different failures, or a pass, are not
    $c = NewCase @("$fence`nnope1`n$fence", "$fence`nnope2`n$fence", "$fence`nnope3`n$fence")
    $r = Delegate $c
    Check 'the same single failure on different candidates is named as a verifier suspect, and the loop goes on' ($r.Out -match 'VERIFIER SUSPECT' -and $r.Out -match 'attempt 2: VERIFIER SUSPECT' -and $r.Out -match 'NOT ACCEPTED' -and $r.Out -match 'check that expectation by hand') $r.Out
    $c = NewCase @("$fence`nnope1`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c
    Check 'a pass on attempt 2 prints no suspect line' ($r.Code -eq 0 -and $r.Out -notmatch 'SUSPECT') $r.Out
    $c = NewCase @("$fence`na`nb`n$fence", "$fence`na`nc`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @() 'verify-count.ps1'
    Check 'several failure lines are not a suspect' ($r.Out -notmatch 'SUSPECT') $r.Out
    $c = NewCase @("$fence`nnope1`n$fence", "$fence`nnope2`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @() 'verify-echo.ps1'
    Check 'two different single failures are not a suspect' ($r.Code -eq 0 -and $r.Out -notmatch 'SUSPECT') $r.Out
    $c = NewCase @("$fence`nnope1`n$fence", "$fence`nnope1`n$fence", "$fence`nnope3`n$fence")
    $r = Delegate $c
    Check 'an identical resubmission is not counted as a second failure of the same check' ($r.Out -match 'identical to the previous attempt' -and $r.Out -notmatch 'attempt 2: VERIFIER SUSPECT') $r.Out

    # 16. the thinking attempt gets the full output budget unless -MaxOutputTokens was given; fast attempts keep the default
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c
    $calls = @(Get-Content (Join-Path $c 'calls.txt'))
    Check 'the thinking attempt defaults to 16384 output tokens and the fast ones to 8192' ($calls[0] -match 'maxout=8192' -and $calls[1] -match 'maxout=8192' -and $calls[2] -match 'maxout=16384') ($calls -join ' | ')
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxOutputTokens', '5000')
    $calls = @(Get-Content (Join-Path $c 'calls.txt'))
    Check 'an explicit -MaxOutputTokens applies to every attempt, the thinking one included' ($calls[2] -match 'maxout=5000') ($calls -join ' | ')

    # 17. a failed run does not leave a failing draft in a real file
    $c = NewCase @("$fence`nbad1`n$fence", "$fence`nbad2`n$fence", "$fence`nbad3`n$fence")
    Set-Content (Join-Path $c 'out.ps1') 'ORIGINAL CONTENT' -Encoding utf8
    $r = Delegate $c
    Check 'NOT ACCEPTED puts an existing output file back unchanged and keeps the best attempt in the work folder' ($r.Code -eq 1 -and (Get-Content -Raw (Join-Path $c 'out.ps1')) -match 'ORIGINAL CONTENT' -and (Test-Path (Join-Path $c 'work\best-candidate.txt'))) "code=$($r.Code) out.ps1=[$((Get-Content -Raw (Join-Path $c 'out.ps1')).Trim())] best=$(Test-Path (Join-Path $c 'work\best-candidate.txt'))"
    $c = NewCase @("$fence`nbad`nx`ny`n$fence", "$fence`nbad`n$fence", "$fence`nbad`nx`ny`nz`n$fence")
    $r = Delegate $c @() 'verify-count.ps1'
    $held = (Get-Content -Raw (Join-Path $c 'out.ps1')).Trim()
    Check 'with no existing file, the output file holds the BEST failed attempt (fewest failing lines), not the last' ($r.Code -eq 1 -and $held -ceq 'bad') "held=[$held] $($r.Out)"

    # 17b. a candidate that does not compile is never the 'best' attempt, even though the verifier reports it as ONE failing line
    Set-Content (Join-Path $base 'verify-compile.ps1') @'
param([string] $Script)
$lines = @(Get-Content $Script)
if (($lines -join "`n") -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
if (($lines -join "`n") -match 'PROSE') { Write-Output 'FAIL does not compile: SyntaxError'; exit 1 }
foreach ($l in $lines) { Write-Output "FAIL $l" }
exit 1
'@ -Encoding utf8
    $c = NewCase @("$fence`nnear`nmiss`n$fence", "$fence`nPROSE here`n$fence", "$fence`nPROSE again`n$fence")
    $r = Delegate $c @() 'verify-compile.ps1'
    $held = (Get-Content -Raw (Join-Path $c 'out.ps1')).Trim()
    Check 'a non-compiling attempt does not replace a nearly passing one as the best' ($r.Code -eq 1 -and $held -match 'near' -and $held -notmatch 'PROSE') "held=[$held]"

    # 19. the thinking attempt is told from the start to write the answer first (thinking attempts ran out of tokens with the answer already in the trace)
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c
    $p3 = Get-Content -Raw (Join-Path $c 'seen-prompt-3.md')
    $p1 = Get-Content -Raw (Join-Path $c 'seen-prompt-1.md')
    Check 'the thinking attempt carries the answer-first instruction and the fast ones do not' ($p3 -match 'Write the complete answer FIRST' -and $p1 -notmatch 'Write the complete answer FIRST') $p3

    # 20. identical failure lines reach the worker once, with a count, so one cause does not hide the others
    Set-Content (Join-Path $base 'verify-many.ps1') @'
param([string] $Script)
if ((Get-Content -Raw $Script) -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
1..5 | ForEach-Object { Write-Output 'FAIL page /x: title length 85 not in 20..70' }
Write-Output 'FAIL page /y: the one other cause'
exit 1
'@ -Encoding utf8
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @() 'verify-many.ps1'
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md')
    $dupes = ([regex]::Matches($p2, 'title length 85 not in 20\.\.70')).Count
    Check 'identical failure lines are shown once with a count and the other cause is still shown' ($dupes -eq 1 -and $p2 -match '\(x5\)' -and $p2 -match 'the one other cause') $p2

    # 18. the outcome line: one JSON line per run with the tag, outcome and attempts; the tag reaches the worker only when given
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-Tag', 'unit-test-tag')
    $line = (Get-Content (Join-Path $c 'outcomes.jsonl') | Select-Object -Last 1) | ConvertFrom-Json
    Check 'the outcome line records tag, task file name, outcome and attempts' ($line.tag -eq 'unit-test-tag' -and $line.outcome -eq 'accepted' -and $line.attempts -eq 2 -and $line.task -eq 'task.md' -and $line.output_tokens -eq 246) ($line | ConvertTo-Json -Compress)
    Check 'the tag is passed to the worker call' (@(Get-Content (Join-Path $c 'calls.txt'))[0] -match 'tag=unit-test-tag')
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nbad`n$fence", "$fence`nbad`n$fence")
    $r = Delegate $c
    $line = (Get-Content (Join-Path $c 'outcomes.jsonl') | Select-Object -Last 1) | ConvertFrom-Json
    Check 'a failed run is logged as not accepted with no tag, and the worker is not given a tag' ($line.outcome -eq 'not accepted' -and $null -eq $line.tag -and @(Get-Content (Join-Path $c 'calls.txt'))[0] -match 'tag=$')

    # ---- V2-01: one row per attempt, a label set by this script's code, and a terminal state on the run row ----
    function Get-Hash8([string] $s) { return ([BitConverter]::ToString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($s))) -replace '-', '').ToLowerInvariant().Substring(0, 8) }
    function Get-HashFull([string] $s) { return ([BitConverter]::ToString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($s))) -replace '-', '').ToLowerInvariant() }
    function Get-Rows([string] $d) { return @(Get-Content (Join-Path $d 'outcomes.jsonl') | ForEach-Object { $_ | ConvertFrom-Json }) }
    function Get-Attempts([string] $d) { return @(Get-Rows $d | Where-Object { $_.kind -eq 'attempt' }) }
    function Get-RunRow([string] $d) { return @(Get-Rows $d | Where-Object { $_.kind -eq 'run' })[-1] }
    $labelRe = '^[A-Z]+(:[0-9a-f]{8})?$'
    $states = @('accepted', 'accepted-after-verifier-edit', 'blocked', 'budget exhausted', 'failed', 'cancelled')
    $allStates = @()

    # 21. a pass on attempt 2: two attempt rows, then the run row LAST, sharing one run id; the pass has no label; fields are counts, hashes and codes
    $c = NewCase @("$fence`nnope`n$fence", "$fence`nGOOD thing`n$fence")
    $r = Delegate $c @('-Tag', 'rows')
    $rows = Get-Rows $c; $at = Get-Attempts $c; $run = Get-RunRow $c
    Check 'two attempts: two attempt rows, then one run row, which is the LAST line' ($at.Count -eq 2 -and $rows.Count -eq 3 -and $rows[-1].kind -eq 'run') ($rows | ConvertTo-Json -Compress)
    Check 'the attempt rows and the run row share one run id' ($run.run -match '^[0-9a-f]{12}$' -and @($at | Where-Object { $_.run -ne $run.run }).Count -eq 0) ($rows | ConvertTo-Json -Compress)
    Check 'attempt rows carry n, mode, tokens, seconds and done_reason' ($at[0].n -eq 1 -and $at[1].n -eq 2 -and $at[0].mode -eq 'default' -and $at[0].prompt_tokens -eq 77 -and $at[0].output_tokens -eq 123 -and $at[0].done_reason -eq 'stop' -and $null -ne $at[0].seconds -and $at[0].seconds -ge 0 -and $at[0].tag -eq 'rows') ($at | ConvertTo-Json -Compress)
    Check 'attempt rows carry the prompt-eval and eval durations (nanoseconds, as Ollama returns them), so a report needs no second log' ($at[0].prompt_eval_duration -eq 150000000 -and $at[0].eval_duration -eq 900000000) ($at[0] | ConvertTo-Json -Compress)
    Check 'the passing attempt has no label and the SHA-256 of its candidate' ($null -eq $at[1].label -and $at[1].candidate_sha256 -ceq (Get-HashFull 'GOOD thing')) ($at[1] | ConvertTo-Json -Compress)
    Check 'the run row keeps its old fields and gains the state' ($run.outcome -eq 'accepted' -and $run.attempts -eq 2 -and $run.state -eq 'accepted' -and $run.tag -eq 'rows') ($run | ConvertTo-Json -Compress)
    $allStates += $run.state

    # 22. WRONG: the verifier said no. The label carries an 8-hex hash of the FIRST failing line, which the test computes itself
    Check 'a failing attempt is WRONG plus the hash of its first failing line, and carries its candidate hash' ($at[0].label -ceq ('WRONG:' + (Get-Hash8 'FAIL candidate does not say GOOD')) -and $at[0].candidate_sha256 -ceq (Get-HashFull 'nope')) ($at[0] | ConvertTo-Json -Compress)

    # 23. NOFENCE, IDENT, CAP, FAILED, each exactly as named, with no hash
    $c = NewCase @('just prose, no code block', "$fence`nsame`n$fence", "$fence`nsame`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3'); $at = Get-Attempts $c
    Check 'a reply with no fenced block is NOFENCE and has no candidate hash' ($at[0].label -ceq 'NOFENCE' -and $null -eq $at[0].candidate_sha256) ($at | ConvertTo-Json -Compress)
    Check 'a candidate byte-equal to the previous one is IDENT (and still carries its hash); the first of them was WRONG' ($at[1].label -match '^WRONG:' -and $at[2].label -ceq 'IDENT' -and $at[2].candidate_sha256 -ceq $at[1].candidate_sha256) ($at | ConvertTo-Json -Compress)
    $allStates += (Get-RunRow $c).state
    $c = NewCase @('@@CAP@@', "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2'); $at = Get-Attempts $c
    Check 'a token cap with no salvageable block is CAP, has no candidate, and the next attempt can pass' ($at[0].label -ceq 'CAP' -and $null -eq $at[0].candidate_sha256 -and $null -eq $at[1].label -and $r.Code -eq 0) ($at | ConvertTo-Json -Compress)
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    New-Item -ItemType File (Join-Path $c 'nolog-1.txt') | Out-Null
    $r = Delegate $c @('-MaxAttempts', '2'); $at = Get-Attempts $c
    Check 'a model call that fails (not a token cap) is FAILED, counts as an attempt and has no tokens or durations (null, not zero)' ($at[0].label -ceq 'FAILED' -and $null -eq $at[0].output_tokens -and $null -eq $at[0].prompt_eval_duration -and $null -eq $at[0].candidate_sha256 -and $at.Count -eq 2) ($at | ConvertTo-Json -Compress)

    # 24. PARSE and LINT (a .ps1 output file): a candidate that does not parse, and one that parses but fails lint-powershell.ps1; lint stops before the verifier
    Set-Content (Join-Path $base 'verify-logged.ps1') @'
param([string] $Script)
Add-Content (Join-Path $env:STUB_DIR 'verifier-calls.txt') 'called'
if ((Get-Content -Raw $Script) -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL candidate does not say GOOD'; exit 1
'@ -Encoding utf8
    $c = NewCase @("$fence`nif (`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2') 'verify-logged.ps1'; $at = Get-Attempts $c
    Check 'a candidate that does not parse is PARSE plus a hash, and the verifier is not called for it' ($at[0].label -match '^PARSE:[0-9a-f]{8}$' -and @(Get-Content (Join-Path $c 'verifier-calls.txt')).Count -eq 1) (($at | ConvertTo-Json -Compress) + ' calls=' + (Get-Content (Join-Path $c 'verifier-calls.txt') -ErrorAction SilentlyContinue))
    $c = NewCase @("$fence`nStart-Process -NoProfile foo`n$fence", "$fence`nGOOD`n$fence")
    $r = Delegate $c @('-MaxAttempts', '2') 'verify-logged.ps1'; $at = Get-Attempts $c
    $p2 = Get-Content -Raw (Join-Path $c 'seen-prompt-2.md')
    Check 'a candidate that parses but fails the lint is LINT plus a hash, and the verifier is not called for it' ($at[0].label -match '^LINT:[0-9a-f]{8}$' -and @(Get-Content (Join-Path $c 'verifier-calls.txt')).Count -eq 1) (($at | ConvertTo-Json -Compress) + ' calls=' + (Get-Content (Join-Path $c 'verifier-calls.txt') -ErrorAction SilentlyContinue))
    Check 'the lint lines are the feedback: the rule id and message reach the worker, the file path does not' ($p2 -match 'PSL006' -and $p2 -match 'Start-Process -NoProfile' -and $p2 -notmatch [regex]::Escape($c)) $p2
    Check 'a clean candidate that passes is not slowed into a LINT label' ($at[1].label -eq $null -and $r.Code -eq 0) ($at | ConvertTo-Json -Compress)
    # a LINT candidate ranks 500: worse than a verifier failure with a few failing lines, better than one that does not parse (1000). The output file
    # of a failed run holds the BEST attempt, so it shows the ranking.
    $c = NewCase @("$fence`nif (`n$fence", "$fence`nStart-Process -NoProfile foo`n$fence", "$fence`nif ((`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3') 'verify-count.ps1'
    $held = (Get-Content -Raw (Join-Path $c 'out.ps1')).Trim()
    Check 'ranking: LINT (500) is better than a candidate that does not parse (1000), so it becomes the best attempt' ($r.Code -eq 1 -and $held -match 'Start-Process -NoProfile foo') "held=[$held]"
    $allStates += (Get-RunRow $c).state
    $c = NewCase @("$fence`nStart-Process -NoProfile foo`n$fence", "$fence`na`nb`nc`n$fence", "$fence`nStart-Process -NoProfile bar`n$fence")
    $r = Delegate $c @('-MaxAttempts', '3') 'verify-count.ps1'
    $held = (Get-Content -Raw (Join-Path $c 'out.ps1')).Trim()
    Check 'ranking: a verifier failure with 3 failing lines is better than LINT (500), so it stays the best attempt' ($r.Code -eq 1 -and $held -match '^a' -and $held -notmatch 'Start-Process') "held=[$held]"

    # 25. SUSPECT: the same single failure on two different candidates; the hash is that of the failing line
    $c = NewCase @("$fence`nnope1`n$fence", "$fence`nnope2`n$fence", "$fence`nnope3`n$fence")
    $r = Delegate $c; $at = Get-Attempts $c
    $h = Get-Hash8 'FAIL candidate does not say GOOD'
    Check 'attempt 1 is WRONG; attempts 2 and 3 repeat its single failure on a new candidate, so they are SUSPECT with the same hash' ($at[0].label -ceq "WRONG:$h" -and $at[1].label -ceq "SUSPECT:$h" -and $at[2].label -ceq "SUSPECT:$h") ($at | ConvertTo-Json -Compress)
    Check 'budget spent with verifier failures: state is budget exhausted and the old outcome field still says not accepted' ((Get-RunRow $c).state -eq 'budget exhausted' -and (Get-RunRow $c).outcome -eq 'not accepted' -and $r.Code -eq 1) ((Get-RunRow $c) | ConvertTo-Json -Compress)
    $allStates += (Get-RunRow $c).state

    # 26. every label in every row matches the fixed pattern, over all the runs above
    $every = @(); foreach ($d in Get-ChildItem $base -Directory -Filter 'case-*') { if (Test-Path (Join-Path $d.FullName 'outcomes.jsonl')) { $every += @(Get-Attempts $d.FullName) } }
    $bad = @($every | Where-Object { $null -ne $_.label -and $_.label -cnotmatch $labelRe })
    Check "every label in $($every.Count) attempt rows matches ^[A-Z]+(:[0-9a-f]{8})?$" ($every.Count -gt 20 -and $bad.Count -eq 0) "bad=$($bad.label -join ',')"
    $known = @('PARSE', 'LINT', 'WRONG', 'CAP', 'NOFENCE', 'IDENT', 'SUSPECT', 'FAILED')
    Check 'and every label is one of the eight in the fixed list' (@($every | Where-Object { $null -ne $_.label -and ($_.label -split ':')[0] -cnotin $known }).Count -eq 0) (($every.label | Sort-Object -Unique) -join ',')

    # 27. terminal states: failed (the worker never answered), cancelled before a call, cancelled between attempts, salvaged counts as accepted
    $c = NewCase @("$fence`nbad`n$fence")
    foreach ($i in 1..3) { New-Item -ItemType File (Join-Path $c "nolog-$i.txt") | Out-Null }
    $r = Delegate $c; $run = Get-RunRow $c
    Check 'every call failed: state is failed, every attempt is FAILED, exit 1' ($run.state -eq 'failed' -and @(Get-Attempts $c | Where-Object { $_.label -ceq 'FAILED' }).Count -eq 3 -and $r.Code -eq 1) ($run | ConvertTo-Json -Compress)
    $allStates += $run.state
    $c = NewCase @("$fence`nGOOD`n$fence")
    New-Item -ItemType Directory (Join-Path $c 'work') | Out-Null; New-Item -ItemType File (Join-Path $c 'work\CANCEL') | Out-Null
    $r = Delegate $c; $run = Get-RunRow $c
    Check 'a CANCEL file in the work folder stops the run before any call: state cancelled, no attempt rows, no model call, exit 1' ($run.state -eq 'cancelled' -and $run.attempts -eq 0 -and (Get-Attempts $c).Count -eq 0 -and -not (Test-Path (Join-Path $c 'calls.txt')) -and $r.Code -eq 1 -and $r.Out -match 'CANCELLED') "$($r.Out) $($run | ConvertTo-Json -Compress)"
    $allStates += $run.state
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nGOOD`n$fence")
    New-Item -ItemType File (Join-Path $c 'cancel-after-1.txt') | Out-Null
    Set-Content (Join-Path $c 'out.ps1') 'ORIGINAL CONTENT' -Encoding utf8
    $r = Delegate $c; $run = Get-RunRow $c
    Check 'a CANCEL file that appears during attempt 1 stops the run after it: one attempt row, state cancelled, the original output file is back' ($run.state -eq 'cancelled' -and $run.attempts -eq 1 -and (Get-Attempts $c).Count -eq 1 -and @(Get-Content (Join-Path $c 'calls.txt')).Count -eq 1 -and (Get-Content -Raw (Join-Path $c 'out.ps1')) -match 'ORIGINAL CONTENT') "$($r.Out) $($run | ConvertTo-Json -Compress)"
    $c = NewCase @("$fence`nbad`n$fence", "$fence`nworse`n$fence", '@@CAP@@')
    Set-Content (Join-Path $c 'think-3.txt') ("$fence`n" + (& $five 'GOOD') + "`n$fence") -Encoding utf8
    $r = Delegate $c @('-MaxAttempts', '3'); $run = Get-RunRow $c; $at = Get-Attempts $c
    Check 'a salvaged answer: the old outcome says salvaged, the state says accepted, and attempt 3 is marked salvaged with no label' ($run.outcome -eq 'salvaged' -and $run.state -eq 'accepted' -and $at[2].salvaged -eq $true -and $null -eq $at[2].label) (($run | ConvertTo-Json -Compress) + ' ' + ($at[2] | ConvertTo-Json -Compress))
    $allStates += $run.state
    Check 'across all the runs, every state is one of the six names, and the four reachable ones were each seen' (@($allStates | Where-Object { $_ -cnotin $states }).Count -eq 0 -and (@('accepted', 'budget exhausted', 'failed', 'cancelled') | Where-Object { $_ -cnotin $allStates }).Count -eq 0) ($allStates -join ',')

    # 28. CANARY: a marker in the packet, in a candidate and in verifier output reaches neither log
    $mark = 'CANARYQ7ZX9'
    Set-Content (Join-Path $base 'verify-canary.ps1') @'
param([string] $Script)
if ((Get-Content -Raw $Script) -match 'GOOD') { Write-Output '1/1 passed'; exit 0 }
Write-Output 'FAIL expected CANARYQ7ZX9-from-the-verifier, got something else'; exit 1
'@ -Encoding utf8
    Set-Content (Join-Path $base 'task-canary.md') "write a thing. CANARYQ7ZX9-in-the-packet" -Encoding utf8
    $c = NewCase @("$fence`nbad CANARYQ7ZX9-in-the-candidate`n$fence", "$fence`nbad2 CANARYQ7ZX9-in-the-candidate`n$fence", "$fence`nbad3 CANARYQ7ZX9-in-the-candidate`n$fence")
    $env:STUB_DIR = $c
    $o = & pwsh -NoProfile -File $Script -TaskFile (Join-Path $base 'task-canary.md') -Verify (Join-Path $base 'verify-canary.ps1') -OutFile (Join-Path $c 'out.ps1') -InvokeScript (Join-Path $base 'stub.ps1') -WorkDir (Join-Path $c 'work') -OutcomeLog (Join-Path $c 'outcomes.jsonl') -UsageLog (Join-Path $c 'central.jsonl') -Tag 'canary' 2>&1 | Out-String
    $logs = (Get-Content -Raw (Join-Path $c 'outcomes.jsonl')) + (Get-Content -Raw (Join-Path $c 'central.jsonl'))
    Check 'the canary run really exercised packet, candidate and verifier text (the work folder has the marker)' ((Get-Content -Raw (Join-Path $c 'work\prompt-2.md')) -match $mark -and (Get-Content -Raw (Join-Path $c 'work\reply-1.txt')) -match $mark -and (Get-Content -Raw (Join-Path $c 'work\verifier-last.txt')) -match $mark) $o
    Check 'but the marker is in neither the outcome log nor the central usage log' ($logs -notmatch $mark -and $logs.Length -gt 200) $logs

    # 29. parallel runs share one outcome log: 24 runs write 24 attempt rows and 24 run rows, all whole JSON (the same lost-line hazard as the usage log)
    $par2 = Join-Path $base 'parallel2'; New-Item -ItemType Directory $par2 | Out-Null
    $procs = 1..$parN | ForEach-Object { Start-Process pwsh -ArgumentList '-NoProfile', '-File', $Script, '-TaskFile', (Join-Path $base 'task.md'), '-Verify', (Join-Path $base 'verify.ps1'), '-OutFile', (Join-Path $par2 "out$_.ps1"), '-InvokeScript', (Join-Path $base 'stub-fast.ps1'), '-WorkDir', (Join-Path $par2 "w$_"), '-OutcomeLog', (Join-Path $par2 'outcomes.jsonl'), '-UsageLog', (Join-Path $par2 'central.jsonl') -PassThru -WindowStyle Hidden }
    $procs | Wait-Process -Timeout 180
    $pl = @(Get-Content (Join-Path $par2 'outcomes.jsonl'))
    $pbad = @($pl | Where-Object { try { $null = $_ | ConvertFrom-Json; $false } catch { $true } })
    Check "$parN parallel runs share one outcome log: $($parN * 2) whole lines ($parN attempt rows and $parN run rows)" ($pl.Count -eq $parN * 2 -and $pbad.Count -eq 0 -and @($pl | ForEach-Object { ($_ | ConvertFrom-Json).kind } | Where-Object { $_ -eq 'run' }).Count -eq $parN) "lines=$($pl.Count) bad=$($pbad.Count)"
} finally { Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue; Remove-Item Env:STUB_DIR -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
