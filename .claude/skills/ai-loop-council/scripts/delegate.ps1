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
  pwsh -NoProfile -File delegate.ps1 -TaskFile task.md -Verify verifier/verify.ps1 -OutFile out/check.ps1

.NOTES
  Exit codes: 0 accepted, 1 not accepted after all attempts or cancelled, 2 not configured, usage error or a verifier refused before the first call, 3 blocked.

.NOTES
  The verifier is frozen (V2-02). Before the first model call the verifier file, every file under its own folder and every -VerifierFiles path (a file or a
  folder) are copied into the work folder, keeping their layout, and the copy is hashed. The verifier runs only from that copy, with the copy's folder as its
  working folder. It is compared with the live files before every verifier run, after it, and immediately before a result is written as accepted: a change to
  any frozen file in the live tree or in the copy (changed or removed) or a file added to the live tree stops the run with exit 3 and state blocked, no
  accepted row, and the output file put back. What a verifier leaves in its working folder (a cache, a marker) is removed from the copy after each run, so it
  cannot carry state from one attempt to the next, and is not a block.
  The candidate is not part of the frozen set, so a candidate that differs from one attempt to the next never blocks. Within an attempt it is hashed when it is
  written and must be the same when the verifier has run and again before accepted; a verifier that writes to or removes the candidate blocks the run
  (candidate-changed).
  Pre-flight: before the first call the verifier is run on an empty stub. Exit 0 is refused (a verifier that cannot fail). So is a path it could not find that
  exists at the same place beside the live verifier (a sibling the manifest does not hold; the path is named), a Python module it could not import (other than
  the candidate itself), and an interpreter that cannot be started. Any other failure passes, with or without FAIL lines, and so does a missing path that is
  missing live as well. Refused at start with exit 2 and no run row: an output file or the work folder inside the verifier's folder, a symlink or junction in the
  manifest or as the verifier's own folder, and a manifest over -MaxManifestFiles or -MaxManifestBytes. A pre-flight refusal has exit 2 too and a run row with
  outcome refused and state blocked (its reason says which); a mid-run block has exit 3 and outcome blocked.
  Later, the same kind of hole (a path missing in the copy that exists beside the live verifier) blocks the run; any other missing path is feedback to the worker.
  A verifier that needs files beside its folder, such as a sibling folder of fixtures, must name them with -VerifierFiles.
  -ReverifyOf <run id> is the safe way after a deliberate verifier edit. It makes no model call: it needs that run's manifest.json and the same verifier path,
  freezes the edited verifier, re-proves it on the empty stub (must fail), on that run's output file as it was before the run (it must get the verdict the old
  verifier gave it, which that run recorded; skipped and recorded if there was no such file or no recorded verdict) and on that run's best rejected candidate
  (must still fail; skipped and recorded if there is none; at least one of the two must run; an accepted candidate is not re-proved), records
  the old and new manifest hashes and a diff of path and hash lists (never file contents), and its only success state is accepted-after-verifier-edit (a failed
  proof is blocked, exit 3). A person must read that diff; nothing here enforces it.
  Limits, stated plainly: this is not a sandbox. An absolute path, an environment variable, an installed package, a tool on PATH, the network and any code
  path the empty stub does not reach are outside it. A verifier that loops over a missing folder runs zero iterations and passes with nothing checked, so
  a verifier author should assert that the number of fixtures is above zero. It detects changes to the declared files; it cannot prove the verifier is good.
  Three more things a verifier author should know. (1) A missing file or module is recognised by the wording of the error message (PowerShell's and Python's
  usual wording), so an error worded differently is not seen, a verifier that tests for a file quietly (Test-Path, exists()) and carries on is not seen, and a
  verifier that prints one of those messages itself on the empty stub, for a path that exists beside it, is refused.
  (2) A verifier must not write to the candidate file: a change to it between the verifier's run and acceptance blocks the run (candidate-changed).
  (3) -ReverifyOf is for an edit that keeps every earlier verdict. An edit that loosens the verifier, so that it now accepts a candidate it rejected, fails the
  third proof and has no safe path by design: a person decides, and starts a new run.

.NOTES
  The outcome log (V2-01): one `attempt` row per attempt, then one `run` row, in that order, sharing a run id. Rows hold counts, hashes and codes,
  never prompts, replies or verifier text. An attempt's label is set here, by code, never by the worker:
    NOFENCE  no complete fenced block      IDENT   byte-equal to the previous candidate (not re-verified)
    PARSE:h  a .ps1 does not parse, or the verifier reported a compile error    LINT:h  a .ps1 parses but fails lint-powershell.ps1 (ranked 500)
    WRONG:h  the verifier failed it        SUSPECT:h  the same single check failed on a different candidate
    CAP      token cap with no passing block in the thinking text     FAILED  the model call failed
  h is the first 8 hex digits of the SHA-256 of the first failing line. A passing attempt has no label. The run row's state is accepted,
  budget exhausted, failed (no call was ever answered), cancelled, blocked or accepted-after-verifier-edit. These two come from the verifier
  hash check (V2-02): blocked ends a run that was stopped because the verifier could not be trusted (its row has a reason), accepted-after-verifier-edit ends only a
  -ReverifyOf run. Every attempt row and the run row carry verifier_sha256 (raw bytes), verifier_norm_sha256 (line endings normalised, for comparing checkouts), and
  the run row also carries verifier_files (the file count). A blocked attempt's label is BLOCKED. To cancel a run, create a file named CANCEL in its work folder: it stops before the next call.
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
    [string] $UsageLog = $(if ($env:LOCAL_WORKER_USAGE_LOG) { $env:LOCAL_WORKER_USAGE_LOG } else { Join-Path $PSScriptRoot '../../../../.loop-logs/local-model-usage.jsonl' }),
    # V2-02. Files or folders the verifier needs besides its own folder (a folder of fixtures beside it, say). They are copied with it, hashed with it, and kept in their layout.
    [string[]] $VerifierFiles = @(),
    # The manifest (verifier folder plus -VerifierFiles) is refused above these caps: a verifier in a big folder would be copied and hashed on every check.
    [ValidateRange(1, 100000)] [int] $MaxManifestFiles = 500,
    [ValidateRange(1, 1073741824)] [long] $MaxManifestBytes = 20971520,
    # The id of an earlier run (its `run` row in the outcome log) whose verifier was edited on purpose: re-prove the edited verifier, with no model call. See .NOTES.
    [string] $ReverifyOf
)
$ErrorActionPreference = 'Stop'
$default = [bool]($PSBoundParameters.ContainsKey('InvokeScript'))
if (-not $default -and -not $Model -and -not $FastProfile) {
    Write-Host 'error: no local worker is configured, so delegation is cloud-only. Set LOCAL_WORKER_MODEL in the lab .env (your preferred local model) and run this through run-with-env.ps1.'
    exit 2
}
$freezeScript = Join-Path $PSScriptRoot 'verifier-freeze.ps1'
foreach ($f in $TaskFile, $Verify, $InvokeScript, $freezeScript) { if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { Write-Host "error: missing file $f"; exit 2 } }
. $freezeScript
$outFull = [IO.Path]::GetFullPath($OutFile)
if ($outFull -match '[\\/]\.git[\\/]') { Write-Host 'error: refusing to write inside .git'; exit 2 }
if (-not $WorkDir) { $WorkDir = Join-Path ([IO.Path]::GetTempPath()) ('delegate-' + [guid]::NewGuid().ToString('N').Substring(0, 8)) }
$WorkDir = [IO.Path]::GetFullPath($WorkDir)   # absolute from here on: the verifier copy's paths are compared with paths the verifier prints
New-Item -ItemType Directory -Force -Path $WorkDir, (Split-Path -Parent $outFull) | Out-Null
# An output file that already existed (a real file in a repo) is put back if no attempt is accepted; a failing draft must not replace it.
$hadOut = Test-Path -LiteralPath $outFull -PathType Leaf
if ($hadOut) { Copy-Item -LiteralPath $outFull -Destination (Join-Path $WorkDir 'out-before.txt') -Force }
$runWatch = [Diagnostics.Stopwatch]::StartNew()

$runId = [guid]::NewGuid().ToString('N').Substring(0, 12)
$anyAnswered = $false   # did any model call come back (a token cap counts: the model answered)? Decides failed against budget exhausted.
$vHash = $null; $vNorm = $null; $vCount = $null   # the frozen verifier manifest (V2-02): raw hash, line-ending-normalised hash, file count. Set before the first call.
$candRaw = $null        # the raw hash of the candidate file as Test-Candidate wrote it; it must be the same when the verifier has run and again before accepted.

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
            prompt_tokens = $Usage.prompt_tokens; output_tokens = $Usage.output_tokens; prompt_eval_duration = $Usage.prompt_eval_duration; eval_duration = $Usage.eval_duration; seconds = [math]::Round($Seconds, 1); done_reason = $Usage.done_reason
            candidate_sha256 = $(if ($null -ne $Cand) { Get-Sha256Hex ([string]$Cand) } else { $null })
            verifier_sha256 = $vHash; verifier_norm_sha256 = $vNorm }
        if ($Salvaged) { $row.salvaged = $true }
        Add-OutcomeLine ($row | ConvertTo-Json -Compress)
    } catch { }
}
# One line per run, after its attempt rows, so results can be counted by tag without keeping scratch folders. $Outcome is the older field (accepted, salvaged,
# not accepted, cancelled); $State is the terminal state. Never allowed to break a run.
function Write-Outcome([string] $Outcome, [int] $Attempts, [string] $State, [hashtable] $Extra = @{}) {
    try {
        $tokens = 0
        $ulog = Join-Path $WorkDir 'usage.jsonl'
        if (Test-Path -LiteralPath $ulog) { foreach ($l in Get-Content -LiteralPath $ulog) { try { $tokens += [int](($l | ConvertFrom-Json).output_tokens) } catch { } } }
        $row = [ordered]@{ kind = 'run'; run = $runId; ts = (Get-Date).ToUniversalTime().ToString('o'); tag = $(if ($Tag) { $Tag } else { $null }); task = (Split-Path -Leaf $TaskFile); outcome = $Outcome; state = $State; attempts = $Attempts
            max_attempts = $MaxAttempts; seconds = [int]$runWatch.Elapsed.TotalSeconds; output_tokens = $tokens; work_dir = $WorkDir
            verifier_sha256 = $vHash; verifier_norm_sha256 = $vNorm; verifier_files = $vCount }
        foreach ($k in $Extra.Keys) { $row[$k] = $Extra[$k] }
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

# V2-02. $null when nothing the run depends on has changed since the verifier was frozen; otherwise Reason and Details. Checked: every manifest file
# live (changed, added, removed; line-ending-only changes are named as such), the frozen files in the copy, and the candidate file.
function Test-Frozen {
    $details = @()
    try {
        $p = Get-VerifierPlan @vfArgs
        if ($p.Error) { $details += "the verifier manifest can no longer be built: $($p.Error)" }
        else {
            $details += @(Compare-VfHashes $vFrozen (Get-VfHashes $p $null))
            foreach ($rel in $vFrozen.Keys) {
                $cp = Join-Path $vCopy ($rel -replace '/', [IO.Path]::DirectorySeparatorChar)
                if (-not (Test-Path -LiteralPath $cp -PathType Leaf)) { $details += "the copy lost: $rel"; continue }
                if ((Get-VfFileHash $cp).Raw -ne $vFrozen[$rel].Raw) { $details += "the copy was changed: $rel" }
            }
        }
    } catch { $details += "a manifest file could not be read: $($_.Exception.Message)" }
    if ($details.Count) { return [pscustomobject]@{ Reason = 'verifier-changed'; Details = $details } }
    if ($candRaw) {
        if (-not (Test-Path -LiteralPath $outFull -PathType Leaf)) { return [pscustomobject]@{ Reason = 'candidate-changed'; Details = @('the candidate file was removed after it was written for this attempt') } }
        if ((Get-VfFileHash $outFull).Raw -ne $candRaw) { return [pscustomobject]@{ Reason = 'candidate-changed'; Details = @('the candidate file changed after it was written for this attempt') } }
    }
    return $null
}
# Stop because the verifier cannot be trusted: no accepted row, the output file back as it was (or removed if it did not exist; the candidate stays in the work folder), exit 3.
function Stop-Blocked($Blocked, [int] $Attempts, [string] $Cand, [string] $Mode, $CallUsage, [double] $Seconds) {
    if ($null -ne $Cand) { Write-AttemptRow $Attempts $Mode 'BLOCKED' $Cand $CallUsage $Seconds }
    if (Test-Path -LiteralPath $outFull -PathType Leaf) { Copy-Item -LiteralPath $outFull -Destination (Join-Path $WorkDir 'blocked-candidate.txt') -Force }
    # The best candidate the old verifier rejected before the block is what -ReverifyOf re-proves against.
    if ($best) { Set-Content -LiteralPath (Join-Path $WorkDir 'best-candidate.txt') -Value $best.Cand -Encoding utf8 }
    if ($hadOut) { Copy-Item -LiteralPath (Join-Path $WorkDir 'out-before.txt') -Destination $outFull -Force }
    elseif (Test-Path -LiteralPath $outFull -PathType Leaf) { Remove-Item -LiteralPath $outFull -Force }
    Write-Outcome 'blocked' $Attempts 'blocked' @{ reason = $Blocked.Reason }
    Write-Host "BLOCKED ($($Blocked.Reason)) at attempt ${Attempts}: nothing was accepted, and the output file was put back. Work dir: $WorkDir"
    foreach ($d in @($Blocked.Details | Select-Object -First 12)) { Write-Host "  $d" }
    if ($Blocked.Reason -eq 'verifier-changed') { Write-Host "  If the verifier was edited on purpose, run again with -ReverifyOf $runId after reading what changed; otherwise restore it." }
    exit 3
}

# Writes the candidate to the output file, parse-checks .ps1, and runs the independent verifier.
# Returns Ok, Stage, Failing (the FAIL lines) and Summary. Nothing else reaches the pipeline.
function Test-Candidate([string] $Cand) {
    Set-Content -LiteralPath $outFull -Value $Cand -Encoding utf8
    $script:candRaw = (Get-VfFileHash $outFull).Raw
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
    # V2-02: nothing may have changed since the proof; the verifier runs from its frozen copy; nothing may have changed when it is done.
    $bad = Test-Frozen
    if ($bad) { return [pscustomobject]@{ Ok = $false; Stage = 'blocked'; Failing = @(); Summary = 'blocked'; Blocked = $bad } }
    $run = Invoke-VfVerifier $vRun $outFull
    if ($run.NoInterpreter) { return [pscustomobject]@{ Ok = $false; Stage = 'blocked'; Failing = @(); Summary = 'blocked'; Blocked = [pscustomobject]@{ Reason = 'verifier-unavailable'; Details = @($run.Text) } } }
    $v = $run.Text
    $ok = ($run.Code -eq 0)
    $bad = Test-Frozen
    if ($bad) { return [pscustomobject]@{ Ok = $false; Stage = 'blocked'; Failing = @(); Summary = 'blocked'; Blocked = $bad } }
    Clear-VfCopyExtras $vFrozen $vCopy   # what the verifier left in its working folder (a cache, a marker) must not reach the next attempt
    if (-not $ok) {
        $hole = Get-VfHole $v $vCopy $vPlan.Root (Split-Path -Parent $vRun) @($outFull)
        if ($hole) {
            $rel = [IO.Path]::GetRelativePath($vCopy, $hole) -replace '\\', '/'
            return [pscustomobject]@{ Ok = $false; Stage = 'blocked'; Failing = @(); Summary = 'blocked'; Blocked = [pscustomobject]@{ Reason = 'manifest-incomplete'; Details = @("the verifier looked for a path inside its copy that the manifest does not hold: $rel (name it with -VerifierFiles)") } }
        }
    }
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

# ---- V2-02: freeze the verifier, prove it cannot pass an empty stub, and (with -ReverifyOf) re-prove it after a deliberate edit. Nothing here calls the model.
$oldRun = $null
if ($ReverifyOf) {
    if (Test-Path -LiteralPath $OutcomeLog) { foreach ($l in Get-Content -LiteralPath $OutcomeLog) { try { $o = $l | ConvertFrom-Json; if ($o.kind -eq 'run' -and $o.run -eq $ReverifyOf) { $oldRun = $o } } catch { } } }
    if (-not $oldRun) { Write-Host "error: no run row with id $ReverifyOf in $OutcomeLog"; exit 2 }
}
# pwsh -File passes a list as one comma-joined string (delegate-batch.ps1 does this): a value that is not itself an existing path is split on commas.
$VerifierFiles = @(@($VerifierFiles) | ForEach-Object { if ($_ -and -not (Test-Path -LiteralPath $_)) { $_ -split ',' } else { $_ } } | Where-Object { $_ })
$vfArgs = @{ Verify = $Verify; Extra = $VerifierFiles; OutFull = $outFull; WorkFull = [IO.Path]::GetFullPath($WorkDir); MaxFiles = $MaxManifestFiles; MaxBytes = $MaxManifestBytes }
$vPlan = Get-VerifierPlan @vfArgs
if ($vPlan.Error) { Write-Host "error: $($vPlan.Error)"; exit 2 }
$vCopy = Join-Path $WorkDir 'verifier-copy'
$vRun = Join-Path $vCopy ($vPlan.VerifyRel -replace '/', [IO.Path]::DirectorySeparatorChar)
# Copy first, hash the copy, then compare it with the live files: a change between the two is caught, which hashing the live files first and copying later would miss.
$vFrozen = $null; $startDetails = @()
try {
    Copy-VfFiles $vPlan $vCopy
    $vFrozen = Get-VfHashes $vPlan $vCopy
    $startDetails = @(Compare-VfHashes $vFrozen (Get-VfHashes $vPlan $null))
} catch { $startDetails = @("the manifest could not be copied or read: $($_.Exception.Message)") }
if ($vFrozen) { $vHash = Get-VfManifestHash $vFrozen 'Raw'; $vNorm = Get-VfManifestHash $vFrozen 'Norm'; $vCount = $vFrozen.Count }
if ($startDetails.Count) { Stop-Blocked ([pscustomobject]@{ Reason = 'verifier-changed'; Details = $startDetails }) 0 $null 'default' $null 0 }
$pyVersion = if ($Verify -match '\.py$') { try { (& python --version 2>&1 | Out-String).Trim() } catch { 'python not found' } } else { $null }
$manifest = [ordered]@{ run = $runId; created = (Get-Date).ToUniversalTime().ToString('o'); verifier = $vPlan.VerifyRel; verifier_path = $vPlan.Verify; sha256 = $vHash; norm_sha256 = $vNorm
    caps = [ordered]@{ files = $MaxManifestFiles; bytes = $MaxManifestBytes }; powershell = $PSVersionTable.PSVersion.ToString(); python = $pyVersion
    note = 'The environment (packages, environment variables, PATH tools, the network) is outside the freeze.'
    files = @(foreach ($k in $vFrozen.Keys) { [ordered]@{ path = $k; sha256 = $vFrozen[$k].Raw; norm_sha256 = $vFrozen[$k].Norm } }) }
Set-Content -LiteralPath (Join-Path $WorkDir 'manifest.json') -Value ($manifest | ConvertTo-Json -Depth 5) -Encoding utf8

function Stop-Refused([string] $Reason, [string] $Message) {
    Write-Outcome 'refused' 0 'blocked' @{ reason = $Reason }
    Write-Host "REFUSED ($Reason): $Message Work dir: $WorkDir"
    exit 2
}
# Pre-flight on an empty stub. Exit 0: the verifier cannot fail. A path it could not find that EXISTS beside the live verifier (a sibling the manifest does not
# hold), or a Python module it could not import: it cannot run from its copy. Any other failure passes, with or without FAIL lines: a missing function or an
# "is not recognized" error on an empty file is how an ordinary verifier fails, and is not a hole in the manifest.
$stubFile = Join-Path (Join-Path $WorkDir 'stub') ('preflight-stub' + [IO.Path]::GetExtension($outFull))
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $stubFile) | Out-Null
New-Item -ItemType File -Force -Path $stubFile | Out-Null
$pre = Invoke-VfVerifier $vRun $stubFile
Set-Content -LiteralPath (Join-Path $WorkDir 'verifier-preflight.txt') -Value $pre.Text -Encoding utf8
if ($pre.NoInterpreter) { Stop-Refused 'preflight-no-interpreter' $pre.Text }
if ($pre.Code -eq 0) { Stop-Refused 'preflight-cannot-fail' 'the verifier accepted an empty file (exit 0), so it cannot fail. Nothing it passes would mean anything. Fix the verifier first.' }
$preHole = Get-VfHole $pre.Text $vCopy $vPlan.Root (Split-Path -Parent $vRun) @($stubFile)
if ($preHole) {
    $holeRel = [IO.Path]::GetRelativePath($vCopy, $preHole) -replace '\\', '/'
    Stop-Refused 'preflight-missing' "the verifier looked for '$holeRel', which exists beside the live verifier but is not in its copy. Name it with -VerifierFiles. See verifier-preflight.txt in the work folder."
}
$preModule = Get-VfMissingModule $pre.Text @($stubFile, $outFull)
if ($preModule) { Stop-Refused 'preflight-missing' "the verifier could not import the module '$preModule'. See verifier-preflight.txt in the work folder." }
# The pre-flight was a verifier run like any other: nothing may have changed during it, and what it left in the copy is cleared.
$bad = Test-Frozen
if ($bad) { Stop-Blocked $bad 0 $null 'default' $null 0 }
Clear-VfCopyExtras $vFrozen $vCopy
# What this verifier says about the output file as it was before the run (if there was one): -ReverifyOf later asks for the same verdict, not for a pass.
$originalVerdict = $null
if ($hadOut -and -not $ReverifyOf) {
    $origCheck = Join-Path (Split-Path -Parent $stubFile) ('original-check' + [IO.Path]::GetExtension($outFull))
    Copy-Item -LiteralPath (Join-Path $WorkDir 'out-before.txt') -Destination $origCheck -Force
    $ov = Invoke-VfVerifier $vRun $origCheck
    $bad = Test-Frozen
    if ($bad) { Stop-Blocked $bad 0 $null 'default' $null 0 }
    Clear-VfCopyExtras $vFrozen $vCopy
    $originalVerdict = if ($ov.NoInterpreter) { $null } elseif ($ov.Code -eq 0) { 'pass' } else { 'fail' }
    $manifest.original_verdict = $originalVerdict
    Set-Content -LiteralPath (Join-Path $WorkDir 'manifest.json') -Value ($manifest | ConvertTo-Json -Depth 5) -Encoding utf8
}

if ($ReverifyOf) {
    # The safe path after a deliberate verifier edit: no model call; three proofs; a diff of path and hash lists for a person to read.
    $oldDir = [string]$oldRun.work_dir
    $oldFiles = $null; $oldVerifierRel = $null; $oldVerifierPath = $null; $oldVerdict = $null
    $oldManifestPath = if ($oldDir) { Join-Path $oldDir 'manifest.json' } else { $null }
    if ($oldManifestPath -and (Test-Path -LiteralPath $oldManifestPath -PathType Leaf)) {
        try {
            $om = Get-Content -Raw -LiteralPath $oldManifestPath | ConvertFrom-Json
            $oldVerifierRel = [string]$om.verifier; $oldVerifierPath = [string]$om.verifier_path
            $oldVerdict = [string]$om.original_verdict; $oldFiles = [Collections.Specialized.OrderedDictionary]::new($script:VfComparer); foreach ($f in $om.files) { $oldFiles[[string]$f.path] = [pscustomobject]@{ Raw = [string]$f.sha256; Norm = [string]$f.norm_sha256 } }
        } catch { $oldFiles = $null }
    }
    # Without the earlier manifest there is nothing to compare, and the run may have used another verifier altogether.
    if (-not $oldFiles) { Write-Host "error: run $ReverifyOf has no readable manifest.json in its work folder (it predates the freeze, or the folder is gone), so its verifier cannot be compared with this one."; exit 2 }
    if ($oldVerifierRel -ne $vPlan.VerifyRel -or -not $oldVerifierPath -or -not $oldVerifierPath.Equals($vPlan.Verify, $script:VfComparison)) { Write-Host "error: run $ReverifyOf used a different verifier file ('$oldVerifierRel' there, '$($vPlan.VerifyRel)' here, or another folder): -ReverifyOf is for an edit to the same verifier."; exit 2 }
    if ($oldRun.verifier_sha256 -and $oldRun.verifier_sha256 -eq $vHash) {
        Write-Host "error: the verifier is unchanged since run $ReverifyOf (same manifest hash), so there is nothing to re-verify."; exit 2
    }
    $proofs = @([ordered]@{ proof = 'empty stub fails'; status = 'passed'; detail = "exit $($pre.Code)" })
    $ext = [IO.Path]::GetExtension($outFull)
    foreach ($spec in @(@{ Name = 'unchanged original keeps its verdict'; File = 'out-before.txt'; Want = 'same' }, @{ Name = 'previously rejected candidate still fails'; File = 'best-candidate.txt'; Want = 'fail' })) {
        $src = if ($oldDir) { Join-Path $oldDir $spec.File } else { $null }
        if (-not $src -or -not (Test-Path -LiteralPath $src -PathType Leaf)) { $proofs += [ordered]@{ proof = $spec.Name; status = 'skipped'; detail = "run $ReverifyOf has no $($spec.File)" }; continue }
        if ($spec.Want -eq 'same' -and -not $oldVerdict) { $proofs += [ordered]@{ proof = $spec.Name; status = 'skipped'; detail = "no verdict was recorded for the original of run $ReverifyOf" }; continue }
        $tmp = Join-Path (Split-Path -Parent $stubFile) ('reverify-' + [IO.Path]::GetFileNameWithoutExtension($spec.File) + $ext)
        Copy-Item -LiteralPath $src -Destination $tmp -Force
        $pr = Invoke-VfVerifier $vRun $tmp
        $bad = Test-Frozen
        if ($bad) { Stop-Blocked $bad 0 $null 'default' $null 0 }
        Clear-VfCopyExtras $vFrozen $vCopy
        $proofHole = Get-VfHole $pr.Text $vCopy $vPlan.Root (Split-Path -Parent $vRun) @($tmp)
        $good = if ($pr.NoInterpreter -or $proofHole) { $false } elseif ($spec.Want -eq 'same') { ($pr.Code -eq 0) -eq ($oldVerdict -eq 'pass') } else { $pr.Code -ne 0 }
        $detail = if ($proofHole) { 'it looked for a path that exists beside the live verifier but is not in its copy: ' + ([IO.Path]::GetRelativePath($vCopy, $proofHole) -replace '\\', '/') } elseif ($spec.Want -eq 'same') { "now $(if ($pr.Code -eq 0) { 'pass' } else { 'fail' }), recorded $oldVerdict" } else { "exit $($pr.Code)" }
        $proofs += [ordered]@{ proof = $spec.Name; status = $(if ($good) { 'passed' } else { 'failed' }); detail = $detail }
    }
    # The empty stub alone proves little: at least one earlier output must have been re-proved.
    if (-not @($proofs | Where-Object { $_.proof -ne 'empty stub fails' -and $_.status -ne 'skipped' }).Count) {
        Stop-Refused 'reverify-nothing-to-prove' "run $ReverifyOf left no output file from before the run and no rejected candidate, so there is nothing to re-prove the edited verifier against."
    }
    # The diff: paths and hash prefixes only, never contents.
    $diff = @()
    if ($oldFiles) {
        foreach ($c in (Compare-VfHashes $oldFiles $vFrozen)) {
            $k = ($c -replace '^[^:]+: ', '')
            $diff += $(if ($c -like 'changed*') { "$c  ($($oldFiles[$k].Raw.Substring(0, 12)) -> $($vFrozen[$k].Raw.Substring(0, 12)))" } else { $c })
        }
    } else { $diff += "no manifest was recorded for run $ReverifyOf; the new manifest has $vCount file(s): " + (($vFrozen.Keys | Select-Object -First 20) -join ', ') }
    $rv = [ordered]@{ run = $runId; reverify_of = $ReverifyOf; old_sha256 = $oldRun.verifier_sha256; new_sha256 = $vHash; old_norm_sha256 = $oldRun.verifier_norm_sha256; new_norm_sha256 = $vNorm; proofs = $proofs; diff = $diff }
    Set-Content -LiteralPath (Join-Path $WorkDir 'reverify.json') -Value ($rv | ConvertTo-Json -Depth 5) -Encoding utf8
    foreach ($p in $proofs) { Write-Host ("  {0,-8} {1} ({2})" -f $p.status, $p.proof, $p.detail) }
    Write-Host "  verifier manifest: $(if ($oldRun.verifier_sha256) { $oldRun.verifier_sha256.Substring(0, 12) } else { 'none recorded' }) -> $($vHash.Substring(0, 12))"
    foreach ($d in @($diff | Select-Object -First 40)) { Write-Host "  $d" }
    $extra = @{ reverify_of = $ReverifyOf; old_verifier_sha256 = $oldRun.verifier_sha256; proofs = (($proofs | ForEach-Object { "$($_.proof): $($_.status)" }) -join '; ') }
    if (@($proofs | Where-Object { $_.status -eq 'failed' }).Count) {
        Write-Outcome 'not accepted' 0 'blocked' ($extra + @{ reason = 'reverify-failed' })
        Write-Host "BLOCKED (reverify-failed): the edited verifier did not pass every proof. Work dir: $WorkDir"; exit 3
    }
    $bad = Test-Frozen   # the last look, immediately before the state is written
    if ($bad) { Stop-Blocked $bad 0 $null 'default' $null 0 }
    Write-Outcome 'reverified' 0 'accepted-after-verifier-edit' $extra
    Write-Host "RE-VERIFIED after a verifier edit (state accepted-after-verifier-edit). A person must read the diff above before relying on it. Work dir: $WorkDir"
    exit 0
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
                if ($r.Blocked) { Stop-Blocked $r.Blocked $n $blk $mode $callUsage $sw.Elapsed.TotalSeconds }
                if ($r.Ok) {
                    $bad = Test-Frozen
                    if ($bad) { Stop-Blocked $bad $n $blk $mode $callUsage $sw.Elapsed.TotalSeconds }
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
    if ($r.Blocked) { Stop-Blocked $r.Blocked $n $cand $mode $callUsage $callSeconds }
    Write-Host "attempt $n ($mode, $secs): $($r.Summary)"
    if ($r.Ok) {
        # The last look, immediately before the result is called accepted.
        $bad = Test-Frozen
        if ($bad) { Stop-Blocked $bad $n $cand $mode $callUsage $callSeconds }
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
