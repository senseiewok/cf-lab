<#
.SYNOPSIS
  Compare raw speed of local model profiles on the same coding prompt.

.DESCRIPTION
  Sends one fixed prompt to each profile several times and reports Ollama's own timings:
  generation speed (tokens/s), prompt processing speed, model load time and total time.
  The first run of each model includes loading it into memory; later runs show warm speed.

  Results describe your machine. Print them; don't commit them to a public repo.

.EXAMPLE
  ./speed-probe.ps1 -Profiles ../../model-qwen3-coder-next/ollama-profile.json, ../../model-qwen3-8-27b/ollama-profile.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string[]] $Profiles,
    [ValidateRange(1, 10)] [int] $Runs = 3,
    # Also run thinking-capable profiles with thinking off, to show what thinking costs.
    [switch] $CompareThinking
)

$ErrorActionPreference = 'Stop'
$prompt = @'
Write a PowerShell 7 function Get-DuplicateFiles that takes a folder path, finds files with identical
content using SHA256 hashes, and returns groups of duplicates. Include comment-based help. Code only.
'@

function Invoke-Probe($profileData, [bool] $think) {
    $options = @{ num_ctx = $profileData.num_ctx; temperature = $profileData.temperature; top_p = $profileData.top_p; top_k = $profileData.top_k; min_p = $profileData.min_p }
    $body = @{ model = $profileData.model; stream = $false; keep_alive = '15m'; options = $options; messages = @(@{ role = 'user'; content = $prompt }) }
    if ($null -ne $profileData.think) { $body.think = $think }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod -Uri 'http://localhost:11434/api/chat' -Method Post -Body ($body | ConvertTo-Json -Depth 10) -ContentType 'application/json' -TimeoutSec 900
    $sw.Stop()
    [pscustomobject]@{
        load_s        = [math]::Round($r.load_duration / 1e9, 1)
        prompt_tok_s  = if ($r.prompt_eval_duration) { [math]::Round($r.prompt_eval_count / ($r.prompt_eval_duration / 1e9), 0) } else { $null }
        gen_tok_s     = [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 1)
        output_tokens = $r.eval_count
        thinking_chars = if ($r.message.thinking) { $r.message.thinking.Length } else { 0 }
        total_s       = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    }
}

$rows = foreach ($p in $Profiles) {
    $profileData = Get-Content -Raw $p | ConvertFrom-Json
    $modes = if ($null -ne $profileData.think -and $CompareThinking) { @($true, $false) } elseif ($null -ne $profileData.think) { @([bool]$profileData.think) } else { @($false) }
    foreach ($think in $modes) {
        for ($i = 1; $i -le $Runs; $i++) {
            $m = Invoke-Probe $profileData $think
            $m | Add-Member -NotePropertyName model -NotePropertyValue $profileData.model -PassThru |
                Add-Member -NotePropertyName thinking -NotePropertyValue $think -PassThru |
                Add-Member -NotePropertyName run -NotePropertyValue $i -PassThru
        }
    }
    # Unload before the next model so they don't compete for GPU memory.
    $null = Invoke-RestMethod -Uri 'http://localhost:11434/api/generate' -Method Post -Body (@{ model = $profileData.model; keep_alive = 0 } | ConvertTo-Json) -ContentType 'application/json'
}
$rows | Format-Table model, thinking, run, load_s, prompt_tok_s, gen_tok_s, output_tokens, thinking_chars, total_s -AutoSize
