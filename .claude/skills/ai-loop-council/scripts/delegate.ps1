<#
.SYNOPSIS
  Delegate one bounded drafting task to the local worker, with an independent verifier and a
  fixed retry shape: up to two attempts in the worker's default mode, then one in thinking mode.

.DESCRIPTION
  The orchestrator writes two things first: a self-contained task packet (-TaskFile) and a
  verifier it trusts (-Verify). This script then loops: send the packet to the local worker,
  extract the code or text from the reply, run the verifier on it, and on failure send the
  worker only the verifier's failing lines plus its previous attempt. It stops at the first
  accepted candidate. A model never marks its own work done: only the verifier does.

  Configuration comes from the single lab env (see .env.example):
    LOCAL_WORKER_MODEL            your preferred local model. Unset (and no profile) = cloud-only:
                                  this script exits 2 and delegates nothing.
    LOCAL_WORKER_PROFILE          optional profile used for attempts 1 and 2
    LOCAL_WORKER_THINKING_PROFILE optional profile used for the last attempt

  Everything it writes goes to a work directory outside the repository (default: a folder under
  the system temp path). It never runs the candidate itself; only your verifier does.

  After an accepted candidate, READ IT. A verifier you wrote cannot cover an edge case you did
  not think of; add the case, watch it fail, then fix.

.PARAMETER Verify
  A .ps1 verifier is run as `pwsh -NoProfile -File <verify> -Script <candidate>`; a .py verifier as
  `python <verify> <candidate>`. Exit 0 accepts. Lines starting with FAIL are fed back.

.PARAMETER MaxOutputTokens
  The most tokens the worker may generate per attempt (default 8192, at most 16384). Reasoning tokens count, so a model that is
  allowed to think can spend the whole budget before it writes the answer; that attempt then fails with a message naming the cap.
  Thinking: an attempt with a profile follows the profile. With no profile, the fast attempts send think off and the last attempt
  sends think on, instead of leaving it to the model's own default.

.NOTES
  Loop behaviour (from the 2026-10-05 review of the local worker's logs): after a failed attempt the worker is shown at most 12 failure lines and
  its BEST attempt so far, not just its latest, so one worse rewrite cannot erase progress; an identical resubmission is named, not re-verified;
  and when a call hits the token cap the complete answers inside its saved thinking text are tried against the verifier (reported as SALVAGED,
  and still to be read with extra care). Each attempt keeps thinking-N.txt and reply-N.txt in the work folder, plus usage.jsonl.

.EXAMPLE
  pwsh -NoProfile -File delegate.ps1 -TaskFile task.md -Verify verify.ps1 -OutFile out/check.ps1

.NOTES
  Exit codes: 0 accepted, 1 not accepted after all attempts or cancelled, 2 not configured or usage error.

.NOTES
  The outcome log (V2-01): one `attempt` row per attempt, then one `run` row, in that order, sharing a run id. Rows hold counts, hashes and codes,
  never prompts, replies or verifier text. An attempt's label is set here, by code, never by the worker:
    NOFENCE  no complete fenced block      IDENT   byte-equal to the previous candidate (not re-verified)
    PARSE:h  a .ps1 does not parse, or the verifier reported a compile error    LINT:h  a .ps1 parses but fails lint-powershell.ps1 (ranked 500)
    WRONG:h  the verifier failed it        SUSPECT:h  the same single check failed on a different candidate
    CAP      token cap with no passing block in the thinking text     FAILED  the model call failed
  h is the first 8 hex digits of the SHA-256 of the first failing line. A passing attempt has no label. The run row's state is accepted,
  budget exhausted, failed (no call was ever answered) or cancelled. blocked and accepted-after-verifier-edit are reserved for the verifier
  hash check (V2-02) and are not produced yet. To cancel a run, create a file named CANCEL in its work folder: it stops before the next call.
  An interrupted process (Ctrl+C) writes no run row, so an attempt row with no run row after it is an interrupted run.
#>
param(
    [Parameter(Mandatory)] [string] $TaskFile,
    [Parameter(Mandatory)] [string] $Verify,
    [Parameter(Mandatory)] [string] $OutFile,
    [string] $SystemFile,
    [ValidateRange(1, 5)] [int] $MaxAttempts = 3,
    [string] $Model = $env:LOCAL_WORKER_MODEL,
    [string] $FastProfile = $env:LOCAL_WORKER_PROFILE,
    [string] $ThinkingProfile = $env:LOCAL_WORKER_THINKING_PROFILE,
    # Passed to the worker only when given: otherwise the profile's own num_ctx applies (the helper's 32,768 only when there is no profile either).
    [int] $NumCtx,
    [ValidateRange(1, 16384)] [int] $MaxOutputTokens = 8192,
    [switch] $NoFence,
    [string] $WorkDir,
    [string] $InvokeScript = (Join-Path $PSScriptRoot 'invoke-local-model.ps1'),
    # A short label for this task, passed to the worker's usage entries and written to the outcome line. Default: LOCAL_WORKER_TAG.
    [string] $Tag = $env:LOCAL_WORKER_TAG,
    # The PowerShell lint run on a .ps1 candidate after it parses and before the verifier. A candidate that fails it is labelled LINT and is not sent to the verifier.
    [string] $LintScript = (Join-Path $PSScriptRoot 'lint-powershell.ps1'),
    # One `attempt` row per attempt and one `run` row per run are appended here (git-ignored .loop-logs by default): tag, task file name, labels, hashes, counts, state, work folder. Never prompts, replies or verifier text.
    [string] $OutcomeLog = $(if ($env:LOCAL_WORKER_OUTCOME_LOG) { $env:LOCAL_WORKER_OUTCOME_LOG } else { Join-Path $PSScriptRoot '../../../../.loop-logs/delegations.jsonl' }),
    # The central usage log (git-ignored .loop-logs by default, the same file invoke-local-model.ps1 writes when called alone): every attempt's usage line is appended here as well as to the work folder's usage.jsonl.
    [string] $UsageLog = $(if ($env:LOCAL_WORKER_USAGE_LOG) { $env:LOCAL_WORKER_USAGE_LOG } else { Join-Path $PSScriptRoot '../../../../.loop-logs/local-model-usage.jsonl' })
)
$ErrorActionPreference = 'Stop'
$default = [bool]($PSBoundParameters.ContainsKey('InvokeScript'))
if (-not $default -and -not $Model -and -not $FastProfile) {
    Write-Host 'error: no local worker is configured, so delegation is cloud-only. Set LOCAL_WORKER_MODEL in the lab .env (your preferred local model) and run this through run-with-env.ps1.'
    exit 2
}
foreach ($f in $TaskFile, $Verify, $InvokeScript) { if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { Write-Host "error: missing file $f"; exit 2 } }
$outFull = [IO.Path]::GetFullPath($OutFile)
if ($outFull -match '[\\/]\.git[\\/]') { Write-Host 'error: refusing to write inside .git'; exit 2 }
if (-not $WorkDir) { $WorkDir = Join-Path ([IO.Path]::GetTempPath()) ('delegate-' + [guid]::NewGuid().ToString('N').Substring(0, 8)) }
New-Item -ItemType Directory -Force -Path $WorkDir, (Split-Path -Parent $outFull) | Out-Null
# An output file that already existed (a real file in a repo) is put back if no attempt is accepted; a failing draft must not replace it.
$hadOut = Test-Path -LiteralPath $outFull -PathType Leaf
if ($hadOut) { Copy-Item -LiteralPath $outFull -Destination (Join-Path $WorkDir 'out-before.txt') -Force }
$runWatch = [Diagnostics.Stopwatch]::StartNew()

$runId = [guid]::NewGuid().ToString('N').Substring(0, 12)
$anyAnswered = $false   # did any model call come back (a token cap counts: the model answered)? Decides failed against budget exhausted.

function Get-Sha256Hex([string] $Text) { return ([BitConverter]::ToString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($Text))) -replace '-', '').ToLowerInvariant() }
# A label is a fixed code, plus (for WRONG, SUSPECT, PARSE, LINT) the first 8 hex digits of the SHA-256 of the first failing line. Never the line itself.
function Get-Label([string] $Code, [string] $FirstFailingLine) { if ($FirstFailingLine) { return "${Code}:" + (Get-Sha256Hex $FirstFailingLine).Substring(0, 8) } else { return $Code } }

# One line in the central outcome log. Never allowed to break a run.
function Add-OutcomeLine([string] $Json) {
    $dir = Split-Path -Parent ([IO.Path]::GetFullPath($OutcomeLog))
    if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    Add-SharedLine $OutcomeLog $Json
}
# One row per attempt, written before the run row: counts, hashes and codes, never text. $Usage is the worker's usage line for this call (or $null when it logged none).
function Write-AttemptRow([int] $N, [string] $Mode, $Label, $Cand, $Usage, [double] $Seconds, [bool] $Salvaged = $false) {
    try {
        $row = [ordered]@{ kind = 'attempt'; ts = (Get-Date).ToUniversalTime().ToString('o'); run = $runId; tag = $(if ($Tag) { $Tag } else { $null }); n = $N; mode = $Mode; label = $Label
            prompt_tokens = $Usage.prompt_tokens; output_tokens = $Usage.output_tokens; seconds = [math]::Round($Seconds, 1); done_reason = $Usage.done_reason
            candidate_sha256 = $(if ($null -ne $Cand) { Get-Sha256Hex ([string]$Cand) } else { $null }) }
        if ($Salvaged) { $row.salvaged = $true }
        Add-OutcomeLine ($row | ConvertTo-Json -Compress)
    } catch { }
}
# One line per run, after its attempt rows, so results can be counted by tag without keeping scratch folders. $Outcome is the older field (accepted, salvaged,
# not accepted, cancelled); $State is the terminal state. Never allowed to break a run.
function Write-Outcome([string] $Outcome, [int] $Attempts, [string] $State) {
    try {
        $tokens = 0
        $ulog = Join-Path $WorkDir 'usage.jsonl'
        if (Test-Path -LiteralPath $ulog) { foreach ($l in Get-Content -LiteralPath $ulog) { try { $tokens += [int](($l | ConvertFrom-Json).output_tokens) } catch { } } }
        $row = [ordered]@{ kind = 'run'; run = $runId; ts = (Get-Date).ToUniversalTime().ToString('o'); tag = $(if ($Tag) { $Tag } else { $null }); task = (Split-Path -Leaf $TaskFile); outcome = $Outcome; state = $State; attempts = $Attempts
            max_attempts = $MaxAttempts; seconds = [int]$runWatch.Elapsed.TotalSeconds; output_tokens = $tokens; work_dir = $WorkDir }
        Add-OutcomeLine ($row | ConvertTo-Json -Compress)
    } catch { }
}

# The work folder's usage.jsonl holds one line per model call that logged. Count them before a call; after it, a NEW line (and only a new one, so a
# call that failed before logging cannot copy the previous attempt's line again) is appended to the central usage log with the attempt, mode and tag.
# Parallel delegations append to one central file, and a line was lost (16 parallel runs gave 15 lines, 48 gave 39). Two causes to avoid:
# Add-Content throws when another writer holds the file, and a shared open with FileMode.Append seeks to the end when it OPENS, so two writers
# that open together overwrite each other with no error. An EXCLUSIVE open makes that seek safe; a sharing violation just means wait and retry.
function Add-SharedLine([string] $Path, [string] $Line) {
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($Line + [Environment]::NewLine)
    for ($try = 1; $try -le 200; $try++) {
        try {
            $fs = [IO.File]::Open($Path, [IO.FileMode]::Append, [IO.FileAccess]::Write, [IO.FileShare]::None)
            try { $fs.Write($bytes, 0, $bytes.Length) } finally { $fs.Dispose() }
            return
        } catch [IO.IOException] { Start-Sleep -Milliseconds (Get-Random -Minimum 5 -Maximum 40) }
    }
    Write-Host "warning: a line could not be written to $(Split-Path -Leaf $Path) (another process kept it locked)"
}
function Get-UsageCount { $u = Join-Path $WorkDir 'usage.jsonl'; if (Test-Path -LiteralPath $u) { return @(Get-Content -LiteralPath $u).Count } else { return 0 } }
# Returns the usage entry it copied (the attempt row reads its token counts from it), or $null when the call logged nothing new.
function Copy-UsageToCentral([int] $Before, [int] $Attempt, [string] $Mode) {
    try {
        $u = Join-Path $WorkDir 'usage.jsonl'
        if (-not (Test-Path -LiteralPath $u)) { return $null }
        $lines = @(Get-Content -LiteralPath $u)
        if ($lines.Count -le $Before) { return $null }
        $e = $lines[-1] | ConvertFrom-Json
        $e | Add-Member -NotePropertyName attempt -NotePropertyValue $Attempt -Force
        $e | Add-Member -NotePropertyName mode -NotePropertyValue $Mode -Force
        if ($Tag) { $e | Add-Member -NotePropertyName tag -NotePropertyValue $Tag -Force }
        $dir = Split-Path -Parent ([IO.Path]::GetFullPath($UsageLog))
        if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Add-SharedLine $UsageLog ($e | ConvertTo-Json -Compress)
        return $e
    } catch { return $null }
}

function Get-Candidate([string] $Reply, [bool] $Plain) {
    if ($Plain) { return $Reply.Trim() }
    # First opening fence to LAST closing fence, so a script that itself contains backticks survives.
    $lines = @($Reply -split "`r?`n"); $open = -1; $close = -1
    for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^\s*```[A-Za-z0-9_+-]*\s*$') { $open = $i; break } }
    if ($open -lt 0) { return $null }
    for ($i = $lines.Count - 1; $i -gt $open; $i--) { if ($lines[$i] -match '^\s*```\s*$') { $close = $i; break } }
    if ($close -le $open) { return $null }
    if ($close -eq $open + 1) { return '' }
    return ($lines[($open + 1)..($close - 1)] -join "`n")
}

# Writes the candidate to the output file, parse-checks .ps1, and runs the independent verifier.
# Returns Ok, Stage, Failing (the FAIL lines) and Summary. Nothing else reaches the pipeline.
function Test-Candidate([string] $Cand) {
    Set-Content -LiteralPath $outFull -Value $Cand -Encoding utf8
    if ($outFull -match '\.ps1$') {
        $errs = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile($outFull, [ref]$null, [ref]$errs)
        if ($errs -and $errs.Count) {
            $msg = 'FAIL does not parse: ' + (($errs | Select-Object -First 4 | ForEach-Object { "line $($_.Extent.StartLineNumber): $($_.Message)" }) -join '; ')
            return [pscustomobject]@{ Ok = $false; Stage = 'parse'; Failing = @($msg); Summary = 'does not parse' }
        }
        # It parses: lint it before the verifier. lint-powershell.ps1 exits 1 on findings; any other exit (2, or it could not run) is no verdict, so the verifier decides.
        if (Test-Path -LiteralPath $LintScript -PathType Leaf) {
            $lo = & pwsh -NoProfile -File $LintScript $outFull 2>&1 | Out-String
            if ($LASTEXITCODE -eq 1) {
                # <path>:<line>:<col>: PSLnnn <message>  ->  FAIL lint line <line>:<col> PSLnnn <message>  (the path is dropped: it is noise to the worker and a private detail)
                $findings = @($lo -split "`r?`n" | Where-Object { $_ -match ':\d+:\d+: PSL\d{3} ' } | ForEach-Object { 'FAIL lint ' + ($_ -replace '^.*?:(\d+):(\d+): (PSL\d{3}) ', 'line $1:$2 $3 ') })
                if (-not $findings.Count) { $findings = @('FAIL lint reported findings') }
                return [pscustomobject]@{ Ok = $false; Stage = 'lint'; Failing = $findings; Summary = 'fails lint' }
            }
        }
    }
    $v = if ($Verify -match '\.py$') { & python $Verify $outFull 2>&1 | Out-String } else { & pwsh -NoProfile -File $Verify -Script $outFull 2>&1 | Out-String }
    $ok = ($LASTEXITCODE -eq 0)
    Set-Content -LiteralPath (Join-Path $WorkDir 'verifier-last.txt') -Value $v -Encoding utf8
    $summary = ($v -split "`r?`n" | Where-Object { $_ -match '\d+\s*/\s*\d+\s+passed' } | Select-Object -Last 1)
    $failing = @($v -split "`r?`n" | Where-Object { $_ -match '^\s*FAIL' })
    if (-not $failing.Count -and -not $ok) { $failing = @(($v -split "`r?`n" | Where-Object { $_ } | Select-Object -Last 15)) }
    $text = if ($summary) { $summary.Trim() } elseif ($ok) { 'verifier passed' } else { 'verifier failed' }
    return [pscustomobject]@{ Ok = $ok; Stage = 'verifier'; Failing = $failing; Summary = $text }
}

# What the worker is shown after a failed attempt: the first 12 failure lines (each cut from the END at 300 characters) and how many were left out.
function Get-Feedback($Failing) {
    $max = 12
    # Identical lines (one per subtest, say) are shown once with a count: twelve copies of one cause used to hide the others.
    $order = @(); $counts = @{}
    foreach ($f in $Failing) { if (-not $counts.ContainsKey($f)) { $order += $f; $counts[$f] = 0 }; $counts[$f]++ }
    $lines = @($order | Select-Object -First $max | ForEach-Object { $t = if ($_.Length -gt 300) { $_.Substring(0, 300) + '...' } else { $_ }; if ($counts[$_] -gt 1) { "$t (x$($counts[$_]))" } else { $t } })
    if ($order.Count -gt $max) { $lines += "($($order.Count - $max) more failure lines omitted)" }
    return ($lines -join "`n")
}

# Complete fenced blocks inside the worker's thinking text, the LAST one first, at most 3, each at least 5 lines long.
function Get-ThinkingBlocks([string] $Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return @() }
    $lines = @(Get-Content -LiteralPath $Path); $blocks = @(); $i = 0
    while ($i -lt $lines.Count) {
        if ($lines[$i] -match '^\s*```[A-Za-z0-9_+-]*\s*$') {
            $j = $i + 1
            while ($j -lt $lines.Count -and $lines[$j] -notmatch '^\s*```\s*$') { $j++ }
            if ($j -lt $lines.Count -and ($j - $i - 1) -ge 5) { $blocks += , (($lines[($i + 1)..($j - 1)]) -join "`n") }
            $i = $j + 1
        } else { $i++ }
    }
    [array]::Reverse($blocks)
    return @($blocks | Select-Object -First 3)
}

# Called when no attempt was accepted: the output file is put back as it was, or, if it did not exist, holds the BEST failed attempt (fewest failing checks), not merely the last.
function Restore-OutFile {
    if ($hadOut) { Copy-Item -LiteralPath (Join-Path $WorkDir 'out-before.txt') -Destination $outFull -Force }
    elseif ($best) { Set-Content -LiteralPath $outFull -Value $best.Cand -Encoding utf8 }
    if ($best) { Set-Content -LiteralPath (Join-Path $WorkDir 'best-candidate.txt') -Value $best.Cand -Encoding utf8 }
}

$task = Get-Content -Raw -LiteralPath $TaskFile
# A thinking attempt can spend its whole budget before it writes the answer (seen at the 8192 default): unless -MaxOutputTokens was given, it gets the maximum.
$thinkBudget = if ($PSBoundParameters.ContainsKey('MaxOutputTokens')) { $MaxOutputTokens } else { 16384 }
$feedback = ''   # for an attempt that produced no candidate to verify
$best = $null    # the best failed candidate so far: Cand, Failing, Count, Attempt (the anchor for repair)
$last = $null    # the previous candidate text, to catch an identical resubmission
$note = ''       # one extra sentence for the next prompt: regression, identical answer
$prevKey = $null # the single failing line of the previous attempt, for the verifier-suspect hint
$suspect = $false
for ($n = 1; $n -le $MaxAttempts; $n++) {
    # A CANCEL file in the work folder stops the run before the next call is paid. The output file is put back as it was, or holds the best attempt so far.
    if (Test-Path -LiteralPath (Join-Path $WorkDir 'CANCEL')) {
        Restore-OutFile
        Write-Outcome 'cancelled' ($n - 1) 'cancelled'
        Write-Host "CANCELLED before attempt ${n}: a CANCEL file is in the work folder, so no further call was made. Work dir: $WorkDir"
        exit 1
    }
    $thinking = ($n -eq $MaxAttempts -and $MaxAttempts -ge 3)
    $mode = if ($thinking) { 'thinking' } else { 'default' }
    $prompt = $task
    if ($n -gt 1) {
        if ($best) {
            $which = if ($best.Attempt -eq $n - 1) { 'previous attempt' } else { "best attempt so far (attempt $($best.Attempt); a later attempt did worse and was set aside)" }
            $prompt += "`n`n--- Attempt $($n - 1) failed the independent verifier. Fix only what failed and return the full result again.$note`nVerifier output (failures only):`n$(Get-Feedback $best.Failing)`n`nYour ${which}:`n``````text`n$($best.Cand)`n``````n"
        } else { $prompt += "`n`n--- Attempt $($n - 1) failed: $feedback$note" }
    }
    # A thinking attempt can spend its whole budget before it writes the answer (seen at the default and at 16,384): ask for the answer first, from the start.
    if ($thinking) { $prompt += "`n`n--- Write the complete answer FIRST, in one fenced block, briefly. Do not re-verify it at length: the independent verifier will." }
    $pf = Join-Path $WorkDir "prompt-$n.md"; Set-Content -LiteralPath $pf -Value $prompt -Encoding utf8
    $params = @{ PromptFile = $pf; MaxOutputTokens = $(if ($thinking) { $thinkBudget } else { $MaxOutputTokens }); Attempt = $n; Mode = $mode }
    if ($PSBoundParameters.ContainsKey('NumCtx')) { $params.NumCtx = $NumCtx }
    if ($Tag) { $params.Tag = $Tag }
    $profile = if ($thinking -and $ThinkingProfile) { $ThinkingProfile } elseif ($FastProfile) { $FastProfile } else { $null }
    if ($profile) { $params.ProfileFile = $profile }
    # Without a profile the model's own thinking default applies, and a thinking model can spend the whole token budget before it writes
    # the answer. So: the last attempt thinks unless a thinking profile says otherwise; a model-only setup gets thinking off before that.
    if ($thinking -and -not $ThinkingProfile) { $params.ThinkMode = 'on' } elseif (-not $profile) { $params.ThinkMode = 'off' }
    if ($Model) { $params.Model = $Model }
    # Evaluation aids, kept in the work folder: the worker's thinking text and a usage log of its own.
    $params.ThinkingFile = Join-Path $WorkDir "thinking-$n.txt"
    $params.LogFile = Join-Path $WorkDir 'usage.jsonl'
    if ($SystemFile) { $params.SystemFile = $SystemFile }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $usageBefore = Get-UsageCount
    try { $reply = (& $InvokeScript @params | Out-String) }
    catch {
        $callUsage = Copy-UsageToCentral $usageBefore $n $mode
        $msg = $_.Exception.Message
        Write-Host "attempt $n ($mode): model call failed: $msg"
        if ($msg -match 'Generated-token limit reached') {
            $anyAnswered = $true   # the model did answer; it ran out of tokens
            # A thinking model may have written a complete answer inside its thinking before it ran out of tokens (seen 2026-10-05:
            # 50 KB of thinking, a passing program on lines 669-852, cut off before the answer). Try those blocks, last first; only the
            # independent verifier can accept one.
            foreach ($blk in @(Get-ThinkingBlocks $params.ThinkingFile)) {
                $r = Test-Candidate $blk
                if ($r.Ok) {
                    Write-Host "SALVAGED on attempt $n ($mode): the call hit the token cap, but a complete answer inside its thinking text passed the verifier -> $outFull"
                    Write-Host "  It was never returned as an answer: read it with extra care before you rely on it. Work dir: $WorkDir"
                    Write-AttemptRow $n $mode $null $blk $callUsage $sw.Elapsed.TotalSeconds $true
                    Write-Outcome 'salvaged' $n 'accepted'
                    exit 0
                }
            }
            $feedback = 'The call ran out of output tokens while thinking and returned no answer. Write the complete answer FIRST, briefly; do not re-verify it at length.'
            Write-AttemptRow $n $mode 'CAP' $null $callUsage $sw.Elapsed.TotalSeconds
        } else {
            $feedback = 'The model call failed.'
            Write-AttemptRow $n $mode 'FAILED' $null $callUsage $sw.Elapsed.TotalSeconds
        }
        $note = ''
        continue
    }
    $sw.Stop()
    $anyAnswered = $true
    $callUsage = Copy-UsageToCentral $usageBefore $n $mode
    $callSeconds = $sw.Elapsed.TotalSeconds
    $usage = ''
    $ulog = Join-Path $WorkDir 'usage.jsonl'
    if (Test-Path -LiteralPath $ulog) {
        try { $u = (Get-Content -LiteralPath $ulog -Tail 1) | ConvertFrom-Json; $usage = ", $($u.output_tokens) tokens, thinking $($u.thinking_chars) chars" } catch { $usage = '' }
    }
    $secs = "$([int]$sw.Elapsed.TotalSeconds)s$usage"
    Set-Content -LiteralPath (Join-Path $WorkDir "reply-$n.txt") -Value $reply -Encoding utf8
    $cand = Get-Candidate $reply ([bool]$NoFence)
    if ($null -eq $cand) {
        $feedback = 'The reply contained no complete fenced block.'
        $note = ' Your last reply had no complete fenced block; return the whole result in ONE fenced block.'
        Write-AttemptRow $n $mode 'NOFENCE' $null $callUsage $callSeconds
        Write-Host "attempt $n ($mode, $secs): no fenced block"; continue
    }
    if ($null -ne $last -and $cand -ceq $last) {
        $note = ' Your last answer was IDENTICAL to the one before it, so the feedback was not applied. Change the specific thing named in the first failing line below.'
        Write-AttemptRow $n $mode 'IDENT' $cand $callUsage $callSeconds
        Write-Host "attempt $n ($mode, $secs): identical to the previous attempt; the feedback did not change the answer"
        continue
    }
    $last = $cand
    $r = Test-Candidate $cand
    Write-Host "attempt $n ($mode, $secs): $($r.Summary)"
    if ($r.Ok) {
        Write-AttemptRow $n $mode $null $cand $callUsage $callSeconds
        Write-Host "ACCEPTED on attempt $n -> $outFull  (read it before you rely on it; work dir: $WorkDir)"; Write-Outcome 'accepted' $n 'accepted'; exit 0
    }
    # A candidate that does not parse or compile is the WORST outcome, even when the verifier reports it as a single failing line (a prose reply once counted as 'better' than a nearly passing script).
    # One that parses but fails the lint ranks 500: worse than any realistic count of failing checks, better than one that does not parse.
    $isParse = ($r.Stage -eq 'parse') -or ($r.Stage -ne 'lint' -and @($r.Failing | Where-Object { $_ -match 'does not compile|SyntaxError|IndentationError|does not parse' }).Count -gt 0)
    $count = if ($isParse) { 1000 } elseif ($r.Stage -eq 'lint') { 500 } else { $r.Failing.Count }
    # One check failing, with the same message, on two DIFFERENT candidates: more often the expectation is wrong than the worker (seen three
    # times on 2026-10-05). Say so; do not stop, because a thinking attempt may still pass if the verifier is right.
    $key = if ($r.Stage -eq 'verifier' -and $r.Failing.Count -eq 1) { [string]$r.Failing[0] } else { $null }
    $suspectNow = $false
    if ($key -and $null -ne $prevKey -and $key -ceq $prevKey) {
        $suspect = $true; $suspectNow = $true
        Write-Host "attempt ${n}: VERIFIER SUSPECT: the same single check failed on two different candidates ($key). Read that check against the spec by hand before blaming the worker."
    }
    $prevKey = $key
    # The attempt's label, from the code path that decided it. The hash is of the first failing line; the line itself is never logged.
    $firstFail = ([string]($r.Failing | Select-Object -First 1)).Trim()
    $label = if ($suspectNow) { Get-Label 'SUSPECT' $firstFail } elseif ($isParse) { Get-Label 'PARSE' $firstFail } elseif ($r.Stage -eq 'lint') { Get-Label 'LINT' $firstFail } else { Get-Label 'WRONG' $firstFail }
    Write-AttemptRow $n $mode $label $cand $callUsage $callSeconds
    $note = ''
    if ($best -and $count -gt $best.Count) { $note = " Your latest attempt had $count failing checks, MORE than the $($best.Count) of your best attempt, so it was set aside: change only the part the failures below name." }
    if (-not $best -or $count -le $best.Count) { $best = [pscustomobject]@{ Cand = $cand; Failing = $r.Failing; Count = $count; Attempt = $n } }
}
Restore-OutFile
# budget exhausted: the model answered at least once and no attempt passed. failed: no call was ever answered (every one errored).
Write-Outcome 'not accepted' $MaxAttempts $(if ($anyAnswered) { 'budget exhausted' } else { 'failed' })
Write-Host "NOT ACCEPTED after $MaxAttempts attempt(s). Last verifier output: $(Join-Path $WorkDir 'verifier-last.txt')"
if ($hadOut) { Write-Host "Your existing output file was put back unchanged. The best failed attempt is in $(Join-Path $WorkDir 'best-candidate.txt')." }
elseif ($best) { Write-Host "The output file holds the BEST failed attempt (attempt $($best.Attempt), $($best.Count) failing checks), not a finished result." }
if ($suspect) { Write-Host 'The same single check failed on different candidates: check that expectation by hand first; the verifier may be what is wrong.' }
exit 1
