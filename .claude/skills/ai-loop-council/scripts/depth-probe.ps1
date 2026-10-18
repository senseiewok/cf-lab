#Requires -Version 7
<#
.SYNOPSIS
  Measure whether a local Ollama model can use a synthetic fact hidden at a chosen depth of a long filler prompt.

.DESCRIPTION
  A PowerShell front-end and self-test harness for depth-probe.py.
  Hides a synthetic fact (an access code for a blue door) at a chosen fraction of a long filler text,
  asks for the code, and scores the reply. A negative control prompt without the fact checks that the
  model replies "not stated" rather than hallucinating an access code.

  With -SelfTest, executes the deterministic offline test suite verifying prompt generation, depth
  placement, negative control scoring, loopback enforcement, and stub Ollama evaluation.

.EXAMPLE
  ./depth-probe.ps1 -SelfTest
  ./depth-probe.ps1 -Profile ../../model-qwen3-8-27b/ollama-profile.64k.fast.json -Lengths '8000,32000' -Depths '0.1,0.5,0.9'
  ./depth-probe.ps1 -DryRun -Lengths '8000' -Depths '0.5'
#>
[CmdletBinding(DefaultParameterSetName = 'Run')]
param(
    [Parameter(Mandatory, ParameterSetName = 'SelfTest')]
    [switch] $SelfTest,

    [Parameter(ParameterSetName = 'Run')]
    [string] $Url = 'http://127.0.0.1:11434',

    [Parameter(ParameterSetName = 'Run')]
    [string] $Model,

    [Parameter(ParameterSetName = 'Run')]
    [string] $Profile,

    [Parameter(ParameterSetName = 'Run')]
    [string] $Lengths = '8000,32000,56000',

    [Parameter(ParameterSetName = 'Run')]
    [string] $Depths = '0.1,0.5,0.9',

    [Parameter(ParameterSetName = 'Run')]
    [ValidateRange(1, 10)]
    [int] $Samples = 1,

    [Parameter(ParameterSetName = 'Run')]
    [string] $Out,

    [Parameter(ParameterSetName = 'Run')]
    [int] $Seed = 1,

    [Parameter(ParameterSetName = 'Run')]
    [double] $CharsPerToken = 4.0,

    [Parameter(ParameterSetName = 'Run')]
    [ValidateSet('on', 'off', 'default')]
    [string] $Think = 'default',

    [Parameter(ParameterSetName = 'Run')]
    [switch] $DryRun,

    [Parameter(ParameterSetName = 'Run')]
    [switch] $ShowPrompt
)

$ErrorActionPreference = 'Stop'
$pyScript = Join-Path $PSScriptRoot 'depth-probe.py'
$testScript = Join-Path $PSScriptRoot 'test_depth_probe.py'

function Get-Python {
    foreach ($name in 'python', 'python3') {
        $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $cmd) { continue }
        try { $v = & $cmd.Source -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $v -and [version]"$v" -ge [version]'3.10') { return $cmd.Source }
    }
    if ($IsWindows) {
        $pyCmd = Get-Command py -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($pyCmd) { return $pyCmd.Source }
    }
    return 'python'
}

$pyExe = Get-Python

if ($SelfTest) {
    if (-not (Test-Path $testScript)) {
        throw "SelfTest failed: cannot find test runner at $testScript"
    }
    if (-not (Test-Path $pyScript)) {
        throw "SelfTest failed: cannot find depth-probe script at $pyScript"
    }

    # Verify wrapper dry-run functionality
    $dryOut = & $pyExe $pyScript --dry-run --lengths 8000 --depths 0.5 2>&1 | Out-String
    $dryExit = $LASTEXITCODE
    if ($dryExit -ne 0 -or $dryOut -notmatch '8000' -or $dryOut -notmatch '0\.5') {
        throw "SelfTest failed on dry-run verification (exit $dryExit): $dryOut"
    }
    Write-Output "PASS: depth-probe wrapper dry-run verified"

    # Run the full unit test suite with stub HTTP server
    Write-Output "Running depth-probe test suite ($testScript)..."
    & $pyExe $testScript
    if ($LASTEXITCODE -ne 0) {
        throw "depth-probe self-tests failed with exit code $LASTEXITCODE"
    }
    Write-Output "PASS: all depth-probe tests and negative controls passed"
    return
}

# Normal execution: forward parameters to depth-probe.py
$pyArgs = @($pyScript, '--url', $Url)
if ($Model) { $pyArgs += @('--model', $Model) }
if ($Profile) { $pyArgs += @('--profile', $Profile) }
if ($Lengths) { $pyArgs += @('--lengths', $Lengths) }
if ($Depths) { $pyArgs += @('--depths', $Depths) }
if ($Samples -gt 1) { $pyArgs += @('--samples', $Samples) }
if ($Out) { $pyArgs += @('--out', $Out) }
if ($Seed -ne 1) { $pyArgs += @('--seed', $Seed) }
if ($CharsPerToken -ne 4.0) { $pyArgs += @('--chars-per-token', $CharsPerToken) }
if ($Think -ne 'default') { $pyArgs += @('--think', $Think) }
if ($DryRun) { $pyArgs += '--dry-run' }
if ($ShowPrompt) { $pyArgs += '--show-prompt' }

& $pyExe @pyArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
