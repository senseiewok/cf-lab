# Test for review-diff.ps1 with a FAKE model script (passed through -InvokeScript), so no model, GPU or network is used.
# Covers: two samples; the evidence check drops a fabricated quote and keeps a real one; the exit codes 0, 1, 2 and 3;
# "no local worker"; -Think; the weak-evidence warning; and that nothing is written inside the reviewed repository.
param([string] $Script = (Join-Path $PSScriptRoot 'review-diff.ps1'))
$ErrorActionPreference = 'Stop'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('review-diff-test-' + [guid]::NewGuid().ToString('N'))
$repo = Join-Path $tmp 'repo'
$stubs = Join-Path $tmp 'stubs'
New-Item -ItemType Directory $repo, $stubs | Out-Null
$fail = @(); $n = 0
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }
# A stub model script: writes the arguments it got to args.txt beside itself, then prints the canned replies.
function New-Stub([string] $name, [string[]] $replies, [int] $code = 0) {
    $dir = Join-Path $stubs $name; New-Item -ItemType Directory $dir | Out-Null
    $body = @("Set-Content -LiteralPath (Join-Path `$PSScriptRoot 'args.txt') -Value (`$args -join ' ')")
    for ($i = 0; $i -lt $replies.Count; $i++) {
        $lit = $replies[$i] -replace "'", "''"
        if ($replies.Count -gt 1) { $body += "'===== sample $($i + 1) of $($replies.Count) ====='" }
        $body += "'$lit'"
    }
    $body += "exit $code"
    $path = Join-Path $dir 'stub.ps1'; Set-Content -LiteralPath $path -Value $body -Encoding utf8
    return $path
}
function Run([string[]] $a) {
    if ($a -notcontains '-OutDir') { $a += @('-OutDir', (Join-Path $tmp ('out-' + [guid]::NewGuid().ToString('N')))) }  # keep every run's files under $tmp
    $o = & pwsh -NoProfile -File $Script @a 2>&1
    @{ Code = $LASTEXITCODE; Out = ($o | Out-String); Last = (@($o | ForEach-Object { "$_" } | Where-Object { $_.Trim() }) | Select-Object -Last 1) }
}
function Get-RepoState { (& git -C $repo status --porcelain=v1 --untracked-files=all --ignored 2>$null) -join "`n" }
$saved = @{ m = $env:LOCAL_WORKER_MODEL; p = $env:LOCAL_WORKER_PROFILE }
try {
    Remove-Item Env:LOCAL_WORKER_MODEL, Env:LOCAL_WORKER_PROFILE -ErrorAction SilentlyContinue
    $env:GIT_AUTHOR_NAME = 't'; $env:GIT_AUTHOR_EMAIL = 't@example.invalid'; $env:GIT_COMMITTER_NAME = 't'; $env:GIT_COMMITTER_EMAIL = 't@example.invalid'
    & git -C $repo init -q 2>&1 | Out-Null
    Set-Content (Join-Path $repo 'base.txt') 'base' -Encoding utf8
    & git -C $repo add base.txt 2>&1 | Out-Null; & git -C $repo commit -q -m base 2>&1 | Out-Null
    Set-Content (Join-Path $repo 'run.ps1') @('$name = $args[0]', 'cmd /c "del $name"', 'Write-Host done') -Encoding utf8
    & git -C $repo add run.ps1 2>&1 | Out-Null

    $real = '{"findings":[{"severity":"high","file":"run.ps1","line":2,"quote":"cmd /c \"del $name\"","problem":"The file name is put into a shell command unquoted.","fix":"Use Remove-Item -LiteralPath.","how_to_verify":"Pass a name with an ampersand."}],"checked_but_fine":[]}'
    $fake = '{"findings":[{"severity":"high","file":"run.ps1","line":3,"quote":"Invoke-Expression $payload","problem":"Runs a payload.","fix":"Remove it.","how_to_verify":"Read line 3."},{"severity":"low","file":"run.ps1","line":2,"quote":"cmd /c \"del $name\"","problem":"An ampersand in the name runs a second command.","fix":"Quote it.","how_to_verify":"Pass a name with a space."}],"checked_but_fine":["line 1"]}'
    $empty = '{"findings":[],"checked_but_fine":["run.ps1"]}'
    $before = Get-RepoState

    # two samples; a fabricated quote dropped; the real one kept and merged across samples; exit 1
    $two = New-Stub 'two' @($real, $fake)
    $out1 = Join-Path $tmp 'out1'
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', $two, '-OutDir', $out1)
    $stubArgs = Get-Content -Raw (Join-Path (Split-Path $two) 'args.txt')
    Check 'two fast samples are asked for (-Samples 2 -ThinkMode off) with the findings schema' ($stubArgs -match '-Samples 2' -and $stubArgs -match '-ThinkMode off' -and $stubArgs -match 'findings\.schema\.json' -and $stubArgs -match '-Model stub-model') $stubArgs
    Check 'each sample gets its own counts' ($r.Out -match 'sample 1: 1 finding\(s\), 1 kept by the evidence check, 0 dropped' -and $r.Out -match 'sample 2: 2 finding\(s\), 1 kept by the evidence check, 1 dropped') $r.Out
    Check 'the fabricated quote is dropped and never printed as a survivor' ($r.Out -match 'DROPPED quote not found #1' -and $r.Out -notmatch 'quote: Invoke-Expression') $r.Out
    Check 'the real quote survives once, merged over both samples' ($r.Out -match 'survivors: 1 ' -and $r.Out -match 'run\.ps1, diff line \+2 \(sample 1,2\)' -and $r.Out -match 'quote: cmd /c "del \$name"' -and $r.Out -match 'problem: The file name is put' -and $r.Out -match 'problem: An ampersand in the name') $r.Out
    Check 'survivors exit 1 and the last line counts them' ($r.Code -eq 1 -and $r.Last -eq 'SURVIVORS: 1') "code=$($r.Code) last=$($r.Last)"
    Check 'coverage is printed from the manifest' ($r.Out -match 'covered: 1 of 1 files in the diff; packet \d+ characters' -and $r.Out -match 'included: run\.ps1') $r.Out
    Check 'the output folder holds the packet, the replies and the summary' ((Test-Path (Join-Path $out1 'packet.md')) -and (Test-Path (Join-Path $out1 'checked-2.json')) -and (Test-Path (Join-Path $out1 'review.json')))

    # a quote copied from the instructions around the diff is not evidence
    $instr = '{"findings":[{"severity":"medium","file":"run.ps1","line":1,"quote":"An empty findings list is a valid answer.","problem":"x","fix":"y","how_to_verify":"z"}],"checked_but_fine":[]}'
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', (New-Stub 'instr' @($instr, $empty)))
    Check 'a quote from the prompt text (outside the diff) is dropped' ($r.Code -eq 0 -and $r.Out -match 'sample 1: 1 finding\(s\), 0 kept' -and $r.Last -eq 'SURVIVORS: 0') $r.Out

    # clean: exit 0; short diff, so no weak-evidence line
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', (New-Stub 'clean' @($empty, $empty)))
    Check 'no survivors exits 0' ($r.Code -eq 0 -and $r.Last -eq 'SURVIVORS: 0') $r.Out
    Check 'a short diff with no survivors gets no weak-evidence line' ($r.Out -notmatch 'weak evidence') $r.Out
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', (New-Stub 'clean2' @($empty, $empty)), '-LargeDiffChars', '10')
    Check 'a long diff with no survivors gets the weak-evidence line' ($r.Out -match 'A clean pass by a fast local model on a long diff is weak evidence; read the diff yourself') $r.Out

    # -Think: one sample, thinking on
    $th = New-Stub 'think' @($real)
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', $th, '-Think')
    $thArgs = Get-Content -Raw (Join-Path (Split-Path $th) 'args.txt')
    Check '-Think asks for one sample with thinking on' ($r.Code -eq 1 -and $thArgs -match '-Samples 1' -and $thArgs -match '-ThinkMode on') "$thArgs $($r.Out)"

    # no local worker: exit 3, the model script is not run
    $nw = New-Stub 'noworker' @($real, $real)
    $r = Run @('-RepoPath', $repo, '-Staged', '-InvokeScript', $nw)
    Check 'no model, no LOCAL_WORKER_MODEL, no profile: exit 3 and nothing reviewed' ($r.Code -eq 3 -and $r.Out -match 'no local worker configured: nothing reviewed' -and -not (Test-Path (Join-Path (Split-Path $nw) 'args.txt'))) $r.Out
    $env:LOCAL_WORKER_MODEL = 'stub-from-env'
    $ev = New-Stub 'fromenv' @($empty, $empty)
    $r = Run @('-RepoPath', $repo, '-Staged', '-InvokeScript', $ev)
    Check 'LOCAL_WORKER_MODEL is used when -Model is not given' ($r.Code -eq 0 -and (Get-Content -Raw (Join-Path (Split-Path $ev) 'args.txt')) -match '-Model stub-from-env') $r.Out
    Remove-Item Env:LOCAL_WORKER_MODEL

    # usage and setup errors: exit 2
    $r = Run @('-RepoPath', $repo, '-Model', 'stub-model', '-InvokeScript', $two)
    Check 'no diff source is a usage error (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'exactly one of') $r.Out
    $r = Run @('-RepoPath', $repo, '-Staged', '-Base', 'HEAD', '-Model', 'stub-model', '-InvokeScript', $two)
    Check 'two diff sources are a usage error (exit 2)' ($r.Code -eq 2) $r.Out
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', (New-Stub 'broken' @('model server not reachable') 1))
    Check 'a failed model call is an error (exit 2), not a clean review' ($r.Code -eq 2 -and $r.Out -match 'the model call failed' -and $r.Out -notmatch 'SURVIVORS') $r.Out
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', (New-Stub 'onesample' @($real)))
    Check 'a missing sample is an error (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'expected 2 sample') $r.Out
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', $two, '-OutDir', (Join-Path $repo 'review-out'))
    Check 'an output folder inside the repository is refused (exit 2)' ($r.Code -eq 2 -and -not (Test-Path (Join-Path $repo 'review-out'))) $r.Out

    Check 'nothing was written inside the reviewed repository by the staged reviews' ((Get-RepoState) -eq $before) "before=[$before] after=[$(Get-RepoState)]"

    # an empty staged diff: nothing to review, the model is not called
    & git -C $repo commit -q -m run 2>&1 | Out-Null
    $before = Get-RepoState
    $em = New-Stub 'emptydiff' @($real, $real)
    $r = Run @('-RepoPath', $repo, '-Staged', '-Model', 'stub-model', '-InvokeScript', $em)
    Check 'an empty diff is not sent to the model and exits 0' ($r.Code -eq 0 -and $r.Out -match 'nothing to review' -and -not (Test-Path (Join-Path (Split-Path $em) 'args.txt'))) $r.Out

    # a saved diff file, and the challenger handoff (no approval: nothing is sent)
    $df = Join-Path $tmp 'change.diff'
    Set-Content -LiteralPath $df -Value @('diff --git a/x.sh b/x.sh', 'new file mode 100644', '--- /dev/null', '+++ b/x.sh', '@@ -0,0 +1,1 @@', '+rm -rf $DIR/') -Encoding utf8
    $r = Run @('-DiffFile', $df, '-Model', 'stub-model', '-InvokeScript', (New-Stub 'difffile' @($empty, $empty)), '-ChallengerHandoff')
    Check 'a saved diff file is reviewed' ($r.Code -eq 0 -and $r.Out -match 'included: x\.sh') $r.Out
    Check '-ChallengerHandoff writes the packet and stops at needs-review' ($r.Out -match 'challenger handoff: needs-review, sha256 [0-9A-F]{64}' -and $r.Out -match 'nothing was sent') $r.Out

    Check 'nothing was written inside the reviewed repository' ((Get-RepoState) -eq $before) "before=[$before] after=[$(Get-RepoState)]"
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
    if ($saved.m) { $env:LOCAL_WORKER_MODEL = $saved.m } else { Remove-Item Env:LOCAL_WORKER_MODEL -ErrorAction SilentlyContinue }
    if ($saved.p) { $env:LOCAL_WORKER_PROFILE = $saved.p } else { Remove-Item Env:LOCAL_WORKER_PROFILE -ErrorAction SilentlyContinue }
}
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
