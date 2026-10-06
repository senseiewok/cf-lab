<#
.SYNOPSIS
    PowerShell AST lint for scripts written by a model (T-0085). Read-only; never runs the files it reads.

.DESCRIPTION
    Parses each given file with [System.Management.Automation.Language.Parser]::ParseFile and reports, as plain text,
    one line per finding: <path as given>:<line>:<column>: <ID> <message>. Then one summary line:
    "FAIL: N finding(s) in M file(s)" or "OK: M file(s) clean".
    Exit codes: 0 clean, 1 at least one finding, 2 usage error (no path, or a path that is not a file; every path is
    checked before any file is linted). A file with parse errors gets only its parse errors (PSL001).

    Rules. Each one comes from a failure the lab recorded; a rule is kept only if it can be decided from the syntax tree
    with few false positives, and each has a fixture that triggers it and a clean twin in lint-fixtures/.
      PSL001  a parse error (line and column of the error).
      PSL002  a statement before param(): the file then runs "param" as a command ("The term 'param' is not recognized").
      PSL003  $script: used in a function that is defined inside another function.
      PSL004  a function with both "return <value>" and a statement-level Write-Output/echo of its own: the caller
              receives an array, not the value. A return or Write-Output inside a nested script block (ForEach-Object { })
              belongs to the script block and is not counted. Bare string statements are not detected.
      PSL005  -ErrorAction/-ea passed to a native command (git, gh, python, python3, py, node, npm, ollama, *.exe):
              it arrives as a literal argument and changes nothing.
      PSL006  Start-Process -NoProfile (a pwsh parameter; pass it in -ArgumentList).
      PSL007  assignment to $matches (every -match overwrites it).
      PSL008  ${a.b} (a variable literally named "a.b"; it is empty). A drive-qualified name such as ${env:a.b} is fine.
      PSL009  redirection to /dev/null (writes a file named dev
ull; use $null).
      PSL010  Join-Path with a single path argument and no pipeline input.
      PSL011  Invoke-Expression or its alias iex.

    Left out on purpose (they cannot be decided from the tree, or flagged too many correct lines): "2>$null" around a
    native call inside a function that throws on a non-zero exit; a missing $LASTEXITCODE check after a native call;
    unquoted paths with spaces; Windows PowerShell 5.1 against 7 differences; Set-Content/Out-File without -Encoding
    (UTF-8 without a BOM on 7); ConvertTo-Json without -Depth (it flagged 13 calls in 12 of the lab's own scripts, too noisy to keep);
    unsafely built arguments for "& git" beyond Invoke-Expression.

.PARAMETER Path
    One or more files, e.g. (Get-ChildItem -Recurse -Filter *.ps1).FullName. Printed exactly as given.

.PARAMETER SelfTest
    Lints every lint-fixtures/**/bad-psl<NNN>*.ps1 (must give findings, all with rule PSL<NNN>) and every
    lint-fixtures/**/clean-*.ps1 (must give none). The one fixture that does not parse lives in lint-fixtures/known-wrong/,
    which check-changed.ps1 skips, prints one PASS or FAIL line each, then
    "All N lint self-tests passed". Needs only PowerShell 7: no model, network, module or sibling repository.
    The same checks run from Python in test_lint_powershell.py.

.EXAMPLE
    pwsh -NoProfile -File lint-powershell.ps1 a.ps1 b.ps1

.EXAMPLE
    pwsh -NoProfile -File lint-powershell.ps1 -SelfTest

.NOTES
    Not wired into delegate.ps1 yet: run it on a candidate before the verifier to reject the known traps early.
#>
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)] [string[]] $Path,
    [switch] $SelfTest
)

$ErrorActionPreference = 'Stop'

function Get-Psl001 {
    param([object[]] $ParseErrors, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    foreach ($err in $ParseErrors) {
        if ($null -eq $err.Extent) { continue }
        $null = $list.Add([pscustomobject]@{
            Path = $FilePath
            Line = $err.Extent.StartLineNumber
            Column = $err.Extent.StartColumnNumber
            Id = 'PSL001'
            Message = ("parse error: " + ($err.Message -replace '\s+', ' '))
        })
    }
    return $list.ToArray()
}

function Get-Psl002 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $nodes = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($cmd in $nodes) {
        $name = $cmd.GetCommandName()
        if ($name -eq 'param') {
            $null = $list.Add([pscustomobject]@{
                Path = $FilePath
                Line = $cmd.Extent.StartLineNumber
                Column = $cmd.Extent.StartColumnNumber
                Id = 'PSL002'
                Message = 'statement before param(): param() must be the first statement'
            })
        }
    }
    return $list.ToArray()
}

function Get-Psl003 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $vars = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.VariableExpressionAst] }, $true)
    foreach ($var in $vars) {
        if (-not $var.VariablePath.IsScript) { continue }
        # Count the functions that enclose this use; two or more means a function inside a function.
        $depth = 0
        $current = $var.Parent
        while ($null -ne $current) {
            if ($current -is [System.Management.Automation.Language.FunctionDefinitionAst]) { $depth++ }
            $current = $current.Parent
        }
        if ($depth -lt 2) { continue }
        $null = $list.Add([pscustomobject]@{
            Path = $FilePath
            Line = $var.Extent.StartLineNumber
            Column = $var.Extent.StartColumnNumber
            Id = 'PSL003'
            Message = 'script scope variable used inside a nested function'
        })
    }
    return $list.ToArray()
}

function Get-Psl004 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $funcs = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
    foreach ($func in $funcs) {
        if ($null -eq $func.Body) { continue }

        # First return <value> of the function's own (not one inside a nested script block)
        $firstReturn = $null
        $returns = $func.Body.FindAll({ param($n) $n -is [System.Management.Automation.Language.ReturnStatementAst] }, $true)
        foreach ($ret in $returns) {
            if ($null -eq $ret.Pipeline) { continue }
            $own = $ret.Parent
            while ($null -ne $own -and $own -isnot [System.Management.Automation.Language.ScriptBlockAst]) { $own = $own.Parent }
            if ($own -eq $func.Body) { $firstReturn = $ret; break }
        }
        if ($null -eq $firstReturn) { continue }

        # Look for a statement-level Write-Output/echo whose nearest enclosing ScriptBlockAst is the function body
        $hasWo = $false
        $commands = $func.Body.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
        foreach ($cmd in $commands) {
            $name = $cmd.GetCommandName()
            if ($null -eq $name) { continue }
            $ln = $name.ToLowerInvariant()
            if ($ln -ne 'write-output' -and $ln -ne 'echo') { continue }

            # "Of its own": walk .Parent upward from the CommandAst until we hit a ScriptBlockAst;
            # that ScriptBlockAst must be the function's Body.
            $node = $cmd.Parent
            $nearestSb = $null
            while ($null -ne $node) {
                if ($node -is [System.Management.Automation.Language.ScriptBlockAst]) { $nearestSb = $node; break }
                $node = $node.Parent
            }
            if ($null -eq $nearestSb) { continue }
            if ($nearestSb -ne $func.Body) { continue }

            # "Statement-level": the CommandAst's parent must be a PipelineAst with exactly one element,
            # and walking up from that PipelineAst we must NOT encounter an AssignmentStatementAst,
            # ParenExpressionAst, or SubExpressionAst before reaching a ScriptBlockAst.
            $pipeline = $cmd.Parent
            if ($null -eq $pipeline) { continue }
            if ($pipeline -isnot [System.Management.Automation.Language.PipelineAst]) { continue }
            if ($null -eq $pipeline.PipelineElements) { continue }
            if ($pipeline.PipelineElements.Count -ne 1) { continue }

            $blocked = $false
            $node = $pipeline.Parent
            while ($null -ne $node) {
                if ($node -is [System.Management.Automation.Language.AssignmentStatementAst]) { $blocked = $true; break }
                if ($node -is [System.Management.Automation.Language.ParenExpressionAst]) { $blocked = $true; break }
                if ($node -is [System.Management.Automation.Language.SubExpressionAst]) { $blocked = $true; break }
                if ($node -is [System.Management.Automation.Language.ScriptBlockAst]) { break }
                $node = $node.Parent
            }
            if ($blocked) { continue }

            $hasWo = $true
            break
        }

        if ($hasWo) {
            $null = $list.Add([pscustomobject]@{
                Path = $FilePath
                Line = $firstReturn.Extent.StartLineNumber
                Column = $firstReturn.Extent.StartColumnNumber
                Id = 'PSL004'
                Message = 'function mixes Write-Output with a return value'
            })
        }
    }
    return $list.ToArray()
}

function Get-Psl005 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $nativeCmds = @('git', 'gh', 'python', 'python3', 'py', 'node', 'npm', 'ollama')
    $commands = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($cmd in $commands) {
        $name = $cmd.GetCommandName()
        if ($null -eq $name) { continue }
        $ln = $name.ToLowerInvariant()
        $isNative = $false
        foreach ($nc in $nativeCmds) {
            if ($ln -eq $nc) { $isNative = $true; break }
        }
        if (-not $isNative) {
            if ($ln.EndsWith('.exe')) { $isNative = $true }
        }
        if (-not $isNative) { continue }

        foreach ($el in $cmd.CommandElements) {
            if ($el -is [System.Management.Automation.Language.CommandParameterAst]) {
                $pn = $el.ParameterName.ToLowerInvariant()
                if ($pn -eq 'erroraction' -or $pn -eq 'ea') {
                    $null = $list.Add([pscustomobject]@{
                        Path = $FilePath
                        Line = $el.Extent.StartLineNumber
                        Column = $el.Extent.StartColumnNumber
                        Id = 'PSL005'
                        Message = '-ErrorAction is a PowerShell common parameter; a native command gets it as a literal argument'
                    })
                }
            }
        }
    }
    return $list.ToArray()
}

function Get-Psl006 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $commands = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($cmd in $commands) {
        $name = $cmd.GetCommandName()
        if ($null -eq $name) { continue }
        $ln = $name.ToLowerInvariant()
        if ($ln -ne 'start-process' -and $ln -ne 'saps') { continue }

        foreach ($el in $cmd.CommandElements) {
            if ($el -is [System.Management.Automation.Language.CommandParameterAst]) {
                $pn = $el.ParameterName.ToLowerInvariant()
                if ($pn -eq 'noprofile') {
                    $null = $list.Add([pscustomobject]@{
                        Path = $FilePath
                        Line = $el.Extent.StartLineNumber
                        Column = $el.Extent.StartColumnNumber
                        Id = 'PSL006'
                        Message = '-NoProfile is a pwsh parameter; pass it in -ArgumentList'
                    })
                }
            }
        }
    }
    return $list.ToArray()
}

function Get-Psl007 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $assignments = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] }, $true)
    foreach ($asg in $assignments) {
        if ($null -eq $asg.Left) { continue }
        if ($asg.Left -isnot [System.Management.Automation.Language.VariableExpressionAst]) { continue }
        $vp = $asg.Left.VariablePath
        if ($null -eq $vp) { continue }
        $up = $vp.UserPath.ToLowerInvariant()
        if ($up -eq 'matches') {
            $null = $list.Add([pscustomobject]@{
                Path = $FilePath
                Line = $asg.Extent.StartLineNumber
                Column = $asg.Extent.StartColumnNumber
                Id = 'PSL007'
                Message = '$matches is overwritten by every -match; assign to another name'
            })
        }
    }
    return $list.ToArray()
}

function Get-Psl008 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $vars = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.VariableExpressionAst] }, $true)
    foreach ($var in $vars) {
        if ($null -eq $var.VariablePath) { continue }
        $up = $var.VariablePath.UserPath
        if ($null -eq $up) { continue }
        if (-not $up.Contains('.')) { continue }
        if ($var.VariablePath.IsDriveQualified) { continue }
        $null = $list.Add([pscustomobject]@{
            Path = $FilePath
            Line = $var.Extent.StartLineNumber
            Column = $var.Extent.StartColumnNumber
            Id = 'PSL008'
            Message = '${a.b} is a variable named "a.b"; use $($a.b)'
        })
    }
    return $list.ToArray()
}

function Get-Psl009 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $reds = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FileRedirectionAst] }, $true)
    foreach ($red in $reds) {
        if ($null -eq $red.Location) { continue }
        if ($red.Location -isnot [System.Management.Automation.Language.StringConstantExpressionAst]) { continue }
        if ($red.Location.Value -eq '/dev/null') {
            $null = $list.Add([pscustomobject]@{
                Path = $FilePath
                Line = $red.Extent.StartLineNumber
                Column = $red.Extent.StartColumnNumber
                Id = 'PSL009'
                Message = '/dev/null is not a PowerShell device; use $null'
            })
        }
    }
    return $list.ToArray()
}

function Get-Psl010 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $commands = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($cmd in $commands) {
        $name = $cmd.GetCommandName()
        if ($null -eq $name) { continue }
        $ln = $name.ToLowerInvariant()
        if ($ln -ne 'join-path') { continue }

        if ($null -eq $cmd.CommandElements) { continue }
        if ($cmd.CommandElements.Count -ne 2) { continue }

        $second = $cmd.CommandElements[1]
        if ($second -is [System.Management.Automation.Language.CommandParameterAst]) { continue }

        # Must not be receiving pipeline input: parent is not a PipelineAst, or it IS the first element.
        $parent = $cmd.Parent
        if ($null -ne $parent) {
            if ($parent -is [System.Management.Automation.Language.PipelineAst]) {
                $firstEl = $parent.PipelineElements[0]
                if ($firstEl -ne $cmd) { continue }
            }
        }

        $null = $list.Add([pscustomobject]@{
            Path = $FilePath
            Line = $cmd.Extent.StartLineNumber
            Column = $cmd.Extent.StartColumnNumber
            Id = 'PSL010'
            Message = 'Join-Path needs a path and a child path'
        })
    }
    return $list.ToArray()
}

function Get-Psl011 {
    param([object] $Ast, [string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $commands = $Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.CommandAst] }, $true)
    foreach ($cmd in $commands) {
        $name = $cmd.GetCommandName()
        if ($null -eq $name) { continue }
        $ln = $name.ToLowerInvariant()
        if ($ln -ne 'invoke-expression' -and $ln -ne 'iex') { continue }
        $null = $list.Add([pscustomobject]@{
            Path = $FilePath
            Line = $cmd.Extent.StartLineNumber
            Column = $cmd.Extent.StartColumnNumber
            Id = 'PSL011'
            Message = 'Invoke-Expression runs a string as code; call the command with & and separate arguments'
        })
    }
    return $list.ToArray()
}

function Format-Finding {
    param([object] $Finding)
    $list = [System.Collections.Generic.List[object]]::new()
    $text = '{0}:{1}:{2}: {3} {4}' -f $Finding.Path, $Finding.Line, $Finding.Column, $Finding.Id, $Finding.Message
    $null = $list.Add($text)
    return $list.ToArray()
}

function Invoke-LintFile {
    param([string] $FilePath)
    $list = [System.Collections.Generic.List[object]]::new()
    $tokens = $null
    $parseErrors = $null
    $full = (Resolve-Path -LiteralPath $FilePath).ProviderPath
    $ast = [System.Management.Automation.Language.Parser]::ParseFile($full, [ref]$tokens, [ref]$parseErrors)
    if ($parseErrors.Count -gt 0) {
        $fs = @(Get-Psl001 -ParseErrors $parseErrors -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
    } else {
        $fs = @(Get-Psl002 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl003 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl004 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl005 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl006 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl007 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl008 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl009 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl010 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
        $fs = @(Get-Psl011 -Ast $ast -FilePath $FilePath)
        foreach ($f in $fs) { $null = $list.Add($f) }
    }
    if ($list.Count -gt 0) {
        $sorted = @($list | Sort-Object -Property @{Expression='Line';Descending=$false}, @{Expression='Column';Descending=$false})
        $out = [System.Collections.Generic.List[object]]::new()
        foreach ($f in $sorted) { $null = $out.Add($f) }
        return $out.ToArray()
    }
    return @()
}

function Invoke-SelfTest {
    $fixtureDir = Join-Path $PSScriptRoot 'lint-fixtures'
    if (-not (Test-Path -LiteralPath $fixtureDir -PathType Container)) {
        Write-Host "error: fixture directory not found: $fixtureDir"
        exit 1
    }
    $badFiles = @(Get-ChildItem -LiteralPath $fixtureDir -Recurse -File -Filter 'bad-psl*.ps1' | Sort-Object Name)
    $cleanFiles = @(Get-ChildItem -LiteralPath $fixtureDir -Recurse -File -Filter 'clean-*.ps1' | Sort-Object Name)
    if ($badFiles.Count -eq 0 -and $cleanFiles.Count -eq 0) {
        Write-Host "error: no fixture files found in $fixtureDir"
        exit 1
    }
    foreach ($file in $badFiles) {
        $fname = $file.Name
        if ($fname -match 'bad-psl(\d{3})') {
            $expectedId = "PSL$($Matches[1])"
        } else {
            Write-Host "FAIL: $fname : could not extract rule ID from filename"
            exit 1
        }
        $findings = @(Invoke-LintFile -FilePath $file.FullName)
        if ($findings.Count -eq 0) {
            Write-Host "FAIL: $fname : expected at least one finding with ID $expectedId, got none"
            exit 1
        }
        foreach ($f in $findings) {
            if ($f.Id -ne $expectedId) {
                Write-Host "FAIL: $fname : expected all findings to have ID $expectedId, got $($f.Id)"
                exit 1
            }
        }
        Write-Host "PASS: $fname"
    }
    foreach ($file in $cleanFiles) {
        $fname = $file.Name
        $findings = @(Invoke-LintFile -FilePath $file.FullName)
        if ($findings.Count -ne 0) {
            Write-Host "FAIL: $fname : expected no findings, got $($findings.Count)"
            exit 1
        }
        Write-Host "PASS: $fname"
    }
    $total = $badFiles.Count + $cleanFiles.Count
    Write-Host "All $total lint self-tests passed"
    exit 0
}

if ($SelfTest) {
    Invoke-SelfTest
}

if ($Path.Count -eq 0) {
    Write-Host 'usage: pwsh -NoProfile -File lint-powershell.ps1 <file> [file ...] | -SelfTest'
    exit 2
}

foreach ($p in $Path) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        Write-Host "error: file not found: $p"
        exit 2
    }
}

$totalFindings = 0
foreach ($p in $Path) {
    try { $findings = @(Invoke-LintFile -FilePath $p) }
    catch {
        Write-Host "error: cannot read ${p}: $($_.Exception.Message)"
        exit 2
    }
    foreach ($f in $findings) {
        $formatted = @(Format-Finding -Finding $f)
        Write-Host $formatted[0]
    }
    $totalFindings += $findings.Count
}

if ($totalFindings -gt 0) {
    Write-Host "FAIL: $totalFindings finding(s) in $($Path.Count) file(s)"
    exit 1
} else {
    Write-Host "OK: $($Path.Count) file(s) clean"
    exit 0
}
