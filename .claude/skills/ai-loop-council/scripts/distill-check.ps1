<#
.SYNOPSIS
  Loop that has the local worker model write a verification check, proves it against
  known-bad and known-fixed examples (some of them hidden), and feeds failures back until
  it works or the retry cap is hit.

.DESCRIPTION
  A case folder contains:
    task.md                What the check must detect, in plain words.
    bad/                   Shown example where the problem IS present (check must exit non-zero).
    fixed/                 Shown example where the problem is NOT present (check must exit 0).
    holdout/bad-<name>/    Hidden examples. The model never sees their contents, so a check that
    holdout/fixed-<name>/  only memorised the shown examples fails here.
    holdout/<dir>.hint.md  Optional one-line hint sent as feedback when a check is wrong on that
                           hidden example. Describe the situation, not the file contents.
    grounding.md           Primary-source excerpts with URLs (specs, official docs), added to the
                           prompt as the authority. The worker has no web access, so the
                           orchestrator collects these; the script warns when the file is missing.
    reference-check.ps1    Optional check written by the orchestrator. It must pass every example
                           before the loop starts; if it doesn't, the examples are wrong.

  Accepted checks are saved as accepted-check.ps1. Every attempt is appended to attempts.jsonl
  (git-ignored), which the orchestrator reads to distill lessons into skills.

  Model-written code is untrusted. Before running it, this script parses it and rejects any
  command, .NET call or file redirect outside a small read-only allowlist. Allowed checks then
  run in a separate pwsh process, inside a temporary copy of the example files, with a timeout.

.EXAMPLE
  ./distill-check.ps1 -CaseDir ../cases/reduced-motion
  ./distill-check.ps1 -CaseDir ../cases/reduced-motion -VerifyCheck ../cases/reduced-motion/accepted-check.ps1
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $CaseDir,
    # Score an existing check against every example instead of running the model loop.
    [string] $VerifyCheck,
    # Run every check in known-wrong/ (deliberately broken or previously wrong checks). Each
    # must fail at least one example; one that passes shows a gap in the examples.
    [switch] $VerifyKnownWrong,
    [ValidateRange(1, 6)] [int] $MaxAttempts = 3,
    [int] $CheckTimeoutSec = 20,
    # Model profile (ollama-profile.json from a model profile skill). Without it, the invoke
    # script's defaults are used.
    [string] $ModelProfile,
    # Benchmark runs: label attempts and leave accepted-check.ps1 untouched.
    [string] $RunLabel,
    [switch] $NoSave
)

$ErrorActionPreference = 'Stop'
$CaseDir = (Resolve-Path $CaseDir).Path
foreach ($p in 'task.md', 'bad', 'fixed') {
    if (-not (Test-Path (Join-Path $CaseDir $p))) { throw "Case folder is missing '$p': $CaseDir" }
}

$invoke = Join-Path $PSScriptRoot 'invoke-local-model.ps1'
$attemptLog = Join-Path $CaseDir 'attempts.jsonl'
$work = Join-Path ([IO.Path]::GetTempPath()) ("distill-" + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $work | Out-Null

$allowedCommands = @(
    'Get-Content', 'Get-ChildItem', 'Select-String', 'Test-Path', 'Get-Command', 'Join-Path', 'Split-Path',
    'ForEach-Object', 'Where-Object', 'Select-Object', 'Sort-Object', 'Measure-Object', 'Group-Object',
    'ConvertFrom-Json', 'Write-Output', 'Write-Error', 'Write-Host', 'Out-String'
)
$allowedTypes = @('regex', 'string', 'math', 'System.Text.RegularExpressions.Regex', 'System.String', 'System.Math',
    # Parsing is read-only and lets checks tell real commands from comments and strings.
    'System.Management.Automation.Language.Parser')
$allowedInstanceMethods = @(
    'Substring', 'Trim', 'TrimStart', 'TrimEnd', 'Split', 'ToLower', 'ToUpper', 'ToLowerInvariant', 'ToUpperInvariant',
    'Contains', 'StartsWith', 'EndsWith', 'IndexOf', 'LastIndexOf', 'Match', 'Matches', 'IsMatch', 'NextMatch',
    'ToString', 'Equals', 'PadLeft', 'PadRight', 'FindAll', 'Find', 'GetCommandName',
    # In-memory collection helpers (hashtables, lists); file objects have no methods with these names.
    'ContainsKey', 'ContainsValue', 'Add', 'Remove'
)

function Test-CheckSafety([string] $code) {
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($code, [ref]$tokens, [ref]$errors)
    if ($errors.Count) {
        $e = $errors[0]
        return "does not parse: $($e.Message) Line $($e.Extent.StartLineNumber): $($e.Extent.StartScriptPosition.Line.Trim())"
    }
    # Traps the contract already warns about. Models still write them, so enforce them here.
    foreach ($t in $tokens) {
        if ($t.Kind -eq 'StringExpandable' -or $t.Kind -eq 'HereStringExpandable') {
            if ($t.Text -match '\$\{\w+\.\w+') { return "lint: '$($Matches[0])...' inside a string reads a variable literally named with a dot, so it is empty. Use `$(`$var.Property) instead. Line $($t.Extent.StartLineNumber): $($t.Extent.StartScriptPosition.Line.Trim())" }
        }
        if ($t.Kind -eq 'Variable' -and $t.Text -in '$matches', '$Matches' -and $t.Extent.StartScriptPosition.Line -match '\$matches\s*=[^=]') {
            return "lint: assigns to `$matches, which PowerShell overwrites after every -match. Use another name. Line $($t.Extent.StartLineNumber): $($t.Extent.StartScriptPosition.Line.Trim())"
        }
    }
    # Functions the check defines itself are fine to call: their bodies are part of this AST,
    # so every command inside them is still checked below.
    $ownFunctions = @($ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true) | ForEach-Object Name)
    $cmds = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($c in $cmds) {
        $name = $c.GetCommandName()
        if (-not $name) { return 'uses a dynamic command name (& $x or & "...")' }
        # Seen in practice: $(.Name) meaning $($file.Name). It's a mistake, not an unsafe command.
        if ($name.StartsWith('.')) { return "lint: treats '$name' as a command. To read a property inside a subexpression, include the variable: `$(`$file$name), not `$($name). Line $($c.Extent.StartLineNumber): $($c.Extent.StartScriptPosition.Line.Trim())" }
        if ($name -notin $allowedCommands -and $name -notin $ownFunctions) { return "uses '$name', which is neither defined in the check nor in the read-only allowlist: $($allowedCommands -join ', ')" }
        # ForEach-Object with a member name ("ForEach-Object Delete", -MemberName) calls that method on
        # every input object, bypassing the method allowlist below. Only script blocks may be passed.
        if ($name -eq 'ForEach-Object') {
            foreach ($el in @($c.CommandElements | Select-Object -Skip 1)) {
                if ($el -is [System.Management.Automation.Language.CommandParameterAst]) {
                    if ($el.ParameterName -notin 'Begin', 'Process', 'End') { return "passes -$($el.ParameterName) to ForEach-Object; only script blocks are allowed, through -Begin, -Process, -End or positionally" }
                    if ($el.Argument -and $el.Argument -isnot [System.Management.Automation.Language.ScriptBlockExpressionAst]) { return 'passes a non-script-block value to ForEach-Object; only script blocks are allowed' }
                }
                elseif ($el -isnot [System.Management.Automation.Language.ScriptBlockExpressionAst]) {
                    return "passes '$($el.Extent.Text)' to ForEach-Object, which would call it as a method; only script blocks are allowed, as in ForEach-Object { `$_.Name }"
                }
            }
        }
    }
    $members = $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.InvokeMemberExpressionAst] }, $true)
    foreach ($m in $members) {
        if ($m.Static) {
            $type = $m.Expression.TypeName.FullName
            # Creating an in-memory collection is harmless; New-Object stays blocked because it can create anything.
            $isCollectionCtor = $m.Member.Value -eq 'new' -and $type -match '^(System\.Collections\.Generic\.)?(HashSet|List|Dictionary|Queue|Stack)\[|^(hashtable|System\.Collections\.Hashtable)$'
            if ($type -notin $allowedTypes -and -not $isCollectionCtor) { return "calls static .NET method on [$type]; only [regex], [string] and [math] are allowed, plus ::new() for HashSet, List, Dictionary, Queue and Stack" }
        }
        elseif ($m.Member.Value -notin $allowedInstanceMethods) {
            # Instance calls could reach FileInfo.Delete(), MoveTo(), etc., so only string/regex helpers pass.
            return "calls method .$($m.Member.Value)(); allowed methods: $($allowedInstanceMethods -join ', '). Use the -replace operator instead of .Replace()"
        }
    }
    # Setting a property can change a file too ($file.IsReadOnly, .LastWriteTime, .Attributes).
    # Checks keep their own state in variables or hashtable indexes ($h["key"] = 1) instead.
    $propertyWrites = $ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
            ($n.Left -is [System.Management.Automation.Language.MemberExpressionAst] -or
            ($n.Left -is [System.Management.Automation.Language.ConvertExpressionAst] -and $n.Left.Child -is [System.Management.Automation.Language.MemberExpressionAst])) }, $true)
    if ($propertyWrites.Count) { return "sets a property ($($propertyWrites[0].Left.Extent.Text) = ...), which can change files; keep state in variables, or use `$h[`"key`"] = value for hashtables" }
    if ($ast.FindAll({ $args[0] -is [System.Management.Automation.Language.FileRedirectionAst] }, $true).Count) {
        return 'redirects output to a file'
    }
    return $null
}

# Mechanical repair for "$name:" inside strings, which the model keeps writing and which
# wastes whole attempts. Only applied when parsing fails with that error, and only kept if
# the repaired code then parses. Scope prefixes like $env: are left alone.
function Repair-KnownTraps([string] $code) {
    $t = $null; $errs = $null
    $null = [System.Management.Automation.Language.Parser]::ParseInput($code, [ref]$t, [ref]$errs)
    if (-not ($errs | Where-Object { $_.ErrorId -eq 'InvalidVariableReferenceWithDrive' })) { return $null }
    $fixed = [regex]::Replace($code, '(?<![\$`\w])\$(?!(?:env|global|script|local|private|using|variable|function):)(\w+):(?!:)', '$$($$$1):')
    $null = [System.Management.Automation.Language.Parser]::ParseInput($fixed, [ref]$t, [ref]$errs)
    if ($errs.Count) { return $null }
    return $fixed
}

# A model profile may name a hints file ("hints_file", relative to the profile): extra notes added to the
# task. The path must resolve inside the skills folder and be a plain .md file, so a profile from elsewhere
# can't make the loop send an arbitrary file (a .env, a key) to the model.
function Get-ModelHints([string] $ProfilePath, [string] $SkillsRoot) {
    $data = Get-Content -Raw -LiteralPath $ProfilePath | ConvertFrom-Json
    if (-not $data.hints_file) { return '' }
    $full = [IO.Path]::GetFullPath((Join-Path (Split-Path -LiteralPath (Resolve-Path -LiteralPath $ProfilePath).Path) $data.hints_file))
    $root = [IO.Path]::GetFullPath($SkillsRoot).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $compare = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
    if (-not $full.StartsWith($root, $compare)) { throw "hints_file '$($data.hints_file)' resolves outside the skills folder." }
    if ($full -notmatch '\.md$') { throw "hints_file '$($data.hints_file)' must be a .md file." }
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "hints_file not found: $($data.hints_file)" }
    if ((Get-Item -LiteralPath $full).LinkType) { throw "hints_file '$($data.hints_file)' is a link; use a real file." }
    "`n`nNotes for this model (mistakes models have made before; avoid them):`n" + (Get-Content -Raw -LiteralPath $full)
}

function Invoke-CheckOn([string] $code, [string] $fixtureDir) {
    $copy = Join-Path $work ('run-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    Copy-Item -LiteralPath $fixtureDir -Destination $copy -Recurse
    $scriptPath = Join-Path $work 'check.ps1'
    Set-Content -Path $scriptPath -Value $code

    $psi = [Diagnostics.ProcessStartInfo]::new('pwsh', "-NoProfile -NonInteractive -File `"$scriptPath`"")
    $psi.WorkingDirectory = $copy
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.UseShellExecute = $false
    $proc = [Diagnostics.Process]::Start($psi)
    $outTask = $proc.StandardOutput.ReadToEndAsync(); $errTask = $proc.StandardError.ReadToEndAsync()
    if (-not $proc.WaitForExit($CheckTimeoutSec * 1000)) {
        $proc.Kill($true)
        return @{ exit = 'timeout'; output = "killed after $CheckTimeoutSec s" }
    }
    $text = ($outTask.Result + $errTask.Result).Trim()
    if ($text.Length -gt 600) { $text = $text.Substring(0, 600) + ' ...' }
    return @{ exit = $proc.ExitCode; output = $text }
}

function Get-FixtureText([string] $dir) {
    Get-ChildItem -LiteralPath $dir -Recurse -File | ForEach-Object {
        "--- $($_.FullName.Substring($dir.Length + 1))`n$(Get-Content -Raw -LiteralPath $_.FullName)"
    } | Out-String
}

function Get-Examples {
    $list = @(
        [pscustomobject]@{ name = 'bad'; dir = (Join-Path $CaseDir 'bad'); expectBad = $true; hidden = $false; hint = '' }
        [pscustomobject]@{ name = 'fixed'; dir = (Join-Path $CaseDir 'fixed'); expectBad = $false; hidden = $false; hint = '' }
    )
    $holdout = Join-Path $CaseDir 'holdout'
    if (Test-Path $holdout) {
        foreach ($d in Get-ChildItem -LiteralPath $holdout -Directory) {
            if ($d.Name -notmatch '^(bad|fixed)-') { throw "Holdout folder must start with bad- or fixed-: $($d.Name)" }
            $hintFile = Join-Path $holdout "$($d.Name).hint.md"
            $list += [pscustomobject]@{
                name = "holdout/$($d.Name)"; dir = $d.FullName; expectBad = $d.Name.StartsWith('bad-'); hidden = $true
                hint = if (Test-Path $hintFile) { (Get-Content -Raw $hintFile).Trim() } else { '' }
            }
        }
    }
    $list
}

# Runs a check on every example; returns one result per example with a pass flag.
function Measure-Check([string] $code, $examples) {
    foreach ($ex in $examples) {
        $r = Invoke-CheckOn $code $ex.dir
        $flagged = ($r.exit -is [int]) -and $r.exit -ne 0
        [pscustomobject]@{
            name = $ex.name; hidden = $ex.hidden; expectBad = $ex.expectBad; hint = $ex.hint
            exit = $r.exit; output = $r.output
            pass = if ($r.exit -eq 'timeout') { $false } elseif ($ex.expectBad) { $flagged } else { $r.exit -eq 0 }
        }
    }
}

function Write-Scoreboard($results) {
    foreach ($r in $results) {
        "{0,-5} {1,-40} expected {2,-8} got exit {3}" -f $(if ($r.pass) { 'PASS' } else { 'FAIL' }), $r.name,
            $(if ($r.expectBad) { 'non-zero' } else { '0' }), $r.exit
    }
    $passed = @($results | Where-Object pass).Count
    "Score: $passed / $(@($results).Count)"
}

$examples = @(Get-Examples)

try {
    if ($VerifyCheck) {
        $code = Get-Content -Raw (Resolve-Path $VerifyCheck)
        # Same mechanical repair the loop applies, so logged raw attempts verify as they ran.
        $repaired = Repair-KnownTraps $code
        if ($repaired) { $code = $repaired; 'Note: applied the automatic "$name:" repair before verifying.' }
        $unsafe = Test-CheckSafety $code
        if ($unsafe) { "Check rejected: $unsafe"; exit 2 }
        $results = @(Measure-Check $code $examples)
        Write-Scoreboard $results
        if (@($results | Where-Object { -not $_.pass }).Count) { exit 1 } else { exit 0 }
    }

    if ($VerifyKnownWrong) {
        $survivors = 0
        foreach ($k in Get-ChildItem (Join-Path $CaseDir 'known-wrong') -Filter *.ps1 -ErrorAction SilentlyContinue) {
            $code = Get-Content -Raw $k.FullName
            if ($repaired = Repair-KnownTraps $code) { $code = $repaired }
            $unsafe = Test-CheckSafety $code
            if ($unsafe) { "{0,-44} REJECTED BY GUARD ($unsafe)" -f $k.Name; continue }
            $failed = @(Measure-Check $code $examples | Where-Object { -not $_.pass })
            if ($failed.Count) { "{0,-44} caught by: {1}" -f $k.Name, (($failed | ForEach-Object name) -join ', ') }
            else { "{0,-44} SURVIVED: passes every example, so the examples don't test what it breaks" -f $k.Name; $survivors++ }
        }
        if ($survivors) { exit 1 } else { exit 0 }
    }

    # Test the tests: an orchestrator-written reference check must pass every example first.
    $reference = Join-Path $CaseDir 'reference-check.ps1'
    if (Test-Path $reference) {
        $refResults = @(Measure-Check (Get-Content -Raw $reference) $examples)
        if (@($refResults | Where-Object { -not $_.pass }).Count) {
            'The reference check fails some examples, so the examples (or the reference) are wrong. Fix them before running the loop:'
            Write-Scoreboard $refResults
            exit 2
        }
        "Reference check passes all $($examples.Count) examples."
    }

    $schemaPath = Join-Path $work 'check.schema.json'
    @{
        type       = 'object'
        properties = @{ check = @{ type = 'string' }; rationale = @{ type = 'string' } }
        required   = @('check', 'rationale')
    } | ConvertTo-Json -Depth 5 | Set-Content $schemaPath

    $hiddenCount = @($examples | Where-Object hidden).Count
    $task = Get-Content -Raw (Join-Path $CaseDir 'task.md')
    # Grounding target: primary-source excerpts the orchestrator collected. The local worker has
    # no web access, so without this file it can only rely on its own (possibly wrong) memory.
    $groundingPath = Join-Path $CaseDir 'grounding.md'
    if (Test-Path $groundingPath) {
        $task += "`n`nGrounding (primary sources; follow these over your own assumptions):`n" + (Get-Content -Raw $groundingPath)
        "Grounding: using grounding.md."
    }
    else {
        "WARNING: no grounding.md in this case. The worker will rely on its memory. Orchestrator: find a grounding target (spec, tests, docs in the repo) or web-search a primary source and save the excerpts to grounding.md."
    }
    $contract = @"
Write a PowerShell 7 script (a "check") for this task:

$task

Contract:
- The script runs with the current directory set to a folder of files like the examples below.
- Exit 1 (e.g. `exit 1`) when the problem IS present; exit 0 when it is not.
- Read-only. Only these commands are allowed: $($allowedCommands -join ', '). Static .NET calls only on [regex], [string], [math]. No file writes.
- Read files with Get-Content -Raw. Use (?s) in a regex that must match across lines.
- Write one statement per line. Put # comments on their own lines, never after code on the same line.
- Diagnostics are required: before each decision, Write-Output the exact string being tested inside [brackets], so leftover text is visible.
- Don't assign to `$matches` (PowerShell sets it automatically). Inside double-quoted strings, write `$($name):` or `$($file.Name)`, never `$name:` or `${file.Name}`.
- The check is also tested on $hiddenCount hidden examples. Solve the general problem described in the task; don't match the exact text of the examples.

Example where the problem IS present (must exit 1):
$(Get-FixtureText (Join-Path $CaseDir 'bad'))
Example where the problem is NOT present (must exit 0):
$(Get-FixtureText (Join-Path $CaseDir 'fixed'))
"@

    if ($ModelProfile) {
        $hints = Get-ModelHints $ModelProfile (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
        if ($hints) { $contract += $hints; "Hints: added from the model profile's hints_file." }
    }

    $feedback = ''
    $accepted = $false
    $best = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        # Fresh context each attempt: contract + only the latest failure.
        $promptPath = Join-Path $work "prompt-$attempt.md"
        Set-Content -Path $promptPath -Value ($contract + $feedback)
        $invokeArgs = @{ PromptFile = $promptPath; SchemaFile = $schemaPath }
        if ($ModelProfile) { $invokeArgs.ProfileFile = (Resolve-Path $ModelProfile).Path }
        $attemptTimer = [Diagnostics.Stopwatch]::StartNew()
        $reply = (& $invoke @invokeArgs | Out-String) | ConvertFrom-Json
        $attemptTimer.Stop()
        $code = $reply.check

        $record = [ordered]@{ ts = (Get-Date).ToUniversalTime().ToString('o'); attempt = $attempt; label = $RunLabel; model_profile = $(if ($ModelProfile) { "$(Split-Path (Split-Path $ModelProfile) -Leaf)/$(Split-Path $ModelProfile -Leaf)" } else { 'default' }); model_seconds = [math]::Round($attemptTimer.Elapsed.TotalSeconds, 1); check = $code; rationale = $reply.rationale }
        $repaired = Repair-KnownTraps $code
        if ($repaired) { $code = $repaired; $record.ran = $code; $record.autofixed = '"$name:" in strings rewritten to "$($name):"' }
        $unsafe = Test-CheckSafety $code
        if ($unsafe -like 'does not parse*') {
            $record.result = 'does-not-parse'; $record.detail = $unsafe
            # Seen in practice: the whole script on one line with "# comment" in the middle,
            # which comments out everything after it, including closing braces.
            $oneLine = @($code -split "`n").Count -le 2 -and $code -match ';\s*#'
            # Also seen: C-style \" escapes. PowerShell escapes with a backtick, so \" ends the string.
            $cStyleEscape = $code -match '"[^"\r\n]*\\"'
            $cause = if ($oneLine) {
                "Your whole check is on one line and contains '# ...' comments, and a # comments out everything after it on that line, including closing braces. Write one statement per line, and put comments on their own lines."
            } elseif ($cStyleEscape) {
                "You escaped a quote with a backslash (\`"). PowerShell doesn't use backslash escapes, so \`" ends the string early. Put regex patterns in single quotes ('...'), where a double quote needs no escape, or escape it with a backtick (``\`")."
            } else { "Common cause: `"`$name:`" inside double quotes; write `"`$(`$name):`" instead." }
            $record.detail += $(if ($oneLine) { ' [one-line script with # comments]' } elseif ($cStyleEscape) { ' [C-style \" escape]' })
            $feedback = "`n`nYour previous check is not valid PowerShell: it $unsafe.`nPrevious check:`n$code`nFix the syntax. $cause"
        }
        elseif ($unsafe -like 'lint:*') {
            $record.result = 'lint'; $record.detail = $unsafe
            $feedback = "`n`nYour previous check was not run because of a known PowerShell bug: $($unsafe.Substring(6))`nPrevious check:`n$code`nFix that line and keep the rest of the logic."
        }
        elseif ($unsafe) {
            $record.result = 'rejected-unsafe'; $record.detail = $unsafe
            # Name the allowed route, not just the rule that was broken.
            $feedback = "`n`nYour previous check was rejected before running because it $unsafe.`nPrevious check:`n$code`nRewrite only the rejected part. Allowed alternatives: define your own helper functions; for case-sensitive comparisons use -ceq, -cne, -cin, -ccontains or -cmatch; for sets and lists use @() arrays or [System.Collections.Generic.HashSet[string]]::new() (not New-Object); use the -replace operator instead of .Replace()."
        }
        else {
            $results = @(Measure-Check $code $examples)
            $failed = @($results | Where-Object { -not $_.pass })
            $passCount = @($results).Count - $failed.Count
            $record.score = "$passCount/$(@($results).Count)"
            $record.failed = @($failed | ForEach-Object name)
            # Anchor on the best check so far: with a fresh context each attempt, a model that
            # rewrites from scratch can throw away a nearly correct check.
            $regressed = $best -and $passCount -lt $best.passCount
            # A fix can break something else at the same score (a swap), which the score alone hides.
            $lost = if ($best) { @($results | Where-Object { -not $_.pass -and $_.name -in $best.passed }) } else { @() }
            if ($lost.Count) { $record.lost = @($lost | ForEach-Object name) }
            if (-not $best -or $passCount -gt $best.passCount) {
                $best = @{ passCount = $passCount; code = $code; failed = $failed; score = $record.score; passed = @($results | Where-Object pass | ForEach-Object name) }
            }
            if ($regressed) { $record.regressed = $true; $code = $best.code; $failed = $best.failed }
            if (-not $failed.Count) { $record.result = 'accepted'; $accepted = $true }
            else {
                $shownFailed = @($failed | Where-Object { -not $_.hidden })
                $record.result = if ($regressed) { 'regressed' } elseif ($shownFailed.Count) { 'failed-shown' } else { 'failed-hidden-only' }
                $lines = foreach ($f in $failed) {
                    $want = if ($f.expectBad) { 'a non-zero exit, because the problem is present' } else { 'exit 0, because the problem is absent' }
                    if ($f.hidden) {
                        # Never echo hidden output: the diagnostics would leak the hidden file contents.
                        "- A hidden example: got exit $($f.exit), required $want. Situation: $(if ($f.hint) { $f.hint } else { 'no hint available' })"
                    }
                    else {
                        $silent = if ($f.expectBad -and -not $f.output) { ' Your check printed nothing here, so none of your conditions matched. Print each string you test in [brackets] and do not repeat the same parsing approach.' } else { '' }
                        "- The shown $($f.name.ToUpper()) example: got exit $($f.exit), required $want. Output: $($f.output)$silent"
                    }
                }
                $intro = if ($regressed) {
                    "Your latest check regressed to $($record.score). Discard it. Your best check so far passed $($best.score); start from that one, shown below, and change only what the failures require."
                } else { "Your best check so far passed $($best.score) examples. Change only what the failures below require; don't rewrite the parts that already work." }
                if (-not $regressed -and $lost.Count) {
                    $lostText = ($lost | ForEach-Object { if ($_.hidden) { "a hidden example ($($_.hint))" } else { "the shown $($_.name.ToUpper()) example" } }) -join '; '
                    $intro += " Careful: your latest change broke examples that an earlier check passed: $lostText. Keep what made them pass while fixing the rest."
                }
                $feedback = @"


$intro
Failures:
$($lines -join "`n")
Best check so far:
$code
Acceptable approach: test only the part of each file the task is about, handle the situations named above, and keep passing the examples you already pass. Return a corrected check.
"@
            }
        }
        $record | ConvertTo-Json -Compress -Depth 5 | Add-Content -Path $attemptLog
        "attempt $attempt`: $($record.result)$(if ($record.score) { " $($record.score)" })$(if ($record.failed) { " failed: $($record.failed -join ', ')" })$(if ($record.detail) { " ($($record.detail))" })"
        if ($accepted) {
            if (-not $NoSave) { Set-Content -Path (Join-Path $CaseDir 'accepted-check.ps1') -Value $code }
            $(if ($NoSave) { 'Accepted (benchmark run; accepted-check.ps1 left unchanged).' } else { "Accepted. Saved to $(Join-Path $CaseDir 'accepted-check.ps1')" })
            break
        }
    }
    if (-not $accepted) { "No check accepted after $MaxAttempts attempts. Escalate to the orchestrator; see $attemptLog." }
}
finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
