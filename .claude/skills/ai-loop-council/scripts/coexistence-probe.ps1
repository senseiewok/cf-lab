<#
.SYNOPSIS
  Measure what it costs your main local model when a second model is used now and then on the same GPU.

.DESCRIPTION
  Local models share GPU memory. When two don't fit together, Ollama unloads one to load the other, so using a
  second model means a reload for the main model afterwards. This script runs short requests in turn and reports:
    - the main model's normal (warm) speed
    - the second model's load time when the main model is resident
    - the main model's reload time, speed and placement (GPU or CPU) after the second model ran
    - whether both models stayed loaded at the same time

  Each request stops after 60 generated tokens, so the numbers are dominated by loading, not by thinking.
  Results describe your machine: print them, don't commit them to a public repo.

.EXAMPLE
  ./coexistence-probe.ps1 -MainProfile ../../model-qwen3-8-27b/ollama-profile.fast.json -SecondProfile ../../model-deepseek-r1-32b/ollama-profile.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $MainProfile,
    [Parameter(Mandatory)] [string] $SecondProfile,
    [ValidateRange(1, 5)] [int] $Rounds = 3
)

$ErrorActionPreference = 'Stop'

function Invoke-Short($pd) {
    $options = @{ num_ctx = $pd.num_ctx; num_predict = 60 }
    foreach ($k in 'temperature', 'top_p', 'top_k', 'min_p', 'presence_penalty') { if ($null -ne $pd.$k) { $options[$k] = $pd.$k } }
    $body = @{ model = $pd.model; stream = $false; keep_alive = '5m'; options = $options; messages = @(@{ role = 'user'; content = 'List three habits of a tidy research notebook, one line each.' }) }
    if ($null -ne $pd.think) { $body.think = [bool]$pd.think }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod -Uri 'http://localhost:11434/api/chat' -Method Post -Body ($body | ConvertTo-Json -Depth 8) -ContentType 'application/json' -TimeoutSec 600
    $sw.Stop()
    [pscustomobject]@{ load_s = [math]::Round($r.load_duration / 1e9, 1); total_s = [math]::Round($sw.Elapsed.TotalSeconds, 1); gen_tok_s = [math]::Round($r.eval_count / ($r.eval_duration / 1e9), 1) }
}

# What is loaded right now, and where it runs.
function Get-Loaded {
    $lines = @(ollama ps | Select-Object -Skip 1 | Where-Object { $_.Trim() })
    @($lines | ForEach-Object { [pscustomobject]@{ model = ($_ -split '\s+')[0]; placement = [regex]::Match($_, '\d+%(/\d+%)? (CPU/GPU|GPU|CPU)').Value } })
}
function Format-Loaded($loaded) { if (-not $loaded) { 'nothing loaded' } else { ($loaded | ForEach-Object { "$($_.model) [$($_.placement)]" }) -join ' + ' } }
function Unload-All { foreach ($m in @(Get-Loaded).model) { $null = Invoke-RestMethod -Uri 'http://localhost:11434/api/generate' -Method Post -Body (@{ model = $m; keep_alive = 0 } | ConvertTo-Json) -ContentType 'application/json' }; Start-Sleep -Seconds 3 }

$main = Get-Content -Raw $MainProfile | ConvertFrom-Json
$second = Get-Content -Raw $SecondProfile | ConvertFrom-Json
if ($main.model -eq $second.model) { throw 'Pass two different models.' }

Unload-All
$rows = @()
$cold = Invoke-Short $main; $rows += [pscustomobject]@{ stage = 'main, first load'; round = 0; load_s = $cold.load_s; total_s = $cold.total_s; gen_tok_s = $cold.gen_tok_s; loaded = (Format-Loaded (Get-Loaded)) }
$warm = 1..2 | ForEach-Object { Invoke-Short $main }
$rows += [pscustomobject]@{ stage = 'main, warm'; round = 0; load_s = ($warm | Measure-Object load_s -Average).Average; total_s = ($warm | Measure-Object total_s -Average).Average; gen_tok_s = ($warm | Measure-Object gen_tok_s -Average).Average; loaded = (Format-Loaded (Get-Loaded)) }
for ($round = 1; $round -le $Rounds; $round++) {
    $s = Invoke-Short $second; $rows += [pscustomobject]@{ stage = 'second, main was loaded'; round = $round; load_s = $s.load_s; total_s = $s.total_s; gen_tok_s = $s.gen_tok_s; loaded = (Format-Loaded (Get-Loaded)) }
    $m = Invoke-Short $main;   $rows += [pscustomobject]@{ stage = 'main, after second'; round = $round; load_s = $m.load_s; total_s = $m.total_s; gen_tok_s = $m.gen_tok_s; loaded = (Format-Loaded (Get-Loaded)) }
}
Unload-All

$rows | Format-Table stage, round, @{ n = 'load_s'; e = { [math]::Round($_.load_s, 1) } }, @{ n = 'total_s'; e = { [math]::Round($_.total_s, 1) } }, @{ n = 'gen_tok_s'; e = { [math]::Round($_.gen_tok_s, 1) } }, loaded -AutoSize | Out-String -Width 220

$warmRow = $rows | Where-Object stage -eq 'main, warm'
$after = @($rows | Where-Object stage -eq 'main, after second'); $sec = @($rows | Where-Object stage -like 'second*')
'=== Summary ==='
"Main model, warm:                  {0:N1} tokens/s" -f $warmRow.gen_tok_s
"Main model after the second ran:   reload {0:N1} s, then {1:N1} tokens/s ({2:P0} of warm speed)" -f ($after | Measure-Object load_s -Average).Average, ($after | Measure-Object gen_tok_s -Average).Average, (($after | Measure-Object gen_tok_s -Average).Average / $warmRow.gen_tok_s)
"Second model, main was loaded:     load {0:N1} s" -f ($sec | Measure-Object load_s -Average).Average
"Extra time per excursion to the second model (both loads): {0:N1} s, before the second model's own work" -f ((($after | Measure-Object load_s -Average).Average) + (($sec | Measure-Object load_s -Average).Average))
"Both loaded together after the second ran: $(if (@($sec.loaded | Where-Object { $_ -match ' \+ ' }).Count) { 'yes' } else { 'no' })"
"Main model placement after reload: $((($after.loaded | Sort-Object -Unique) -join '; '))"
