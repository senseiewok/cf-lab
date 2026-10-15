<#
.SYNOPSIS
    Unit test suite for tasks/fast-sentinel-gate.ps1.
    Verifies lock acquisition, contention back-off, stale/corrupt recovery,
    git delta watermarking, and lock release.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$gateScript = Join-Path $PSScriptRoot "fast-sentinel-gate.ps1"
$testLockFile = ".loop-logs/test-sentinel.lock"
$fullTestLockPath = Join-Path $repoRoot $testLockFile

# Ensure cleanup on entry and exit
function Cleanup-TestLock {
    if (Test-Path $fullTestLockPath) {
        Remove-Item $fullTestLockPath -Force -ErrorAction SilentlyContinue
    }
}

Cleanup-TestLock

$passCount = 0
$failCount = 0

function Assert-Test {
    param(
        [string]$Name,
        [bool]$Condition,
        [string]$Details = ""
    )
    if ($Condition) {
        Write-Host "PASS: $Name" -ForegroundColor Green
        $script:passCount++
    } else {
        Write-Host "FAIL: $Name - $Details" -ForegroundColor Red
        $script:failCount++
    }
}

Write-Host "=== Running Fast Sentinel Gate Tests ==="

try {
    # Test 1: Clean Acquisition (Exit code 0)
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-alpha" -LockFile $testLockFile | Out-Null
    $code1 = $LASTEXITCODE
    $lockExists = Test-Path $fullTestLockPath
    $lockData = if ($lockExists) { Get-Content $fullTestLockPath -Raw | ConvertFrom-Json } else { $null }

    Assert-Test -Name "Initial lock acquisition exits 0" -Condition ($code1 -eq 0) -Details "ExitCode=$code1"
    Assert-Test -Name "Lock file created with correct metadata" -Condition ($lockExists -and ($lockData.held_by -eq "sentinel-alpha")) -Details "held_by=$($lockData.held_by)"

    # Test 2: Active Contention Back-Off (Exit code 10)
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-beta" -LockFile $testLockFile | Out-Null
    $code2 = $LASTEXITCODE
    Assert-Test -Name "Contention back-off exits 10" -Condition ($code2 -eq 10) -Details "ExitCode=$code2"

    # Test 3: Release by Non-Owner Leaves Lock Intact
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-beta" -LockFile $testLockFile -Release | Out-Null
    $lockStillExists = Test-Path $fullTestLockPath
    Assert-Test -Name "Release by non-owner does not remove lock" -Condition $lockStillExists

    # Test 4: Release by Owner (Exit code 0)
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-alpha" -LockFile $testLockFile -Release | Out-Null
    $code4 = $LASTEXITCODE
    $lockRemoved = -not (Test-Path $fullTestLockPath)
    Assert-Test -Name "Release by owner exits 0" -Condition ($code4 -eq 0) -Details "ExitCode=$code4"
    Assert-Test -Name "Lock file successfully removed after release" -Condition $lockRemoved

    # Test 5: Stale Lock Recovery (>30 min)
    $staleTime = (Get-Date).AddMinutes(-45).ToString("o")
    $stalePayload = @{
        sentinel_id = "abandoned-sentinel"
        held_by     = "abandoned-sentinel"
        acquired_at = $staleTime
        pid         = 99999
        host        = "OLD-HOST"
    } | ConvertTo-Json
    Set-Content -Path $fullTestLockPath -Value $stalePayload -Encoding utf8

    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-gamma" -LockFile $testLockFile | Out-Null
    $code5 = $LASTEXITCODE
    $reacquiredData = Get-Content $fullTestLockPath -Raw | ConvertFrom-Json
    Assert-Test -Name "Stale lock (>30m) reclaimed with exit 0" -Condition ($code5 -eq 0) -Details "ExitCode=$code5"
    Assert-Test -Name "Stale lock ownership transferred" -Condition ($reacquiredData.held_by -eq "sentinel-gamma")

    # Release gamma lock
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-gamma" -LockFile $testLockFile -Release | Out-Null

    # Test 6: Corrupt Lock Recovery
    Set-Content -Path $fullTestLockPath -Value "NOT_VALID_JSON_CORRUPT_DATA" -Encoding utf8
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-delta" -LockFile $testLockFile | Out-Null
    $code6 = $LASTEXITCODE
    $corruptRecoveredData = Get-Content $fullTestLockPath -Raw | ConvertFrom-Json
    Assert-Test -Name "Corrupt lock cleanly recovered with exit 0" -Condition ($code6 -eq 0) -Details "ExitCode=$code6"
    Assert-Test -Name "Corrupt lock overwritten by new sentinel" -Condition ($corruptRecoveredData.held_by -eq "sentinel-delta")

    # Release delta lock
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-delta" -LockFile $testLockFile -Release | Out-Null

    # Test 7: Watermark Matching Yields Idle Exit (Exit code 20)
    $tasksTree = (git -C $repoRoot rev-parse "HEAD:tasks")
    $testWatermarkPath = Join-Path $repoRoot ".loop-logs/test-watermark.json"
    $watermarkPayload = @{
        sentinel_id = "sentinel-watermark-test"
        timestamp   = (Get-Date).ToString("o")
        tree_hashes = @{
            "tasks" = $tasksTree
        }
    } | ConvertTo-Json
    Set-Content -Path $testWatermarkPath -Value $watermarkPayload -Encoding utf8

    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-epsilon" -LockFile $testLockFile -WatermarkFile ".loop-logs/test-watermark.json" -WatchPaths @("tasks") | Out-Null
    $code7 = $LASTEXITCODE
    Assert-Test -Name "Matching watermark tree hash exits 20 (clean idle, zero token burn)" -Condition ($code7 -eq 20) -Details "ExitCode=$code7"

    # Test 8: Modified Watermark Tree Hash Proceeds to Acquire Lock (Exit code 0)
    $watermarkPayloadModified = @{
        sentinel_id = "sentinel-watermark-test"
        timestamp   = (Get-Date).ToString("o")
        tree_hashes = @{
            "tasks" = "0000000000000000000000000000000000000000"
        }
    } | ConvertTo-Json
    Set-Content -Path $testWatermarkPath -Value $watermarkPayloadModified -Encoding utf8

    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-epsilon" -LockFile $testLockFile -WatermarkFile ".loop-logs/test-watermark.json" -WatchPaths @("tasks") | Out-Null
    $code8 = $LASTEXITCODE
    Assert-Test -Name "Changed watermark tree hash falls through to acquire lock (exit 0)" -Condition ($code8 -eq 0) -Details "ExitCode=$code8"

    # Release epsilon lock & cleanup watermark
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-epsilon" -LockFile $testLockFile -Release | Out-Null
    if (Test-Path $testWatermarkPath) {
        Remove-Item $testWatermarkPath -Force -ErrorAction SilentlyContinue
    }

    # Test 9: F-01 Leaf Basename Key Resolution (e.g., watch path './tasks' matches key 'tasks')
    $leafWatermarkPath = Join-Path $repoRoot ".loop-logs/test-leaf-watermark.json"
    $leafPayload = @{
        sentinel_id = "sentinel-leaf-test"
        timestamp   = (Get-Date).ToString("o")
        tree_hashes = @{
            "tasks" = $tasksTree
        }
    } | ConvertTo-Json
    Set-Content -Path $leafWatermarkPath -Value $leafPayload -Encoding utf8

    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-zeta" -LockFile $testLockFile -WatermarkFile ".loop-logs/test-leaf-watermark.json" -WatchPaths @("./tasks") | Out-Null
    $code9 = $LASTEXITCODE
    Assert-Test -Name "Leaf basename key resolution matches and exits 20 (F-01)" -Condition ($code9 -eq 20) -Details "ExitCode=$code9"

    # Test 10: F-03 Absolute Path for LockFile & WatermarkFile
    $absLockPath = [System.IO.Path]::GetFullPath($fullTestLockPath)
    $absWatermarkPath = [System.IO.Path]::GetFullPath($leafWatermarkPath)
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-eta" -LockFile $absLockPath -WatermarkFile $absWatermarkPath -WatchPaths @("tasks") | Out-Null
    $code10 = $LASTEXITCODE
    Assert-Test -Name "Absolute path for LockFile & WatermarkFile correctly handled (F-03)" -Condition ($code10 -eq 20) -Details "ExitCode=$code10"

    # Cleanup leaf watermark
    if (Test-Path $leafWatermarkPath) {
        Remove-Item $leafWatermarkPath -Force -ErrorAction SilentlyContinue
    }

    # Test 11: -Force Bypasses Matching Watermark & Acquires Lock (Exit code 0)
    $tasksTree = (git -C $repoRoot rev-parse "HEAD:tasks")
    $forceWatermarkPath = Join-Path $repoRoot ".loop-logs/test-force-watermark.json"
    $forcePayload = @{
        sentinel_id = "sentinel-force-test"
        timestamp   = (Get-Date).ToString("o")
        tree_hashes = @{
            "tasks" = $tasksTree
        }
    } | ConvertTo-Json
    Set-Content -Path $forceWatermarkPath -Value $forcePayload -Encoding utf8

    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-theta" -LockFile $testLockFile -WatermarkFile ".loop-logs/test-force-watermark.json" -WatchPaths @("tasks") -Force | Out-Null
    $code11 = $LASTEXITCODE
    Assert-Test -Name "-Force bypasses matching watermark and exits 0" -Condition ($code11 -eq 0) -Details "ExitCode=$code11"

    # Test 12: -Force Overrides Active Lock Held by Another Sentinel (Exit code 0)
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-iota" -LockFile $testLockFile -Force | Out-Null
    $code12 = $LASTEXITCODE
    $iotaLockData = Get-Content $fullTestLockPath -Raw | ConvertFrom-Json
    Assert-Test -Name "-Force overrides active lock and transfers ownership" -Condition ($code12 -eq 0 -and $iotaLockData.held_by -eq "sentinel-iota") -Details "ExitCode=$code12, held_by=$($iotaLockData.held_by)"

    # Cleanup force watermark
    if (Test-Path $forceWatermarkPath) {
        Remove-Item $forceWatermarkPath -Force -ErrorAction SilentlyContinue
    }

    # Release iota lock
    & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-iota" -LockFile $testLockFile -Release | Out-Null

    # Test 13: A watch path in a dot-named sibling repo ('.ai/src') resolves instead of being treated as a
    # permanent delta (TrimStart('.') used to turn it into 'ai/src', so the showcase gate never idled).
    $commonGit = (git -C $repoRoot rev-parse --path-format=absolute --git-common-dir 2>$null)
    $labMain = if ($commonGit) { Split-Path -Parent $commonGit } else { $repoRoot }
    $siblingAi = Join-Path (Split-Path -Parent $labMain) ".ai"
    $aiSrcTree = if (Test-Path (Join-Path $siblingAi "src")) { (git -C $siblingAi rev-parse "HEAD:src" 2>$null) } else { $null }
    if ($aiSrcTree) {
        $dotWatermarkPath = Join-Path $repoRoot ".loop-logs/test-dot-watermark.json"
        $dotPayload = @{
            sentinel_id = "sentinel-dot-test"
            timestamp   = (Get-Date).ToString("o")
            tree_hashes = @{ "src" = $aiSrcTree }
        } | ConvertTo-Json
        Set-Content -Path $dotWatermarkPath -Value $dotPayload -Encoding utf8

        & pwsh -NoProfile -File $gateScript -SentinelName "sentinel-dot" -LockFile $testLockFile -WatermarkFile ".loop-logs/test-dot-watermark.json" -WatchPaths @(".ai/src") 2>$null | Out-Null
        $code13 = $LASTEXITCODE
        Assert-Test -Name "Dot-named sibling watch path '.ai/src' resolves and matches watermark (exit 20)" -Condition ($code13 -eq 20) -Details "ExitCode=$code13"
        Remove-Item $dotWatermarkPath -Force -ErrorAction SilentlyContinue
    } else {
        Write-Host "SKIP: Test 13 needs the sibling .ai repo with a src folder next to cf-lab." -ForegroundColor Yellow
    }

} finally {
    Cleanup-TestLock
}

Write-Host "`nTest Summary: $passCount passed, $failCount failed."
if ($failCount -gt 0) {
    exit 1
}
exit 0
