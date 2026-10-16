<#
.SYNOPSIS
  Run the lab's opt-in browser, graphics, and viewer checks (T-0133).

.DESCRIPTION
  Executes the 7 checks that require a local browser (Playwright Chromium) and
  load ONLY local pages or loopback HTTP servers. No external network requests
  are made.

  If Playwright is not installed, the runner prints an informational message
  and exits cleanly.

.EXAMPLE
  pwsh -NoProfile -File tasks/run-browser-tests.ps1 -DryRun
  pwsh -NoProfile -File tasks/run-browser-tests.ps1
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$RequireBrowser,
    [int]$TimeoutSec = 300
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot | Split-Path -Parent
$skills = Join-Path $repo '.claude/skills'

$checks = @(
    @{ name = 'observe-page-selftest';    script = "$skills/playwright-browser-testing/scripts/observe-page.py"; args = @('--self-test') },
    @{ name = 'pr-screenshots-selftest';  script = "$skills/playwright-browser-testing/scripts/pr-screenshots.py"; args = @('--self-test') },
    @{ name = 'test-check-webgl';         script = "$skills/webgl-threejs-graphics/scripts/test-check-webgl.py"; args = @() },
    @{ name = 'test-check-animated-page'; script = "$skills/webgl-threejs-graphics/scripts/test-check-animated-page.py"; args = @() },
    @{ name = 'webgl-playwright';         script = "$skills/webgl-threejs-graphics/scripts/test-playwright.py"; args = @() },
    @{ name = 'svg-examples';             script = "$skills/svg-animation/scripts/test-examples.py"; args = @() },
    @{ name = 'svg-playwright';           script = "$skills/svg-animation/scripts/test-playwright.py"; args = @() }
)

if ($DryRun) {
    Write-Host "Planned browser test checks ($($checks.Count)):"
    foreach ($c in $checks) {
        Write-Host "  - $($c.name): python $($c.script) $($c.args -join ' ')"
    }
    exit 0
}

# Verify python and playwright availability
$pyCheck = python -c "import playwright; print('Playwright available')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Playwright is not installed in the active Python environment."
    Write-Host "Opt-in installation: pip install --require-hashes -r tasks/browser-requirements.txt"
    Write-Host "Then install Chromium: python -m playwright install chromium"
    if ($RequireBrowser) {
        Write-Host "FAIL: -RequireBrowser was specified but Playwright is missing."
        exit 1
    }
    Write-Host "Skipping browser checks cleanly (offline / opt-in mode)."
    exit 0
}

$failures = 0
$results = @()

Write-Host "Running $($checks.Count) browser checks (timeout ${TimeoutSec}s each)..."
Write-Host "------------------------------------------------------------"

foreach ($c in $checks) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $cmdArgs = @($c.script) + $c.args
    $pinfo = New-Object System.Diagnostics.ProcessStartInfo
    $pinfo.FileName = 'python'
    foreach ($arg in $cmdArgs) {
        $pinfo.ArgumentList.Add($arg)
    }
    $pinfo.RedirectStandardOutput = $true
    $pinfo.RedirectStandardError = $true
    $pinfo.UseShellExecute = $false
    $pinfo.CreateNoWindow = $true

    $proc = [System.Diagnostics.Process]::Start($pinfo)
    $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
    $stderrTask = $proc.StandardError.ReadToEndAsync()

    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        try { $proc.Kill() } catch {}
        $sw.Stop()
        Write-Host ("FAIL  {0,-26} TIMEOUT after {1:N1}s" -f $c.name, $sw.Elapsed.TotalSeconds)
        $failures++
        $results += @{ Name = $c.name; Status = 'TIMEOUT'; Seconds = $sw.Elapsed.TotalSeconds }
        continue
    }

    [System.Threading.Tasks.Task]::WaitAll(@($stdoutTask, $stderrTask))
    $sw.Stop()
    $exitCode = $proc.ExitCode

    if ($exitCode -eq 0) {
        Write-Host ("PASS  {0,-26} in {1:N2}s" -f $c.name, $sw.Elapsed.TotalSeconds)
        $results += @{ Name = $c.name; Status = 'PASS'; Seconds = $sw.Elapsed.TotalSeconds }
    } else {
        Write-Host ("FAIL  {0,-26} exit {1} in {2:N2}s" -f $c.name, $exitCode, $sw.Elapsed.TotalSeconds)
        $stdout = $stdoutTask.Result
        $stderr = $stderrTask.Result
        if ($stdout) { Write-Host "  STDOUT: $stdout" }
        if ($stderr) { Write-Host "  STDERR: $stderr" }
        $failures++
        $results += @{ Name = $c.name; Status = "FAIL ($exitCode)"; Seconds = $sw.Elapsed.TotalSeconds }
    }
}

Write-Host "------------------------------------------------------------"
Write-Host "Summary: $($checks.Count - $failures)/$($checks.Count) checks passed, $failures failures."

if ($failures -gt 0) {
    exit 1
}
exit 0
