<#
.SYNOPSIS
  Send one bounded task to a local Ollama model and print its reply.

.DESCRIPTION
  Used by an orchestrator agent (Claude Code, Copilot, etc.) to delegate work to the
  local worker model. Every call starts from a fresh context: pass the task packet in
  -PromptFile, never a whole chat history. Talks only to localhost (the loopback address, never the network).

  Usage records (model, token counts, seconds) are appended to a local JSONL log that
  is git-ignored. Prompts and replies are never logged.

.EXAMPLE
  ./invoke-local-model.ps1 -PromptFile task.md
  ./invoke-local-model.ps1 -PromptFile review.md -SchemaFile findings.schema.json -Samples 2
#>
[CmdletBinding(DefaultParameterSetName='Invoke')]
param(
    [Parameter(Mandatory,ParameterSetName='Invoke')] [string] $PromptFile,
    [Parameter(Mandatory,ParameterSetName='SelfTest')] [switch] $SelfTest,
    [string] $SystemFile,
    # JSON schema file; when set, Ollama constrains the reply to that schema.
    [string] $SchemaFile,
    [string] $Model,
    # Independent samples of the same packet. Useful for diverse review candidates.
    [ValidateRange(1, 5)] [int] $Samples = 1,
    [int] $NumCtx = 32768,
    [double] $Temperature,
    [double] $TopP,
    [int] $TopK,
    [double] $MinP,
    [int] $TimeoutSec = 900,
    [ValidateRange(1,16384)] [int] $MaxOutputTokens = 8192,
    # Thinking mode when no profile decides it: default = the model's own, on, or off. on or off also overrides a profile's think setting.
    # (Not named -Think: PowerShell variable names are case-insensitive and $think is used below.)
    [ValidateSet('default','on','off')] [string] $ThinkMode = 'default',
    # Thinking effort for a model that offers levels (the qwen3.8 27b alias lists low, medium and xhigh). off and on are the Boolean switch; a level turns thinking on at that effort.
    # Wins over -ThinkMode and over the profile. Whether a given model honours a level is measured, not assumed: see think-level-probe.ps1.
    [ValidateSet('default','off','on','low','medium','xhigh')] [string] $ThinkLevel = 'default',
    [ValidateRange(1,65536)] [int] $MaxReplyBytes = 65536,
    # A model profile (ollama-profile.json in a model's profile skill) supplying the model name
    # and sampling settings. Parameters passed explicitly on the command line still win.
    # Default: LOCAL_WORKER_PROFILE if set. With no profile, no -Model and no LOCAL_WORKER_MODEL there is no
    # local worker and delegation is cloud-only; nothing falls back to a particular model.
    [string] $ProfileFile = $env:LOCAL_WORKER_PROFILE,
    [string] $LogFile = (Join-Path $PSScriptRoot '../../../../.loop-logs/local-model-usage.jsonl'),
    # Opt-in: save the model's thinking text here (local file; the thinking can quote the packet, so keep it out of repos).
    [string] $ThinkingFile,
    # A short label written into this call's usage entry (which task it was for), so the central log can be grouped by task later. Default: LOCAL_WORKER_TAG.
    [string] $Tag = $env:LOCAL_WORKER_TAG
)

$ErrorActionPreference = 'Stop'

function Assert-LocalModelName([string] $Name) {
    if ($Name -match ':cloud$|-cloud$|^https?://') { throw 'Use a reviewed cloud handoff, not the local invocation helper, for cloud models or registry URLs' }
}

function Get-CheckedReply($Reply, [int] $Limit, [string] $SchemaText) {
    if ($Reply.done -isnot [bool] -or -not $Reply.done) { throw 'Incomplete model response; do not dispatch further calls until termination is resolved' }
    if ($Reply.error) { throw 'Ollama returned an error; no model reply accepted' }
    if ($Reply.done_reason -eq 'length') { throw "Generated-token limit reached ($MaxOutputTokens output tokens; reasoning tokens count). Use a fast profile (think false) or raise -MaxOutputTokens (up to 16384). Truncated artifacts are not accepted" }
    $content = $Reply.message.content
    if ($content -isnot [string] -or [string]::IsNullOrWhiteSpace($content)) { throw 'Model response contains no usable text' }
    if ([Text.Encoding]::UTF8.GetByteCount($content) -gt $Limit) { throw 'Final model reply exceeds the configured byte limit' }
    if ($SchemaText -and -not (Test-Json -Json $content -Schema $SchemaText -ErrorAction Stop)) { throw 'Model response failed the requested JSON schema' }
    return $content
}

# The profile's think key may be a Boolean or a level name; an explicit -ThinkLevel beats -ThinkMode beats the profile. Returns $null (leave it to the model), a Boolean or a level string.
function Resolve-Think($ProfileThink, [string] $Mode, [string] $Level) {
    $think = $null
    if ($null -ne $ProfileThink) {
        if ($ProfileThink -is [bool]) { $think = $ProfileThink }
        elseif ($ProfileThink -is [string] -and $ProfileThink -cin 'low', 'medium', 'xhigh') { $think = $ProfileThink }
        else { throw "Unknown think value in the profile: '$ProfileThink' (use true, false, low, medium or xhigh)" }
    }
    if ($Mode -ne 'default') { $think = ($Mode -eq 'on') }
    if ($Level -ne 'default') { $Level = $Level.ToLowerInvariant(); $think = if ($Level -eq 'on') { $true } elseif ($Level -eq 'off') { $false } else { $Level } }
    return $think
}

if ($SelfTest) {
    $valid = @{done=$true;done_reason='stop';message=@{content='valid reply'}}
    if ((Get-CheckedReply $valid 64 '') -cne 'valid reply') { throw 'Valid reply rejected' }
    $schema = '{"type":"object","properties":{"answer":{"type":"integer"}},"required":["answer"],"additionalProperties":false}'
    if ((Get-CheckedReply @{done=$true;message=@{content='{"answer":42}'}} 64 $schema) -cne '{"answer":42}') { throw 'Valid JSON reply rejected' }
    $cases = @(
        @{name='missing completion';reply=@{message=@{content='reply'}}},
        @{name='incomplete completion';reply=@{done=$false;message=@{content='reply'}}},
        @{name='string completion not trusted';reply=@{done='true';message=@{content='reply'}}},
        @{name='server error';reply=@{done=$true;error='error';message=@{content='reply'}}},
        @{name='token-truncated artifact';reply=@{done=$true;done_reason='length';message=@{content='partial'}}},
        @{name='empty reply';reply=@{done=$true;message=@{content=' '}}},
        @{name='nontext reply';reply=@{done=$true;message=@{content=42}}},
        @{name='oversized reply';reply=@{done=$true;message=@{content=('x'*65)}}},
        @{name='invalid JSON';reply=@{done=$true;message=@{content='{broken'}};schema=$schema},
        @{name='wrong JSON schema';reply=@{done=$true;message=@{content='{"answer":"wrong"}'}};schema=$schema}
    )
    foreach ($case in $cases) {
        $rejected=$false
        try { $null=Get-CheckedReply $case.reply 64 $case.schema } catch { $rejected=$true }
        if (-not $rejected) { throw "Invalid response accepted: $($case.name)" }
        "PASS: $($case.name)"
    }
    $capMsg = ''
    try { $null = Get-CheckedReply @{done=$true;done_reason='length';message=@{content='partial'}} 64 '' } catch { $capMsg = $_.Exception.Message }
    if ($capMsg -notmatch 'MaxOutputTokens' -or $capMsg -notmatch '8192') { throw "The token-cap error must name the cap and how to raise it, got: $capMsg" }
    'PASS: the token-cap error names the cap and how to raise it'
    Assert-LocalModelName 'test-local:small'
    foreach ($name in 'test:cloud','test:small-cloud','https://registry.invalid/model') {
        $rejected=$false
        try { Assert-LocalModelName $name } catch { $rejected=$true }
        if (-not $rejected) { throw 'Cloud/URL model name accepted by local helper' }
    }
    $thinkCases = @(
        @{name='nothing set leaves thinking to the model'; profile=$null; mode='default'; level='default'; want=$null},
        @{name='a Boolean profile value is kept'; profile=$true; mode='default'; level='default'; want=$true},
        @{name='a level in the profile is kept'; profile='low'; mode='default'; level='default'; want='low'},
        @{name='ThinkMode off beats the profile'; profile='xhigh'; mode='off'; level='default'; want=$false},
        @{name='ThinkLevel beats ThinkMode and the profile'; profile=$false; mode='off'; level='medium'; want='medium'},
        @{name='ThinkLevel off is the Boolean false'; profile=$true; mode='default'; level='off'; want=$false},
        @{name='ThinkLevel on is the Boolean true'; profile=$null; mode='default'; level='on'; want=$true}
    )
    foreach ($c in $thinkCases) {
        $got = Resolve-Think $c.profile $c.mode $c.level
        if ($null -eq $c.want) { if ($null -ne $got) { throw "Think case failed: $($c.name) (got '$got')" } }
        elseif ($got -isnot $c.want.GetType() -or $got -ne $c.want) { throw "Think case failed: $($c.name) (got '$got')" }
        "PASS: $($c.name)"
    }
    foreach ($bad in 'high', 'LOW ', 3, '') {
        $rejected = $false
        try { $null = Resolve-Think $bad 'default' 'default' } catch { $rejected = $true }
        if (-not $rejected) { throw "An unknown think value in a profile was accepted: '$bad'" }
        "PASS: a profile think value of '$bad' is rejected"
    }
    'All 28 local reply/name/think tests passed; no profile, model, GPU or network required'
    exit 0
}

$think = $null
$presencePenalty = $null
if ($ProfileFile) {
    $profileData = Get-Content -Raw $ProfileFile | ConvertFrom-Json
    $map = @{ model = 'Model'; num_ctx = 'NumCtx'; temperature = 'Temperature'; top_p = 'TopP'; top_k = 'TopK'; min_p = 'MinP' }
    foreach ($key in $map.Keys) {
        $param = $map[$key]
        if ($null -ne $profileData.$key -and -not $PSBoundParameters.ContainsKey($param)) { Set-Variable -Name $param -Value $profileData.$key }
    }
    if ($null -ne $profileData.presence_penalty) { $presencePenalty = [double]$profileData.presence_penalty }
}
$think = Resolve-Think $(if ($profileData) { $profileData.think } else { $null }) $ThinkMode $ThinkLevel
# LOCAL_WORKER_MODEL overrides the profile's model name (but not an explicit -Model).
if ($env:LOCAL_WORKER_MODEL -and -not $PSBoundParameters.ContainsKey('Model')) { $Model = $env:LOCAL_WORKER_MODEL }
if (-not $Model) { throw 'No local worker is configured, so delegation is cloud-only. To use a local model, set LOCAL_WORKER_MODEL (your preferred model, for example in the lab .env) or LOCAL_WORKER_PROFILE, or pass -Model / -ProfileFile.' }
Assert-LocalModelName $Model

# Never hand a model secrets (security-baseline section 9). Catch the obvious mistake of
# passing a credential file itself as the task packet.
foreach ($f in @($PromptFile, $SystemFile) | Where-Object { $_ }) {
    if ((Split-Path -Leaf $f) -match '^\.env($|\.)|\.(pem|key|p12|pfx|ppk)$|^id_(rsa|ed25519)|^credentials\.json$|^\.npmrc$') {
        if ((Split-Path -Leaf $f) -notmatch '^\.env\.(example|sample)$') { throw "Refusing to send '$f' to a model: it looks like a credential file." }
    }
}

$messages = @()
if ($SystemFile) { $messages += @{ role = 'system'; content = (Get-Content -Raw $SystemFile) } }
$prompt = Get-Content -Raw $PromptFile

$format = $null
$schemaText = $null
if ($SchemaFile) {
    $schemaText = Get-Content -Raw $SchemaFile
    $format = $schemaText | ConvertFrom-Json -AsHashtable
    # Ollama recommends also showing the schema in the prompt to ground the reply.
    $prompt += "`n`nReply with JSON only, matching this schema:`n$schemaText"
}
$messages += @{ role = 'user'; content = $prompt }

$logDir = Split-Path $LogFile
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

for ($i = 1; $i -le $Samples; $i++) {
    $body = @{
        model      = $Model
        stream     = $false
        keep_alive = '15m'
        messages   = $messages
        options    = @{ num_ctx = $NumCtx; num_predict = $MaxOutputTokens }
    }
    # Send only the sampling settings that were set; otherwise the model's own defaults apply.
    foreach ($o in @(@('temperature', 'Temperature'), @('top_p', 'TopP'), @('top_k', 'TopK'), @('min_p', 'MinP'))) {
        if ($PSBoundParameters.ContainsKey($o[1]) -or ($profileData -and $null -ne $profileData.($o[0]))) { $body.options[$o[0]] = (Get-Variable -Name $o[1] -ValueOnly) }
    }
    if ($format) { $body.format = $format }
    if ($null -ne $think) { $body.think = $think }
    if ($null -ne $presencePenalty) { $body.options.presence_penalty = $presencePenalty }

    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-RestMethod -Uri 'http://localhost:11434/api/chat' -Method Post `
        -Body ($body | ConvertTo-Json -Depth 32) -ContentType 'application/json' -TimeoutSec $TimeoutSec
    $sw.Stop()

    @{
        ts            = (Get-Date).ToUniversalTime().ToString('o')
        model         = $Model
        prompt_tokens = $r.prompt_eval_count
        output_tokens = $r.eval_count
        seconds       = [math]::Round($sw.Elapsed.TotalSeconds, 1)
        structured    = [bool]$format
        # $null when no setting was sent: the model then uses its own default (the qwen3.8 alias thinks by default), so it is not the same as false
        tag           = if ($Tag) { $Tag } else { $null }
        think         = if ($null -eq $think) { $null } else { [bool]$think }
        think_level   = if ($think -is [string]) { $think } else { $null }
        done_reason   = $r.done_reason
        # output_tokens includes reasoning tokens when thinking is on.
        thinking_chars = if ($r.message.thinking) { $r.message.thinking.Length } else { 0 }
    } | ConvertTo-Json -Compress | Add-Content -Path $LogFile
    if ($ThinkingFile -and $r.message.thinking) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent ([IO.Path]::GetFullPath($ThinkingFile))) | Out-Null
        Set-Content -LiteralPath $ThinkingFile -Value $r.message.thinking -Encoding utf8
    }
    $content = Get-CheckedReply $r $MaxReplyBytes $schemaText
    if ($Samples -gt 1) { "===== sample $i of $Samples =====" }
    $content
}
