# Test for review-diff.ps1 with a FAKE model script (passed through -InvokeScript), so no model, GPU or network is used.
# Covers: two samples; the evidence check drops a fabricated quote and keeps a real one; the exit codes 0, 10, 4, 3 and
# 2 (never 1); an unexpected exception fails closed; "no local worker"; cloud model names and a non-loopback
# OLLAMA_HOST or model-script URL are refused; strict sample separators; stderr kept out of the reply; terminal-safe and
# privacy-masked output; -Think; the weak-evidence warning; the output folder (new or empty only, links resolved,
# deleted unless -KeepOutDir); and that nothing is written inside the reviewed repository.
param([string] $Script = (Join-Path $PSScriptRoot 'review-diff.ps1'))
$ErrorActionPreference = 'Stop'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('review-diff-test-' + [guid]::NewGuid().ToString('N'))
$repo = Join-Path $tmp 'repo'
$stubs = Join-Path $tmp 'stubs'
New-Item -ItemType Directory $repo, $stubs | Out-Null
$fail = @(); $n = 0
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }
# A stub model script: writes the arguments it got to args.txt beside itself, then prints the given lines as they are.
function New-Stub([string] $name, [string[]] $lines, [int] $code = 0, [string] $stderr = '') {
    $dir = Join-Path $stubs $name; New-Item -ItemType Directory $dir | Out-Null
    $body = @("Set-Content -LiteralPath (Join-Path `$PSScriptRoot 'args.txt') -Value (`$args -join ' ')")
    if ($stderr) { $body += "[Console]::Error.WriteLine('$($stderr -replace "'", "''")')" }
    foreach ($l in $lines) { $body += "'" + ($l -replace "'", "''") + "'" }
    $body += "exit $code"
    $path = Join-Path $dir 'stub.ps1'; Set-Content -LiteralPath $path -Value $body -Encoding utf8
    return $path
}
function Samples([string[]] $replies) {
    $out = @()
    for ($i = 0; $i -lt $replies.Count; $i++) { $out += "===== sample $($i + 1) of $($replies.Count) ====="; $out += $replies[$i] }
    return $out
}
function Run([string[]] $a) {
    if ($a -notcontains '-OutDir' -and -not ($a | Where-Object { $_ -like '-OutDir:*' })) { $a += "-OutDir:$(Join-Path $tmp ('out-' + [guid]::NewGuid().ToString('N')))" }
    $o = & pwsh -NoProfile -File $Script @a 2>&1
    @{ Code = $LASTEXITCODE; Out = ($o | Out-String); Last = (@($o | ForEach-Object { "$_" } | Where-Object { $_.Trim() }) | Select-Object -Last 1) }
}
function Get-RepoState { (& git -C $repo status --porcelain=v1 --untracked-files=all --ignored 2>$null) -join "`n" }
$saved = @{ m = $env:LOCAL_WORKER_MODEL; p = $env:LOCAL_WORKER_PROFILE; h = $env:OLLAMA_HOST }
try {
    Remove-Item Env:LOCAL_WORKER_MODEL, Env:LOCAL_WORKER_PROFILE, Env:OLLAMA_HOST -ErrorAction SilentlyContinue
    $env:GIT_AUTHOR_NAME = 't'; $env:GIT_AUTHOR_EMAIL = 't@example.invalid'; $env:GIT_COMMITTER_NAME = 't'; $env:GIT_COMMITTER_EMAIL = 't@example.invalid'
    & git -C $repo init -q 2>&1 | Out-Null
    Set-Content (Join-Path $repo 'base.txt') 'base' -Encoding utf8
    & git -C $repo add base.txt 2>&1 | Out-Null; & git -C $repo commit -q -m base 2>&1 | Out-Null
    $tok = 'gh' + 'p_' + ('A1b2' * 9)   # matches the lab's privacy pattern; built at run time so this file holds no token
    Set-Content (Join-Path $repo 'run.ps1') @('$name = $args[0]', 'cmd /c "del $name"', 'Write-Host done', "`$t = '$tok'") -Encoding utf8
    & git -C $repo add run.ps1 2>&1 | Out-Null

    $real = '{"findings":[{"severity":"high","file":"run.ps1","line":2,"quote":"cmd /c \"del $name\"","problem":"The file name is put into a shell command unquoted.","fix":"Use Remove-Item -LiteralPath.","how_to_verify":"Pass a name with an ampersand."}],"checked_but_fine":[]}'
    $fake = '{"findings":[{"severity":"high","file":"run.ps1","line":3,"quote":"Invoke-Expression $payload","problem":"Runs a payload.","fix":"Remove it.","how_to_verify":"Read line 3."},{"severity":"low","file":"run.ps1","line":2,"quote":"cmd /c \"del $name\"","problem":"An ampersand in the name runs a second command.","fix":"Quote it.","how_to_verify":"Pass a name with a space."}],"checked_but_fine":["line 1"]}'
    $empty = '{"findings":[],"checked_but_fine":["run.ps1"]}'
    $before = Get-RepoState

    # two samples; a fabricated quote dropped; the real one kept and merged across samples; exit 10
    $two = New-Stub 'two' (Samples @($real, $fake)) 0 'warning: { not json'
    $out1 = Join-Path $tmp 'out1'
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$two", "-OutDir:$out1", '-KeepOutDir')
    $stubArgs = Get-Content -Raw (Join-Path (Split-Path $two) 'args.txt')
    Check 'two fast samples are asked for with the findings schema, values passed as -Name:value' ($stubArgs -match '-Samples[: ]2' -and $stubArgs -match '-ThinkMode[: ]off' -and $stubArgs -match '-SchemaFile[: ]\S*findings\.schema\.json' -and $stubArgs -match '-Model[: ]stub-model') $stubArgs
    Check 'each sample gets its own counts' ($r.Out -match 'sample 1: 1 finding\(s\), 1 kept by the evidence check, 0 dropped' -and $r.Out -match 'sample 2: 2 finding\(s\), 1 kept by the evidence check, 1 dropped') $r.Out
    Check 'the fabricated quote is dropped and never printed as a survivor' ($r.Out -match 'DROPPED quote not found #1' -and $r.Out -notmatch 'quote: Invoke-Expression') $r.Out
    Check 'the real quote survives once, merged over both samples, with both problems' ($r.Out -match 'survivors: 1 ' -and $r.Out -match 'run\.ps1, diff line \+2 \(sample 1,2\)' -and $r.Out -match 'problem: The file name is put' -and $r.Out -match 'problem: An ampersand in the name') $r.Out
    Check 'survivors exit 10 (never 1) and the last line counts them' ($r.Code -eq 10 -and $r.Last -eq 'SURVIVORS: 1') "code=$($r.Code) last=$($r.Last)"
    Check 'stderr of the model script is kept out of the reply and saved apart' ((Get-Content -Raw (Join-Path $out1 'model-stderr.txt')) -match 'warning: \{ not json') $r.Out
    $rj = Get-Content -Raw (Join-Path $out1 'review.json') | ConvertFrom-Json
    Check 'review.json carries the run id, status, counts and exit code' ($rj.run_id -match '^[0-9a-f]{32}$' -and $rj.status -eq 'reviewed' -and $rj.survivors_count -eq 1 -and $rj.exit_code -eq 10 -and $rj.files_reviewed -eq 1 -and $rj.files_in_diff -eq 1) ($rj | ConvertTo-Json -Depth 4)
    Check 'coverage says reviewed X of Y files, Z not reviewed' ($r.Out -match 'coverage: reviewed 1 of 1 files, 0 not reviewed') $r.Out
    Check '-KeepOutDir keeps the output folder' ((Test-Path (Join-Path $out1 'packet.md')) -and (Test-Path (Join-Path $out1 'checked-2.json')))

    # the output folder is deleted by default
    $out2 = Join-Path $tmp 'out2'
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'del' (Samples @($empty, $empty)))", "-OutDir:$out2")
    Check 'the output folder is deleted at the end unless -KeepOutDir' ($r.Code -eq 0 -and -not (Test-Path $out2)) $r.Out

    # a quote copied from the instructions or a file header is not evidence
    $instr = '{"findings":[{"severity":"medium","file":"run.ps1","line":1,"quote":"An empty findings list is a valid answer.","problem":"x","fix":"y","how_to_verify":"z"},{"severity":"medium","file":"run.ps1","line":1,"quote":"### file: run.ps1","problem":"x","fix":"y","how_to_verify":"z"}],"checked_but_fine":[]}'
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'instr' (Samples @($instr, $empty)))")
    Check 'a quote from the prompt text or a file header is dropped' ($r.Code -eq 0 -and $r.Out -match 'sample 1: 2 finding\(s\), 0 kept' -and $r.Last -eq 'SURVIVORS: 0') $r.Out

    # terminal-safe and masked output (finding 1 and 11)
    $esc = [string][char]27; $ls = [string][char]0x2028; $rlo = [string][char]0x202E; $c1 = [string][char]0x9B
    $nasty = (@{ findings = @(@{ severity = 'low'; file = 'run.ps1'; quote = "`$t = '$tok'"; problem = "bad${esc}[31mred${ls}next${rlo}rev${c1}x`rcr"; fix = 'f'; how_to_verify = 'v' }); checked_but_fine = @() } | ConvertTo-Json -Depth 5 -Compress)
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'nasty' (Samples @($nasty, $empty)))")
    Check 'control, C1, line-separator and bidi characters from the model are printed as ?' ($r.Code -eq 10 -and $r.Out.Contains('bad?[31mred?next?rev?x?cr') -and -not $r.Out.Contains($esc) -and -not $r.Out.Contains($ls) -and -not $r.Out.Contains($rlo)) $r.Out
    Check 'a survivor quote that matches a privacy pattern is masked' ($r.Out -match 'quote: \$t = ''\[masked: secret\]''' -and -not $r.Out.Contains($tok)) $r.Out

    # clean: exit 0; the weak-evidence line only for a long reviewed diff
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'clean' (Samples @($empty, $empty)))")
    Check 'no survivors exits 0 and gets no weak-evidence line on a short diff' ($r.Code -eq 0 -and $r.Last -eq 'SURVIVORS: 0' -and $r.Out -notmatch 'weak evidence') $r.Out
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'clean2' (Samples @($empty, $empty)))", '-LargeDiffChars:10')
    Check 'a long diff with no survivors gets the weak-evidence line' ($r.Out -match 'A clean pass by a fast local model on a long diff is weak evidence; read the diff yourself') $r.Out

    # strict separators (finding 10)
    $sneaky = @('===== sample 1 of 2 =====', $empty, '===== sample 2 of 2 =====', $real, '===== sample 2 of 2 =====', $empty)
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'sneaky' $sneaky)")
    Check 'an extra separator line fails closed (exit 2), it does not change the part count' ($r.Code -eq 2 -and $r.Out -match 'expected exactly 2 in order' -and $r.Out -notmatch 'SURVIVORS') $r.Out
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'onesample' (Samples @($real)))")
    Check 'a missing sample fails closed (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'separator') $r.Out
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'notjson' (Samples @('not json at all', $empty)))")
    Check 'a reply that is not JSON fails closed (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'sample 1 is not a JSON findings reply') $r.Out

    # -Think: one sample, thinking on; a separator then is an error
    $th = New-Stub 'think' @($real)
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$th", '-Think')
    $thArgs = Get-Content -Raw (Join-Path (Split-Path $th) 'args.txt')
    Check '-Think asks for one sample with thinking on' ($r.Code -eq 10 -and $thArgs -match '-Samples[: ]1' -and $thArgs -match '-ThinkMode[: ]on') "$thArgs $($r.Out)"
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'think2' (Samples @($real)))", '-Think')
    Check 'with -Think a separator line fails closed' ($r.Code -eq 2) $r.Out

    # no local worker: exit 3, the model script is not run
    $nw = New-Stub 'noworker' (Samples @($real, $real))
    $r = Run @("-RepoPath:$repo", '-Staged', "-InvokeScript:$nw")
    Check 'no model, no LOCAL_WORKER_MODEL, no profile: exit 3 and nothing reviewed' ($r.Code -eq 3 -and $r.Out -match 'no local worker configured: nothing reviewed' -and -not (Test-Path (Join-Path (Split-Path $nw) 'args.txt'))) $r.Out
    $env:LOCAL_WORKER_MODEL = 'stub-from-env'
    $ev = New-Stub 'fromenv' (Samples @($empty, $empty))
    $r = Run @("-RepoPath:$repo", '-Staged', "-InvokeScript:$ev")
    Check 'LOCAL_WORKER_MODEL is used when -Model is not given' ($r.Code -eq 0 -and (Get-Content -Raw (Join-Path (Split-Path $ev) 'args.txt')) -match '-Model[: ]stub-from-env') $r.Out
    Remove-Item Env:LOCAL_WORKER_MODEL

    # cloud routing refused (finding 3)
    foreach ($bad in 'gpt-oss:120b-cloud', 'qwen3:cloud', 'some-cloud:latest') {
        $cl = New-Stub ('cloud' + [guid]::NewGuid().ToString('N').Substring(0, 6)) (Samples @($empty, $empty))
        $r = Run @("-RepoPath:$repo", '-Staged', "-Model:$bad", "-InvokeScript:$cl")
        Check "a cloud model name is refused before any call ($bad)" ($r.Code -eq 2 -and $r.Out -match 'cloud-routed' -and -not (Test-Path (Join-Path (Split-Path $cl) 'args.txt'))) $r.Out
    }
    $env:OLLAMA_HOST = 'http://remote.example.invalid:11434'
    $oh = New-Stub 'ollamahost' (Samples @($empty, $empty))
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$oh")
    Check 'a non-loopback OLLAMA_HOST is refused before any call' ($r.Code -eq 2 -and $r.Out -match 'OLLAMA_HOST' -and -not (Test-Path (Join-Path (Split-Path $oh) 'args.txt'))) $r.Out
    foreach ($okHost in '127.0.0.1:11434', 'http://localhost:11434', '[::1]:11434') {
        $env:OLLAMA_HOST = $okHost
        $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub ('lh' + [guid]::NewGuid().ToString('N').Substring(0, 6)) (Samples @($empty, $empty)))")
        Check "a loopback OLLAMA_HOST is accepted ($okHost)" ($r.Code -eq 0) $r.Out
    }
    Remove-Item Env:OLLAMA_HOST
    $remoteStub = New-Stub 'remoteurl' (Samples @($empty, $empty))
    Add-Content -LiteralPath $remoteStub -Value '# Invoke-RestMethod -Uri ''https://api.example.invalid/api/chat'''
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$remoteStub")
    Check 'a model script that names a non-loopback URL is refused' ($r.Code -eq 2 -and $r.Out -match 'non-loopback address') $r.Out

    # usage and setup errors: exit 2; an unexpected exception fails closed with exit 2, never 1 (finding 1)
    $r = Run @("-RepoPath:$repo", '-Model:stub-model', "-InvokeScript:$two")
    Check 'no diff source is a usage error (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'exactly one of') $r.Out
    $r = Run @("-RepoPath:$repo", '-Staged', '-Base:HEAD', '-Model:stub-model', "-InvokeScript:$two")
    Check 'two diff sources are a usage error (exit 2)' ($r.Code -eq 2) $r.Out
    $r = Run @('-RepoPath:-C', '-Staged', '-Model:stub-model', "-InvokeScript:$two")
    Check 'a path argument that starts with - is refused (exit 2)' ($r.Code -eq 2 -and $r.Out -match "must not start with '-'") $r.Out
    $badProfile = Join-Path $tmp 'bad-profile.json'; Set-Content -LiteralPath $badProfile -Value '{ not json' -Encoding utf8
    $r = Run @("-RepoPath:$repo", '-Staged', "-ProfileFile:$badProfile", "-InvokeScript:$two")
    Check 'an unexpected exception fails closed with exit 2' ($r.Code -eq 2 -and $r.Out -match 'unexpected failure, nothing reviewed') $r.Out
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$(New-Stub 'broken' @('model server not reachable') 1)")
    Check 'a failed model call is an error (exit 2), not a clean review' ($r.Code -eq 2 -and $r.Out -match 'the model call failed' -and $r.Out -notmatch 'SURVIVORS') $r.Out

    # output folder rules (finding 12)
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$two", "-OutDir:$(Join-Path $repo 'review-out')")
    Check 'an output folder inside the repository is refused (exit 2)' ($r.Code -eq 2 -and -not (Test-Path (Join-Path $repo 'review-out'))) $r.Out
    $junction = Join-Path $tmp 'link-to-repo'
    $linkType = if ($IsWindows) { 'Junction' } else { 'SymbolicLink' }
    New-Item -ItemType $linkType -Path $junction -Target $repo | Out-Null
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$two", "-OutDir:$(Join-Path $junction 'review-out')")
    Check 'an output folder reached through a link into the repository is refused (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'links resolved' -and -not (Test-Path (Join-Path $repo 'review-out'))) $r.Out
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$two", "-OutDir:$junction")
    Check 'an output folder that is itself a link is refused (exit 2)' ($r.Code -eq 2) $r.Out
    Remove-Item -LiteralPath $junction -Force -Recurse:$false
    $used = Join-Path $tmp 'used'; New-Item -ItemType Directory $used | Out-Null; Set-Content (Join-Path $used 'checked-1.json') '{"tool":"check-findings-evidence","results":[],"findings":[]}' -Encoding utf8
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$two", "-OutDir:$used")
    Check 'a non-empty output folder is never reused, so a stale checked file cannot count (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'new or empty') $r.Out

    # nothing reviewed (finding 2): every file excluded -> exit 4, never "0 survivors"
    Set-Content (Join-Path $repo 'package-lock.json') '{"lockfileVersion": 3}' -Encoding utf8
    & git -C $repo commit -q -m run 2>&1 | Out-Null
    & git -C $repo add package-lock.json 2>&1 | Out-Null
    $nr = New-Stub 'nothing' (Samples @($real, $real))
    $out3 = Join-Path $tmp 'out3'
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$nr", "-OutDir:$out3", '-KeepOutDir')
    $rj3 = Get-Content -Raw (Join-Path $out3 'review.json') | ConvertFrom-Json
    Check 'a diff whose files are all excluded is NOTHING REVIEWED (exit 4), the model is not called' ($r.Code -eq 4 -and $r.Last -eq 'NOTHING REVIEWED' -and $r.Out -notmatch 'SURVIVORS' -and $rj3.status -eq 'nothing_reviewed' -and -not (Test-Path (Join-Path (Split-Path $nr) 'args.txt'))) $r.Out
    Check 'nothing written inside the reviewed repository by the staged reviews' ((Get-RepoState) -match '^A  package-lock\.json$' -and ((Get-RepoState) -split "`n").Count -eq 1) "after=[$(Get-RepoState)]"
    & git -C $repo commit -q -m lock 2>&1 | Out-Null
    $before = Get-RepoState

    # an empty staged diff: EMPTY DIFF, exit 0, the model is not called
    $em = New-Stub 'emptydiff' (Samples @($real, $real))
    $r = Run @("-RepoPath:$repo", '-Staged', '-Model:stub-model', "-InvokeScript:$em")
    Check 'an empty diff is not sent to the model and exits 0 with EMPTY DIFF' ($r.Code -eq 0 -and $r.Last -eq 'EMPTY DIFF' -and -not (Test-Path (Join-Path (Split-Path $em) 'args.txt'))) $r.Out

    # a saved diff file, and the challenger handoff (no approval: nothing is sent)
    $df = Join-Path $tmp 'change.diff'
    Set-Content -LiteralPath $df -Value @('diff --git a/x.sh b/x.sh', 'new file mode 100644', '--- /dev/null', '+++ b/x.sh', '@@ -0,0 +1,1 @@', '+rm -rf $DIR/') -Encoding utf8
    $out4 = Join-Path $tmp 'out4'
    $r = Run @("-DiffFile:$df", '-Model:stub-model', "-InvokeScript:$(New-Stub 'difffile' (Samples @($empty, $empty)))", '-ChallengerHandoff', "-OutDir:$out4", '-KeepOutDir')
    $rj4 = Get-Content -Raw (Join-Path $out4 'review.json') | ConvertFrom-Json
    Check 'a saved diff file is reviewed' ($r.Code -eq 0 -and $r.Out -match 'reviewed: x\.sh') $r.Out
    Check '-ChallengerHandoff makes the packet, stops at needs-review and records it in review.json' ($r.Out -match 'challenger handoff: needs-review, sha256 [0-9A-F]{64}' -and $rj4.challenger_handoff.status -eq 'needs-review' -and $rj4.challenger_handoff.sha256 -match '^[0-9A-F]{64}$') $r.Out

    Check 'nothing was written inside the reviewed repository' ((Get-RepoState) -eq $before) "before=[$before] after=[$(Get-RepoState)]"
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
    foreach ($k in @(@('m', 'LOCAL_WORKER_MODEL'), @('p', 'LOCAL_WORKER_PROFILE'), @('h', 'OLLAMA_HOST'))) {
        if ($saved[$k[0]]) { Set-Item -Path "Env:$($k[1])" -Value $saved[$k[0]] } else { Remove-Item "Env:$($k[1])" -ErrorAction SilentlyContinue }
    }
}
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
