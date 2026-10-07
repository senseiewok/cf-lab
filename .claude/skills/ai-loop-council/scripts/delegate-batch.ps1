<#
.SYNOPSIS
  Run several delegations one after another, unattended, and print one results table.

.DESCRIPTION
  This is the whole "queue": a JSON list and a loop. The local model serves one request at a time (Ollama queues the rest),
  so running delegations sequentially loses nothing and needs no lock. Each item is delegated with delegate.ps1, exactly as if
  you had run it by hand; this script adds nothing to what is trusted. The verifier of each item still decides.

  The batch file is a JSON array of objects: name, task, verify, out (paths relative to the batch file's folder), and optionally
  verifier_files (an array of files or folders the verifier needs besides its own folder, passed as -VerifierFiles). A verifier needs a folder of
  its own: delegate.ps1 freezes the whole folder, so neither the output file nor the work folder may be inside it. Each item
  gets a work folder next to the batch file, work-<name>. A missing file in one item is reported for that item and the batch
  goes on, unless -StopOnFail is given. The results are printed, and written next to the batch file as <batch>.results.json.

  Exit code: 0 when every item was accepted, 1 when any was not, 2 on a usage error. An item that delegate.ps1 blocked (exit 3: the verifier changed\n  mid-run) or refused before the first call (exit 2: the verifier cannot fail, or cannot run from its copy) is reported as blocked or refused.

.EXAMPLE
  pwsh -NoProfile -File delegate-batch.ps1 -Batch .\batch.json -NumCtx 65536 -MaxOutputTokens 16384
#>
param(
    [Parameter(Mandatory)] [string] $Batch,
    [string] $DelegateScript = (Join-Path $PSScriptRoot 'delegate.ps1'),
    # Passed to delegate.ps1 only when given, so a profile's own num_ctx is not overridden.
    [int] $NumCtx,
    [ValidateRange(1, 16384)] [int] $MaxOutputTokens = 8192,
    [string] $Model,
    [string] $FastProfile,
    [string] $ThinkingProfile,
    [string] $InvokeScript,
    [switch] $StopOnFail
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Batch -PathType Leaf)) { Write-Host "error: missing batch file $Batch"; exit 2 }
$batchFull = (Resolve-Path -LiteralPath $Batch).Path
$dir = Split-Path -Parent $batchFull
try { $items = @(Get-Content -Raw -LiteralPath $batchFull | ConvertFrom-Json -ErrorAction Stop) } catch { Write-Host "error: the batch file is not valid JSON: $($_.Exception.Message)"; exit 2 }
if (-not $items.Count) { Write-Host 'error: the batch file has no items'; exit 2 }
foreach ($it in $items) {
    foreach ($k in 'name', 'task', 'verify', 'out') {
        if (-not $it.PSObject.Properties[$k] -or [string]::IsNullOrWhiteSpace([string]$it.$k)) { Write-Host "error: an item is missing '$k'"; exit 2 }
    }
    if ([string]$it.name -notmatch '^[A-Za-z0-9._-]+$') { Write-Host "error: the item name '$($it.name)' may use only letters, digits, dot, underscore and hyphen"; exit 2 }
}
if ($items.name.Count -ne @($items.name | Select-Object -Unique).Count) { Write-Host 'error: item names must be unique'; exit 2 }

function Resolve-Item([string] $p) { if ([IO.Path]::IsPathRooted($p)) { $p } else { Join-Path $dir $p } }

$results = @()
foreach ($it in $items) {
    $task = Resolve-Item $it.task; $verify = Resolve-Item $it.verify; $out = Resolve-Item $it.out
    $work = Join-Path $dir ("work-" + $it.name)
    $row = [ordered]@{ name = [string]$it.name; status = 'error'; detail = ''; seconds = 0 }
    $missing = @($task, $verify | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing) {
        $row.detail = 'missing file: ' + (Split-Path -Leaf $missing[0])
    } else {
        $args2 = @('-NoProfile', '-File', $DelegateScript, '-TaskFile', $task, '-Verify', $verify, '-OutFile', $out, '-WorkDir', $work, '-MaxOutputTokens', $MaxOutputTokens)
        if ($PSBoundParameters.ContainsKey('NumCtx')) { $args2 += '-NumCtx', $NumCtx }
        if ($Model) { $args2 += '-Model', $Model }
        if ($FastProfile) { $args2 += '-FastProfile', $FastProfile }
        if ($ThinkingProfile) { $args2 += '-ThinkingProfile', $ThinkingProfile }
        if ($InvokeScript) { $args2 += '-InvokeScript', $InvokeScript }
        if ($it.PSObject.Properties['verifier_files']) { $vf = @(@($it.verifier_files) | Where-Object { $_ } | ForEach-Object { Resolve-Item ([string]$_) }); if ($vf.Count) { $args2 += '-VerifierFiles'; $args2 += ($vf -join ',') } }
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $text = (& pwsh @args2 2>&1 | Out-String)
        $row.seconds = [int]$sw.Elapsed.TotalSeconds
        $code = $LASTEXITCODE
        if ($text -match 'ACCEPTED on attempt (\d+)') { $row.status = 'accepted'; $row.detail = "attempt $($Matches[1])" }
        # delegate.ps1 exits 0 with "SALVAGED on attempt N" when a capped call's thinking held a complete answer that passed the verifier: accepted, but flagged for an extra careful read.
        elseif ($text -match 'SALVAGED on attempt (\d+)') { $row.status = 'accepted'; $row.detail = "attempt $($Matches[1]) SALVAGED from thinking text: read with extra care" }
        elseif ($text -match 'NOT ACCEPTED after (\d+)') { $row.status = 'not accepted'; $row.detail = "after $($Matches[1]) attempt(s)" }
        # delegate.ps1 exits 1 with "CANCELLED before attempt N" when a CANCEL file is in the item's work folder: a decision by a person, not a failure of the worker or the script.
        elseif ($text -match 'CANCELLED before attempt (\d+)') { $row.status = 'cancelled'; $row.detail = "before attempt $($Matches[1])" }
        # V2-02: the verifier was frozen and then changed (exit 3), or it was refused before the first call (exit 2). Nothing was accepted, and the worker is not to blame.
        elseif ($text -match 'BLOCKED \((\S+)\)') { $row.status = 'blocked'; $row.detail = $Matches[1] }
        elseif ($text -match 'REFUSED \((\S+)\)') { $row.status = 'refused'; $row.detail = $Matches[1] }
        else { $row.status = 'error'; $row.detail = "delegate.ps1 exit $code" }
        Set-Content -LiteralPath (Join-Path $dir ("log-" + $it.name + '.txt')) -Value $text -Encoding utf8
    }
    $results += [pscustomobject]$row
    Write-Host ("{0,-24} {1,-13} {2,5}s  {3}" -f $row.name, $row.status, $row.seconds, $row.detail)
    if ($StopOnFail -and $row.status -ne 'accepted') { Write-Host 'stopping: -StopOnFail'; break }
}
$resultsFile = [IO.Path]::ChangeExtension($batchFull, $null).TrimEnd('.') + '.results.json'
$results | ConvertTo-Json -AsArray | Set-Content -LiteralPath $resultsFile -Encoding utf8
$ok = @($results | Where-Object { $_.status -eq 'accepted' }).Count
Write-Host "$ok of $($items.Count) accepted; results in $resultsFile"
if ($ok -eq $items.Count) { exit 0 } else { exit 1 }
