<#
.SYNOPSIS
  Cleanly restart Ollama on Windows and report the settings the server started with.

.DESCRIPTION
  Stopping only "ollama" leaves its llama-server model runners alive, still holding GPU
  memory, so the next model load spills onto the CPU. This stops all three process types,
  starts the Ollama app again, optionally preloads a model, and prints the server's
  context length and bind address from its log.

.EXAMPLE
  ./restart-ollama.ps1 -Preload qwen3.8:27b
#>
[CmdletBinding()]
param(
    [string] $Preload,
    [string] $KeepAlive = '30m'
)

$ErrorActionPreference = 'Stop'
# A stale OLLAMA_HOST in this shell would point the restarted app and the CLI at the wrong address.
$env:OLLAMA_HOST = [Environment]::GetEnvironmentVariable('OLLAMA_HOST', 'User')
if (-not $env:OLLAMA_HOST) { [Environment]::SetEnvironmentVariable('OLLAMA_HOST', $null, 'Process') }

Get-Process 'ollama app', 'ollama', 'llama-server' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 4
Start-Process "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"

$deadline = (Get-Date).AddSeconds(45)
do { Start-Sleep -Seconds 2; $listen = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue } until ($listen -or (Get-Date) -gt $deadline)
if (-not $listen) { throw 'Ollama did not start listening on port 11434 within 45 seconds.' }
Start-Sleep -Seconds 2

$config = Get-Content "$env:LOCALAPPDATA\Ollama\server.log" | Select-String 'server config' | Select-Object -Last 1
$context = [regex]::Match($config.Line, 'OLLAMA_CONTEXT_LENGTH:(\d+)').Groups[1].Value
$bindHost = [regex]::Match($config.Line, 'OLLAMA_HOST:([^ \]]+)').Groups[1].Value
"Listening on: $(($listen | ForEach-Object LocalAddress) -join ', ')"
# Ollama's API has no authentication. Anything other than loopback exposes it to the network.
$exposed = @($listen | Where-Object { $_.LocalAddress -notin '127.0.0.1', '::1' })
if ($exposed) { Write-Warning "Ollama is listening on $(($exposed.LocalAddress | Sort-Object -Unique) -join ', '), not only on loopback. Anyone who can reach this machine can use it and read prompts. Unset OLLAMA_HOST (see security-baseline) unless you meant this." }
"Server context length: $context"
"Server bind address: $bindHost"

if ($Preload) {
    $body = @{ model = $Preload; keep_alive = $KeepAlive } | ConvertTo-Json
    $null = Invoke-RestMethod -Uri 'http://localhost:11434/api/generate' -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 180
    ollama ps
}
"llama-server processes: $(@(Get-Process llama-server -ErrorAction SilentlyContinue).Count)"
