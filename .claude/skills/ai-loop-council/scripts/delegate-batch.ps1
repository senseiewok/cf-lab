<#
.SYNOPSIS
  Run several delegations one after another, unattended, and print one results table.

.DESCRIPTION
  This is the whole "queue": a JSON list and a loop. The local model serves one request at a time (Ollama queues the rest),
  so running delegations sequentially loses nothing and needs no lock; it stays sequential on purpose. Each item is delegated
  with delegate.ps1, exactly as if you had run it by hand; this script adds nothing to what is trusted. The verifier of each
  item still decides.

  The batch file is a JSON array of objects: name, task, verify, out (paths relative to the batch file's folder), and optionally
  verifier_files (an array of files or folders the verifier needs besides its own folder, passed as -VerifierFiles). A verifier needs a folder of
  its own: delegate.ps1 freezes the whole folder, so neither the output file nor the work folder may be inside it. Each item
  gets a work folder next to the batch file, work-<name>. A missing file in one item is reported for that item and the batch
  goes on, unless -StopOnFail is given.

  Optional per-item fields:
    priority           an integer, lower runs first (default 100); ties keep the order of the file.
    depends_on         an array of item names. The item runs only when every one of them was accepted, in this run or an earlier
                       one (read from the results file); otherwise it is skipped with status "skipped (dependency not accepted: <name>)".
                       An item always runs after the items it depends on, whatever its priority. An unknown name or a cycle is a usage error.
    tag                passed to delegate.ps1 as -Tag (default: the item name).
    max_attempts       passed as -MaxAttempts; max_output_tokens passed as -MaxOutputTokens (default: the batch's -MaxOutputTokens).
                       Both are checked against the ranges in delegate.ps1's own param block before anything runs.

  The results file, <batch>.results.json next to the batch file, is rewritten after every item (a temporary file, then a move), so
  an interrupted batch keeps what it finished. It holds the latest row of each item: an item this run did not touch (left out by -Only
  or -MaxItems, or skipped as accepted earlier) keeps its earlier row. -Force starts it afresh.

  -DryRun validates the batch and prints the plan (order, task, verifier folder, output, work folder, caps) without calling delegate.ps1
  or any model. Per item it flags a missing task or verifier, and, with the same rules as delegate.ps1 (Get-VerifierPlan in
  verifier-freeze.ps1), an output file or work folder inside the verifier's folder and a verifier manifest over 500 files or 20 MB.
  -Resume skips an item whose last status in the results file is accepted and whose output file still exists ("skipped (accepted
  earlier)"); -Force overrides -Resume. -Only <names> and -MaxItems <n> run a subset (-MaxItems counts items that are started, not
  skipped ones). A file named CANCEL next to the batch file, there before the batch starts or created between items, stops the batch
  before its next item; every item left gets status "cancelled". Delete the file to run again.

  Exit code: 0 when every item listed in this run was accepted (now or earlier), 1 when any was not, 2 on a usage error. With -DryRun:
  0 when every item is runnable, 1 when any is not. An item that delegate.ps1 blocked (exit 3: the verifier changed mid-run) or refused
  before the first call (exit 2: the verifier cannot fail, or cannot run from its copy) is reported as blocked or refused.

.NOTES
  One line per item: name, status, seconds, detail. Then "<n> of <m> accepted; results in <file>" (an item skipped as accepted earlier
  counts as accepted) and one totals line: accepted, not accepted, blocked, refused, skipped, cancelled, and other (delegate.ps1 ended
  some other way, or a file was missing; see the item's log-<name>.txt). Items not run because of -StopOnFail or -MaxItems are not listed.
  A worked example with its own verifier folder is in batch-example/: run it with -DryRun first.

.EXAMPLE
  pwsh -NoProfile -File delegate-batch.ps1 -Batch .\batch.json -DryRun
  pwsh -NoProfile -File delegate-batch.ps1 -Batch .\batch.json -NumCtx 65536 -MaxOutputTokens 16384
  pwsh -NoProfile -File delegate-batch.ps1 -Batch .\batch.json -Resume
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
    [switch] $StopOnFail,
    # Validate and print the plan; call nothing.
    [switch] $DryRun,
    # Skip items accepted in an earlier run whose output file still exists.
    [switch] $Resume,
    # Ignore the earlier results file: run every selected item and start the results file afresh.
    [switch] $Force,
    # Run only these items (names from the batch file).
    [string[]] $Only = @(),
    # Start at most this many items.
    [ValidateRange(1, 100000)] [int] $MaxItems = 100000
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

# The [ValidateRange(min, max)] of one parameter of delegate.ps1, read from its syntax tree (never run), so the batch checks the same ranges. Falls back to $Default.
function Get-DelegateRange([string] $ParamName, [int[]] $Default) {
    $real = Join-Path $PSScriptRoot 'delegate.ps1'
    if (-not (Test-Path -LiteralPath $real -PathType Leaf)) { return $Default }
    $ast = [Management.Automation.Language.Parser]::ParseFile($real, [ref]$null, [ref]$null)
    $p = @($ast.ParamBlock.Parameters | Where-Object { $_.Name.VariablePath.UserPath -eq $ParamName })
    if (-not $p.Count) { return $Default }
    $range = @($p[0].Attributes | Where-Object { $_.TypeName.Name -eq 'ValidateRange' -and $_.PositionalArguments.Count -eq 2 })
    if (-not $range.Count) { return $Default }
    return @([int]$range[0].PositionalArguments[0].Value, [int]$range[0].PositionalArguments[1].Value)
}
function Test-JsonInt($v) { return ($v -is [int] -or $v -is [long]) }

# Optional per-item fields. Every check runs before anything is delegated.
$attemptRange = Get-DelegateRange 'MaxAttempts' @(1, 5)
$tokenRange = Get-DelegateRange 'MaxOutputTokens' @(1, 16384)
$names = @($items | ForEach-Object { [string]$_.name })
$info = @{}
for ($i = 0; $i -lt $items.Count; $i++) {
    $it = $items[$i]; $nm = [string]$it.name
    $e = [ordered]@{ Item = $it; Index = $i; Priority = 100; Deps = @(); Tag = $nm; MaxAttempts = $null; MaxTokens = $MaxOutputTokens }
    if ($it.PSObject.Properties['priority']) {
        if (-not (Test-JsonInt $it.priority) -or [long]$it.priority -lt [int]::MinValue -or [long]$it.priority -gt [int]::MaxValue) { Write-Host "error: item '$nm': priority must be an integer"; exit 2 }
        $e.Priority = [int]$it.priority
    }
    if ($it.PSObject.Properties['depends_on']) {
        $d = @($it.depends_on)
        foreach ($x in $d) {
            if ($x -isnot [string] -or [string]::IsNullOrWhiteSpace($x)) { Write-Host "error: item '$nm': depends_on must be an array of item names"; exit 2 }
            if ($names -notcontains $x) { Write-Host "error: item '$nm' depends on '$x', which is not an item in this batch"; exit 2 }
        }
        $e.Deps = @($d | Select-Object -Unique)
    }
    if ($it.PSObject.Properties['tag']) {
        if ($it.tag -isnot [string] -or $it.tag -notmatch '^[A-Za-z0-9._:-]+$') { Write-Host "error: item '$nm': tag may use only letters, digits, dot, underscore, colon and hyphen"; exit 2 }
        $e.Tag = $it.tag
    }
    if ($it.PSObject.Properties['max_attempts']) {
        if (-not (Test-JsonInt $it.max_attempts) -or $it.max_attempts -lt $attemptRange[0] -or $it.max_attempts -gt $attemptRange[1]) { Write-Host "error: item '$nm': max_attempts must be an integer from $($attemptRange[0]) to $($attemptRange[1])"; exit 2 }
        $e.MaxAttempts = [int]$it.max_attempts
    }
    if ($it.PSObject.Properties['max_output_tokens']) {
        if (-not (Test-JsonInt $it.max_output_tokens) -or $it.max_output_tokens -lt $tokenRange[0] -or $it.max_output_tokens -gt $tokenRange[1]) { Write-Host "error: item '$nm': max_output_tokens must be an integer from $($tokenRange[0]) to $($tokenRange[1])"; exit 2 }
        $e.MaxTokens = [int]$it.max_output_tokens
    }
    $info[$nm] = [pscustomobject]$e
}
foreach ($o in $Only) { if ($names -notcontains $o) { Write-Host "error: -Only names '$o', which is not an item in this batch"; exit 2 } }

# The order: repeatedly take the ready item (every dependency already placed) with the lowest priority, then the earliest in the file.
$order = [Collections.Generic.List[object]]::new()
$placed = [Collections.Generic.HashSet[string]]::new()
while ($order.Count -lt $items.Count) {
    $ready = @($info.Values | Where-Object { -not $placed.Contains([string]$_.Item.name) -and -not @($_.Deps | Where-Object { -not $placed.Contains($_) }).Count })
    if (-not $ready.Count) { Write-Host ('error: depends_on has a cycle among: ' + (@($items | Where-Object { -not $placed.Contains([string]$_.name) } | ForEach-Object { $_.name }) -join ', ')); exit 2 }
    $next = $ready | Sort-Object -Property Priority, Index | Select-Object -First 1
    $order.Add($next); [void]$placed.Add([string]$next.Item.name)
}
$selected = @($order | Where-Object { -not $Only.Count -or $Only -contains [string]$_.Item.name })

function Resolve-Item([string] $p) { if ([IO.Path]::IsPathRooted($p)) { $p } else { Join-Path $dir $p } }

# The earlier results file: what was accepted before (for -Resume and depends_on), and the rows this run does not replace.
$resultsFile = [IO.Path]::ChangeExtension($batchFull, $null).TrimEnd('.') + '.results.json'
$rows = [ordered]@{}
if (-not $Force -and (Test-Path -LiteralPath $resultsFile -PathType Leaf)) {
    try {
        foreach ($r in @(Get-Content -Raw -LiteralPath $resultsFile | ConvertFrom-Json -ErrorAction Stop)) { if ($r -and $r.name -and $names -contains [string]$r.name) { $rows[[string]$r.name] = $r } }
    } catch {
        if ($Resume) { Write-Host "error: the results file cannot be read, so -Resume cannot tell what was accepted: $resultsFile"; exit 2 }
        Write-Host "note: ignoring an unreadable results file: $resultsFile"
    }
}
$earlier = @{}
foreach ($k in $rows.Keys) { $earlier[$k] = [string]$rows[$k].status }
$cancelFile = Join-Path $dir 'CANCEL'

if ($DryRun) {
    . (Join-Path $PSScriptRoot 'verifier-freeze.ps1')
    $capFiles = 500; $capBytes = 20971520   # delegate.ps1's default -MaxManifestFiles and -MaxManifestBytes
    $bad = 0; $n = 0; $started = 0
    Write-Host "plan for $batchFull (dry run: nothing is delegated)"
    foreach ($e in $selected) {
        $it = $e.Item; $nm = [string]$it.name
        $task = Resolve-Item $it.task; $verify = Resolve-Item $it.verify; $out = Resolve-Item $it.out; $work = Join-Path $dir ("work-" + $nm)
        $skipEarlier = $Resume -and -not $Force -and $earlier[$nm] -eq 'accepted' -and (Test-Path -LiteralPath $out -PathType Leaf)
        if (-not $skipEarlier) { if ($started -ge $MaxItems) { Write-Host "stopping: -MaxItems $MaxItems reached"; break }; $started++ }
        $n++
        $problems = @()
        if (-not (Test-Path -LiteralPath $task -PathType Leaf)) { $problems += "missing task: $($it.task)" }
        if (-not (Test-Path -LiteralPath $verify -PathType Leaf)) { $problems += "missing verifier: $($it.verify)" }
        $manifest = ''
        if (Test-Path -LiteralPath $verify -PathType Leaf) {
            $vf = @(); if ($it.PSObject.Properties['verifier_files']) { $vf = @(@($it.verifier_files) | Where-Object { $_ } | ForEach-Object { Resolve-Item ([string]$_) }) }
            try {
                $plan = Get-VerifierPlan -Verify $verify -Extra $vf -OutFull ([IO.Path]::GetFullPath($out)) -WorkFull ([IO.Path]::GetFullPath($work)) -MaxFiles $capFiles -MaxBytes $capBytes
                if ($plan.Error) { $problems += $plan.Error } else { $manifest = "$(@($plan.Files).Count) file(s), $($plan.Bytes) bytes" }
            } catch { $problems += "the verifier manifest cannot be read: $($_.Exception.Message)" }
        }
        $attempts = if ($null -ne $e.MaxAttempts) { $e.MaxAttempts } else { 'default' }
        Write-Host ("{0,2}. {1}  (priority {2}{3})" -f $n, $nm, $e.Priority, $(if ($e.Deps.Count) { '; after ' + ($e.Deps -join ', ') } else { '' }))
        Write-Host "    task      $task"
        Write-Host "    verifier  $(Split-Path -Parent ([IO.Path]::GetFullPath($verify)))$(if ($manifest) { "  ($manifest; caps $capFiles files, $capBytes bytes)" })"
        Write-Host "    output    $out"
        Write-Host "    work      $work"
        Write-Host "    caps      max attempts $attempts, max output tokens $($e.MaxTokens), tag $($e.Tag)"
        if ($skipEarlier) { Write-Host '    note      would be skipped: accepted earlier (-Resume)' }
        foreach ($dep in $e.Deps) {
            if ($earlier[$dep] -ne 'accepted' -and -not @($selected | Where-Object { $_.Item.name -eq $dep }).Count) { Write-Host "    note      would be skipped: '$dep' is not selected and was not accepted earlier" }
        }
        if ($problems.Count) { $bad++; foreach ($p in $problems) { Write-Host "    NOT RUNNABLE  $p" } } else { Write-Host '    runnable' }
    }
    if (Test-Path -LiteralPath $cancelFile) { Write-Host "note: a CANCEL file is next to the batch file, so a real run would stop before its first item: $cancelFile" }
    Write-Host "$($n - $bad) of $n item(s) runnable"
    if ($bad) { exit 1 } else { exit 0 }
}

# Write the results file whole after every item: a temporary file in the same folder, then a move over the old one.
function Save-Results {
    $list = @(foreach ($e in $order) { $k = [string]$e.Item.name; if ($rows.Contains($k)) { $rows[$k] } })
    $tmp = "$resultsFile.tmp-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
    $list | ConvertTo-Json -AsArray | Set-Content -LiteralPath $tmp -Encoding utf8
    [IO.File]::Move($tmp, $resultsFile, $true)
}
function Show-Row($row) { Write-Host ("{0,-24} {1,-13} {2,5}s  {3}" -f $row.name, $row.status, $row.seconds, $row.detail) }

$results = @()    # the rows listed in this run, in order
$latest = @{}     # name -> the item's latest status: from the earlier results file, then from this run
foreach ($k in $earlier.Keys) { $latest[$k] = $earlier[$k] }
$started = 0; $cancelled = $false
foreach ($e in $selected) {
    $it = $e.Item; $nm = [string]$it.name
    $task = Resolve-Item $it.task; $verify = Resolve-Item $it.verify; $out = Resolve-Item $it.out
    $work = Join-Path $dir ("work-" + $nm)
    $row = [ordered]@{ name = $nm; status = 'error'; detail = ''; seconds = 0 }
    if ($Resume -and -not $Force -and $earlier[$nm] -eq 'accepted' -and (Test-Path -LiteralPath $out -PathType Leaf)) {
        # The earlier accepted row stays in the results file, so a later -Resume still sees it as accepted.
        $row.status = 'skipped (accepted earlier)'
        $results += [pscustomobject]$row; Show-Row $row
        continue
    }
    if (-not $cancelled -and (Test-Path -LiteralPath $cancelFile)) { $cancelled = $true; Write-Host "cancelled: a CANCEL file is next to the batch file, so no further item is started ($cancelFile)" }
    if ($cancelled) {
        $row.status = 'cancelled'; $row.detail = 'CANCEL file next to the batch'
        $latest[$nm] = $row.status; $rows[$nm] = [pscustomobject]$row; $results += $rows[$nm]; Show-Row $row; Save-Results
        continue
    }
    $notOk = @($e.Deps | Where-Object { $latest[$_] -ne 'accepted' })
    if ($notOk.Count) {
        $row.status = "skipped (dependency not accepted: $($notOk[0]))"
        $latest[$nm] = $row.status; $rows[$nm] = [pscustomobject]$row; $results += $rows[$nm]; Show-Row $row; Save-Results
        if ($StopOnFail) { Write-Host 'stopping: -StopOnFail'; break }
        continue
    }
    if ($started -ge $MaxItems) { Write-Host "stopping: -MaxItems $MaxItems reached"; break }
    $started++
    $missing = @($task, $verify | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing) {
        $row.detail = 'missing file: ' + (Split-Path -Leaf $missing[0])
    } else {
        $args2 = @('-NoProfile', '-File', $DelegateScript, '-TaskFile', $task, '-Verify', $verify, '-OutFile', $out, '-WorkDir', $work, '-MaxOutputTokens', $e.MaxTokens, '-Tag', $e.Tag)
        if ($null -ne $e.MaxAttempts) { $args2 += '-MaxAttempts', $e.MaxAttempts }
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
        Set-Content -LiteralPath (Join-Path $dir ("log-" + $nm + '.txt')) -Value $text -Encoding utf8
    }
    $latest[$nm] = $row.status; $rows[$nm] = [pscustomobject]$row; $results += $rows[$nm]; Show-Row $row; Save-Results
    if ($StopOnFail -and $row.status -ne 'accepted') { Write-Host 'stopping: -StopOnFail'; break }
}
if (-not $results.Count) { Write-Host 'nothing was run'; Save-Results }
$count = { param($s) @($results | Where-Object { $_.status -eq $s }).Count }
$skipped = @($results | Where-Object { $_.status -like 'skipped*' }).Count
$ok = (& $count 'accepted') + (& $count 'skipped (accepted earlier)')
$other = @($results | Where-Object { $_.status -notin 'accepted', 'not accepted', 'blocked', 'refused', 'cancelled' -and $_.status -notlike 'skipped*' }).Count
Write-Host "$ok of $($results.Count) accepted; results in $resultsFile"
Write-Host ("totals: accepted {0}, not accepted {1}, blocked {2}, refused {3}, skipped {4}, cancelled {5}, other {6}" -f (& $count 'accepted'), (& $count 'not accepted'), (& $count 'blocked'), (& $count 'refused'), $skipped, (& $count 'cancelled'), $other)
if ($results.Count -and $ok -eq $results.Count) { exit 0 } else { exit 1 }
