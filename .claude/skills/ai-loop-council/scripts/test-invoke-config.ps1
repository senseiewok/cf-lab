# Test: with no local worker configured, invoke-local-model.ps1 refuses (cloud-only);
# a configured LOCAL_WORKER_MODEL is picked up. No Ollama, network or model is contacted.
param([string] $Script = (Join-Path $PSScriptRoot 'invoke-local-model.ps1'))
$ErrorActionPreference = 'Stop'
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('invoke-config-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $tmp | Out-Null
Set-Content (Join-Path $tmp 'p.md') 'hello' -Encoding utf8
$fail = @(); $n = 0
function Run([hashtable] $envVars, [string[]] $extra = @()) {
    $keys = 'LOCAL_WORKER_MODEL', 'LOCAL_WORKER_PROFILE'
    $saved = @{}; foreach ($k in $keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process'); [Environment]::SetEnvironmentVariable($k, $null, 'Process') }
    foreach ($k in $envVars.Keys) { [Environment]::SetEnvironmentVariable($k, $envVars[$k], 'Process') }
    try { $o = & pwsh -NoProfile -File $Script -PromptFile (Join-Path $tmp 'p.md') @extra 2>&1 | Out-String; return @{ Code = $LASTEXITCODE; Out = $o } }
    finally { foreach ($k in $keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') } }
}
function Check([string] $name, [bool] $ok, [string] $detail = '') { $script:n++; Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fail += $name } }
try {
    $r = Run @{}
    Check 'nothing configured: refuses and says cloud-only' ($r.Code -ne 0 -and $r.Out -match 'cloud-only') $r.Out
    Check 'nothing configured: does not silently pick Qwen' (-not ($r.Out -match 'qwen' -and $r.Out -match 'Invoke-RestMethod')) $r.Out
    $r = Run @{ LOCAL_WORKER_MODEL = 'preferred:cloud' }
    Check 'LOCAL_WORKER_MODEL is picked up (a cloud-looking name is then refused by the local helper, proving it was read)' ($r.Code -ne 0 -and $r.Out -match 'reviewed cloud handoff') $r.Out
    $r = Run @{} @('-Model', 'x:cloud')
    Check 'an explicit -Model works without any env' ($r.Code -ne 0 -and $r.Out -match 'reviewed cloud handoff') $r.Out
    $o = & pwsh -NoProfile -File $Script -SelfTest 2>&1 | Out-String
    Check 'the self-test passes and covers the token-cap message (it names the cap and how to raise it)' ($LASTEXITCODE -eq 0 -and $o -match 'token-cap error names the cap') $o
    # the four 64K profiles: the model-card sampling sets, one thinking setting each, and the context the alias is built with
    $profDir = Join-Path $PSScriptRoot '../../model-qwen3-8-27b'
    $think = @{ temperature = 1.0; top_p = 0.95; top_k = 20; min_p = 0.0; presence_penalty = 0.0 }
    $fastSet = @{ temperature = 0.7; top_p = 0.8; top_k = 20; min_p = 0.0; presence_penalty = 1.5 }
    foreach ($case in @(@('ollama-profile.64k.fast.json', $false, $fastSet), @('ollama-profile.64k.json', $true, $think))) {
        $f = Join-Path $profDir $case[0]
        $ok = Test-Path $f
        $p = if ($ok) { Get-Content -Raw $f | ConvertFrom-Json } else { $null }
        $good = $ok -and $p.model -ceq 'qwen3.8:27b-64k' -and $p.num_ctx -eq 65536 -and $p.think -ceq $case[1]
        if ($good) { foreach ($k in $case[2].Keys) { if ([double]$p.$k -ne [double]$case[2][$k]) { $good = $false } } }
        Check "profile $($case[0]): 64K alias, think $($case[1]), the model-card sampling set" $good $f
    }
} finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
