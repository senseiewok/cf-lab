# Test for the OS guard in restart-ollama.ps1. It NEVER runs restart-ollama.ps1, which stops every Ollama process:
# it parses the script, checks that the guard comes before any statement that reads settings or touches a process,
# and runs only the guard's own statements, cut from the parse tree, in a child PowerShell with the platform simulated.
# No Ollama, model or network. Prints PASS/FAIL per check and "N/N passed"; exit 0 only when all pass.
param([string] $Script = (Join-Path $PSScriptRoot 'restart-ollama.ps1'))
$ErrorActionPreference = 'Stop'
$fail = @(); $n = 0
function Check([string] $name, [bool] $ok, [string] $detail = '') {
    $script:n++
    Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" }))
    if (-not $ok) { $script:fail += $name }
}
$risky = 'Stop-Process|Get-Process|Start-Process|Start-Sleep|Get-NetTCPConnection|Invoke-RestMethod|GetEnvironmentVariable|SetEnvironmentVariable|OLLAMA_HOST|LOCALAPPDATA|\bollama\b'

# Returns the problems with a script text's guard; an empty list means the guard is in place and comes first.
function Get-GuardProblems([string] $text) {
    $tokens = $null; $errors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { return @("does not parse: $($errors[0].Message)") }
    $s = @($ast.EndBlock.Statements)
    $p = @()
    if ($s.Count -lt 5) { return @('fewer than five statements') }
    if (-not ($s[0] -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $s[0].Name -eq 'Get-PlatformRefusal')) { $p += 'statement 1 is not the Get-PlatformRefusal function' }
    if ($s[1].Extent.Text -notmatch '^\$onWindows\s*=') { $p += 'statement 2 does not set $onWindows' }
    if ($s[2].Extent.Text -notmatch '^\$refusal\s*=\s*Get-PlatformRefusal\s+\$onWindows') { $p += 'statement 3 does not ask Get-PlatformRefusal' }
    if (-not ($s[3] -is [System.Management.Automation.Language.IfStatementAst] -and $s[3].Extent.Text -match '\bexit 2\b')) { $p += 'statement 4 is not the if that exits 2' }
    for ($i = 0; $i -lt 4; $i++) { if ($s[$i].Extent.Text -cmatch $risky) { $p += "guard statement $($i + 1) touches a process or a setting" } }
    $firstRisky = -1
    for ($i = 0; $i -lt $s.Count; $i++) { if ($s[$i].Extent.Text -cmatch $risky) { $firstRisky = $i; break } }
    if ($firstRisky -ge 0 -and $firstRisky -lt 4) { $p += 'something that touches a process or a setting runs before the guard' }
    return $p
}

# Runs only the guard statements, with $onWindows forced, in a child PowerShell. Returns the exit code and the output.
function Invoke-Guard([string] $text, [bool] $onWindows) {
    $ast = [System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$null, [ref]$null)
    $s = @($ast.EndBlock.Statements)
    $body = @($s[0].Extent.Text, ('$onWindows = $' + $onWindows.ToString().ToLowerInvariant()), $s[2].Extent.Text, $s[3].Extent.Text, "Write-Output 'GUARD PASSED'", 'exit 0') -join "`n"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('restart-guard-' + [guid]::NewGuid().ToString('N') + '.ps1')
    try {
        [IO.File]::WriteAllText($tmp, $body, [Text.UTF8Encoding]::new($false))
        $o = & pwsh -NoProfile -File $tmp 2>&1 | Out-String
        return @{ Code = $LASTEXITCODE; Out = $o }
    } finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
}

$text = Get-Content -Raw -LiteralPath $Script
$problems = @(Get-GuardProblems $text)
Check 'the guard is the first four statements and comes before any process or setting' ($problems.Count -eq 0) ($problems -join '; ')
if ($problems.Count -eq 0) {
    $r = Invoke-Guard $text $false
    Check 'on a system other than Windows the guard exits 2' ($r.Code -eq 2) "exit=$($r.Code) out=$($r.Out)"
    Check 'and says the script is Windows only' ($r.Out -match 'This script is Windows only; restart Ollama the way your system does') $r.Out
    Check 'and stops before the next statement' ($r.Out -notmatch 'GUARD PASSED') $r.Out
    $r = Invoke-Guard $text $true
    Check 'on Windows the guard lets the script continue, silently' ($r.Code -eq 0 -and $r.Out.Trim() -eq 'GUARD PASSED') "exit=$($r.Code) out=$($r.Out)"
    $s = @([System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$null, [ref]$null).EndBlock.Statements)
    $detected = & ([scriptblock]::Create($s[1].Extent.Text + '; $onWindows'))
    $want = ($PSVersionTable.PSEdition -eq 'Desktop') -or ($IsWindows -eq $true)
    Check "the platform test reads this host correctly (Windows: $want)" ($detected -eq $want) "got $detected"
}
# Negative controls: the structural check must catch a guard that is missing or comes too late.
$lines = $text -split "`r?`n"
$noGuard = ($lines | Where-Object { $_ -notmatch '^if \(\$refusal\)' }) -join "`n"
Check 'negative control: a script without the if-exit is caught' (@(Get-GuardProblems $noGuard).Count -gt 0) ''
$late = "Get-Process 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force`n" + $text.Substring($text.IndexOf('# OS guard'))
Check 'negative control: a process stop before the guard is caught' (@(Get-GuardProblems $late).Count -gt 0) ''
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
