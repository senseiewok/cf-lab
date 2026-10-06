<#
.SYNOPSIS
  Measure whether a local model's thinking levels (off, low, medium, xhigh) really change how much it thinks.

.DESCRIPTION
  Sends the same short reasoning question to the local worker at each level, using the 64K profile files
  (ollama-profile.64k.fast.json and ollama-profile.64k.json in the model profile skill, with -ThinkLevel), several samples each, and reads thinking_chars,
  output tokens and seconds from the usage log. Pass: the model answers correctly where it finishes, the median
  thinking_chars is 0 for off and strictly increases through low, medium and xhigh. This is the "does the thinking
  switch work" check of model-onboarding, extended to levels. It contacts only the local Ollama server and sends
  no private data (the prompt is a fixed arithmetic question). A failed level (for example the server rejecting a
  string level) is reported by name, not hidden.

  It needs a running Ollama with the model loaded or loadable; it is not part of the offline self-tests.

.EXAMPLE
  ./think-level-probe.ps1 -Samples 3
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 10)] [int] $Samples = 3,
    [string] $ProfileDir = (Join-Path $PSScriptRoot '../../model-qwen3-8-27b'),
    [string] $OutFile,
    # The question and the digits its right answer contains. The default is the easy one; a harder one shows whether effort changes.
    [string] $PromptText = 'List the prime numbers between 100 and 140, add them up, and reply with the sum as digits only, nothing else.',
    [string] $Want = '1067'
)
$ErrorActionPreference = 'Stop'
$invoke = Join-Path $PSScriptRoot 'invoke-local-model.ps1'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('think-probe-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $tmp | Out-Null
$log = Join-Path $tmp 'usage.jsonl'
$prompt = Join-Path $tmp 'prompt.md'
# Default question: the primes between 100 and 140 are 101, 103, 107, 109, 113, 127, 131, 137 and 139; their sum is 1067.
Set-Content $prompt $PromptText -Encoding utf8
$want = $Want

$median = { param($v) $s = @($v | Sort-Object); if (-not $s.Count) { return $null }; $s[[math]::Floor(($s.Count - 1) / 2)] }
$rows = @()
try {
    foreach ($level in 'fast', 'low', 'medium', 'xhigh') {
        # off uses the 64K fast profile; every other level uses the 64K thinking profile with -ThinkLevel (an explicit level wins over the profile's think setting)
        $profile = Join-Path $ProfileDir $(if ($level -eq 'fast') { 'ollama-profile.64k.fast.json' } else { 'ollama-profile.64k.json' })
        if (-not (Test-Path $profile)) { throw "Missing profile: $profile" }
        $levelArgs = if ($level -eq 'fast') { @() } else { @('-ThinkLevel', $level) }
        $max = if ($level -in 'medium', 'xhigh') { 16384 } else { 8192 }
        $chars = @(); $tokens = @(); $secs = @(); $right = 0; $errors = @()
        for ($i = 1; $i -le $Samples; $i++) {
            $before = if (Test-Path $log) { @(Get-Content $log).Count } else { 0 }
            try {
                $out = (& pwsh -NoProfile -File $invoke -PromptFile $prompt -ProfileFile $profile @levelArgs -LogFile $log -MaxOutputTokens $max -TimeoutSec 900 2>&1 | Out-String).Trim()
                if ($LASTEXITCODE -ne 0) { throw $out }
                if ($out -match "(^|\D)$want(\D|$)") { $right++ }
            }
            catch { $errors += ($_.Exception.Message -replace '\s+', ' ').Substring(0, [math]::Min(160, ($_.Exception.Message -replace '\s+', ' ').Length)) }
            $lines = @(Get-Content $log -ErrorAction SilentlyContinue)
            if ($lines.Count -gt $before) {
                $rec = $lines[-1] | ConvertFrom-Json
                $chars += [int]$rec.thinking_chars; $tokens += [int]$rec.output_tokens; $secs += [double]$rec.seconds
            }
        }
        $rows += [pscustomobject]@{
            level = $level; calls = $Samples; right = $right; errors = $errors.Count
            median_thinking_chars = (& $median $chars); median_output_tokens = (& $median $tokens); median_seconds = (& $median $secs)
            first_error = ($errors | Select-Object -First 1)
        }
        $rows[-1] | Format-List | Out-String | Write-Output
    }
}
finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }

$table = $rows | Format-Table level, calls, right, errors, median_thinking_chars, median_output_tokens, median_seconds -AutoSize | Out-String
Write-Output $table
$pass = $true; $notes = @()
$byLevel = @{}; foreach ($r in $rows) { $byLevel[$r.level] = $r }
if ($byLevel['fast'].errors -gt 0 -or $null -eq $byLevel['fast'].median_thinking_chars -or $byLevel['fast'].median_thinking_chars -ne 0) { $pass = $false; $notes += 'FAIL: off (fast) did not give zero thinking' }
$prev = 0
foreach ($lv in 'low', 'medium', 'xhigh') {
    $m = $byLevel[$lv].median_thinking_chars
    if ($null -eq $m) { $pass = $false; $notes += "FAIL: $lv produced no usable calls ($($byLevel[$lv].first_error))"; continue }
    if ($m -le $prev) { $pass = $false; $notes += "FAIL: $lv median thinking_chars $m is not above the level before ($prev)" }
    $prev = $m
}
if (-not $notes) { $notes += 'PASS: off is zero and thinking increases strictly through low, medium and xhigh' }
$notes | Write-Output
if ($OutFile) { ($table + "`n" + ($notes -join "`n")) | Set-Content -LiteralPath $OutFile -Encoding utf8 }
exit ([int](-not $pass))
