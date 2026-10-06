[CmdletBinding()]
param(
    [ValidateSet('Local','Cloud','Unknown')] [string] $Runtime = 'Unknown',
    [ValidateSet('Unknown','TrustedRuntime','UserConfiguration')] [string] $RuntimeEvidence = 'Unknown',
    [switch] $CrossProviderDelegation,
    [ValidateSet('Routine','Implementation','Planning','Architecture','Research','HighRisk')] [string] $TaskKind = 'Routine',
    [switch] $Difficult,
    [switch] $NeedsIndependentReview,
    [switch] $LocalAvailable,
    [switch] $LocalThinkingAvailable,
    [switch] $CloudAvailable,
    [switch] $CloudApproved,
    [ValidateSet('Unreviewed','ApprovedPublic','ApprovedSanitized','Prohibited')] [string] $CloudData = 'Unreviewed',
    [ValidateRange(0,9)] [int] $FastFailures = 0,
    [ValidateRange(0,9)] [int] $ThinkingFailures = 0,
    [ValidateRange(0,9)] [int] $ThinkingCallsUsed = 0,
    [ValidateRange(0,9)] [int] $LocalCallsUsed = 0,
    [ValidateRange(0,9)] [int] $CloudCallsUsed = 0,
    [ValidateRange(0,9)] [int] $LocalCallBudget = 3,
    [ValidateRange(0,1)] [int] $CloudCallBudget = 1,
    [ValidateSet('NotRun','Passed','Failed')] [string] $Validation = 'NotRun',
    [switch] $RequiredReviewComplete,
    [switch] $ContainmentUnresolved,
    [switch] $SelfTest
)

$ErrorActionPreference = 'Stop'

function Get-CrossProviderSetting([bool] $Explicit, [bool] $Value, [string] $EnvironmentValue) {
    if ($Explicit) { return $Value }
    if ([string]::IsNullOrWhiteSpace($EnvironmentValue)) { return $false }
    switch ($EnvironmentValue.Trim().ToLowerInvariant()) {
        'true' { return $true }
        'false' { return $false }
        default { throw 'COUNCIL_CROSS_PROVIDER_DELEGATION must be true or false' }
    }
}

function Select-WorkRoute([hashtable] $State) {
    $knownRuntime = if ($State.RuntimeEvidence -in @('TrustedRuntime','UserConfiguration')) { $State.Runtime } else { 'Unknown' }
    $localRemaining = [Math]::Max(0, $State.LocalCallBudget - $State.LocalCallsUsed)
    $cloudRemaining = [Math]::Max(0, [Math]::Min(1, $State.CloudCallBudget) - $State.CloudCallsUsed)
    $wantsThinking = $State.LocalThinkingAvailable -and ($State.FastFailures -ge 2 -or $State.TaskKind -in @('Planning','Architecture','Research'))
    $action = 'blocked'
    $target = 'none'
    $reason = 'No usable, approved route'

    if ($State.ContainmentUnresolved) {
        $reason = 'Resolve cancellation or containment before dispatching anything else'
    }
    elseif ($State.Validation -eq 'Passed' -and $State.RequiredReviewComplete) {
        $action = 'complete'
        $reason = 'Frozen checks and required review passed; no more model calls'
    }
    elseif (-not $State.CrossProviderDelegation -and $knownRuntime -eq 'Unknown') {
        $reason = 'Cross-provider delegation is disabled and the current provider is unknown'
    }
    else {
        $needsCloud = $State.Difficult -or $State.NeedsIndependentReview -or
            $State.TaskKind -eq 'HighRisk' -or $State.ThinkingFailures -gt 0 -or
            -not $State.LocalAvailable -or $localRemaining -eq 0 -or
            ($wantsThinking -and $State.ThinkingCallsUsed -ge 1) -or
            ($knownRuntime -eq 'Cloud' -and -not $State.CrossProviderDelegation) -or
            ($State.FastFailures -ge 2 -and -not $State.LocalThinkingAvailable)
        if ($needsCloud) {
            if (-not $State.CrossProviderDelegation -and $knownRuntime -ne 'Cloud') { $reason = 'Cross-provider delegation is disabled; cloud escalation is blocked' }
            elseif ($cloudRemaining -eq 0) { $reason = 'Cloud call budget exhausted; stop instead of bouncing providers' }
            elseif (-not $State.CloudAvailable) { $reason = 'Cloud adapter unavailable; prepare a manual handoff without transmitting it' }
            elseif (-not $State.CloudApproved) { $reason = 'Cloud use requires user approval' }
            elseif ($State.CloudData -notin @('ApprovedPublic','ApprovedSanitized')) { $reason = 'Cloud packet has not passed the data-sharing review' }
            else {
                $target = 'cloud'
                $action = if ($knownRuntime -eq 'Cloud') { 'continue-cloud' } else { 'handoff-cloud' }
                $reason = 'One bounded cloud plan, evidence synthesis, or review; verify the result before local execution'
            }
        }
        else {
            $target = if ($wantsThinking) { 'local-thinking' } else { 'local-fast' }
            $action = if ($knownRuntime -eq 'Local') { 'continue-local' } else { 'delegate-local' }
            $reason = 'Use the configured local capability; verifier feedback controls escalation'
        }
    }
    [pscustomobject]@{
        action = $action
        target = $target
        reason = $reason
        runtime = $knownRuntime
        cross_provider_delegation = [bool]$State.CrossProviderDelegation
        local_calls_remaining = $localRemaining
        cloud_calls_remaining = $cloudRemaining
        status = 'decision only; no model calls, provider detection, or permission changes'
    }
}

if ($SelfTest) {
    $defaults = @{
        Runtime='Unknown';RuntimeEvidence='Unknown';TaskKind='Routine';Difficult=$false
        CrossProviderDelegation=$true
        NeedsIndependentReview=$false;LocalAvailable=$true;LocalThinkingAvailable=$true
        CloudAvailable=$true;CloudApproved=$false;CloudData='Unreviewed'
        FastFailures=0;ThinkingFailures=0;ThinkingCallsUsed=0;LocalCallsUsed=0;CloudCallsUsed=0
        LocalCallBudget=3;CloudCallBudget=1;Validation='NotRun';RequiredReviewComplete=$false
        ContainmentUnresolved=$false
    }
    $tests = @(
        @{name='disabled keeps a local agent local';changes=@{CrossProviderDelegation=$false;Runtime='Local';RuntimeEvidence='TrustedRuntime'};action='continue-local';target='local-fast'},
        @{name='disabled keeps approved cloud work cloud';changes=@{CrossProviderDelegation=$false;Runtime='Cloud';RuntimeEvidence='TrustedRuntime';CloudApproved=$true;CloudData='ApprovedPublic'};action='continue-cloud';target='cloud'},
        @{name='disabled blocks local to cloud escalation';changes=@{CrossProviderDelegation=$false;Runtime='Local';RuntimeEvidence='TrustedRuntime';Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic'};action='blocked';target='none'},
        @{name='disabled blocks unknown provider routing';changes=@{CrossProviderDelegation=$false};action='blocked';target='none'},
        @{name='disabled still enforces cloud approval';changes=@{CrossProviderDelegation=$false;Runtime='Cloud';RuntimeEvidence='TrustedRuntime'};action='blocked';target='none'},
        @{name='disabled still enforces cloud data review';changes=@{CrossProviderDelegation=$false;Runtime='Cloud';RuntimeEvidence='TrustedRuntime';CloudApproved=$true};action='blocked';target='none'},
        @{name='unknown backend delegates local';changes=@{};action='delegate-local';target='local-fast'},
        @{name='cloud agent offloads routine work';changes=@{Runtime='Cloud';RuntimeEvidence='TrustedRuntime'};action='delegate-local';target='local-fast'},
        @{name='local agent stays local';changes=@{Runtime='Local';RuntimeEvidence='TrustedRuntime'};action='continue-local';target='local-fast'},
        @{name='self-claimed provider is unknown';changes=@{Runtime='Cloud'};action='delegate-local';target='local-fast'},
        @{name='explicit provider config is usable';changes=@{Runtime='Local';RuntimeEvidence='UserConfiguration'};action='continue-local';target='local-fast'},
        @{name='CPU or small model needs no GPU flag';changes=@{LocalThinkingAvailable=$false};action='delegate-local';target='local-fast'},
        @{name='easy planning remains local';changes=@{TaskKind='Planning'};action='delegate-local';target='local-thinking'},
        @{name='grounded research stays local';changes=@{TaskKind='Research'};action='delegate-local';target='local-thinking'},
        @{name='routine architecture stays local';changes=@{TaskKind='Architecture'};action='delegate-local';target='local-thinking'},
        @{name='one failed fast attempt stays cheap';changes=@{FastFailures=1;LocalCallsUsed=1};action='delegate-local';target='local-fast'},
        @{name='two fast failures use thinking';changes=@{FastFailures=2;LocalCallsUsed=2};action='delegate-local';target='local-thinking'},
        @{name='spent planning thinking call blocks retry';changes=@{TaskKind='Planning';ThinkingCallsUsed=1;LocalCallsUsed=1};action='blocked';target='none'},
        @{name='spent thinking call can hand off once';changes=@{FastFailures=2;ThinkingCallsUsed=1;LocalCallsUsed=2;CloudApproved=$true;CloudData='ApprovedPublic'};action='handoff-cloud';target='cloud'},
        @{name='spent thinking still permits routine fast work';changes=@{ThinkingCallsUsed=1;LocalCallsUsed=1};action='delegate-local';target='local-fast'},
        @{name='no thinking needs cloud permission';changes=@{FastFailures=2;LocalCallsUsed=2;LocalThinkingAvailable=$false};action='blocked';target='none'},
        @{name='hard plan without approval blocked';changes=@{TaskKind='Planning';Difficult=$true};action='blocked';target='none'},
        @{name='approval alone does not approve data';changes=@{Difficult=$true;CloudApproved=$true};action='blocked';target='none'},
        @{name='secrets never use automatic cloud';changes=@{Difficult=$true;CloudApproved=$true;CloudData='Prohibited'};action='blocked';target='none'},
        @{name='local to approved public cloud';changes=@{Runtime='Local';RuntimeEvidence='TrustedRuntime';Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic'};action='handoff-cloud';target='cloud'},
        @{name='cloud agent handles approved hard gap';changes=@{Runtime='Cloud';RuntimeEvidence='TrustedRuntime';Difficult=$true;CloudApproved=$true;CloudData='ApprovedSanitized'};action='continue-cloud';target='cloud'},
        @{name='unknown provider needs explicit handoff';changes=@{Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic'};action='handoff-cloud';target='cloud'},
        @{name='cloud unavailable never invents adapter';changes=@{Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic';CloudAvailable=$false};action='blocked';target='none'},
        @{name='no Ollama and no approval blocks';changes=@{LocalAvailable=$false};action='blocked';target='none'},
        @{name='no Ollama uses approved cloud';changes=@{LocalAvailable=$false;CloudApproved=$true;CloudData='ApprovedPublic'};action='handoff-cloud';target='cloud'},
        @{name='neither provider blocks explicitly';changes=@{LocalAvailable=$false;CloudAvailable=$false};action='blocked';target='none'},
        @{name='spent cloud call stops escalation';changes=@{Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic';CloudCallsUsed=1};action='blocked';target='none'},
        @{name='zero cloud budget cannot dispatch';changes=@{Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic';CloudCallBudget=0};action='blocked';target='none'},
        @{name='function clamps oversized cloud budget';changes=@{Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic';CloudCallsUsed=1;CloudCallBudget=9};action='blocked';target='none'},
        @{name='spent local budget requests cloud once';changes=@{LocalCallsUsed=3;CloudApproved=$true;CloudData='ApprovedPublic'};action='handoff-cloud';target='cloud'},
        @{name='both budgets exhausted stops';changes=@{LocalCallsUsed=3;CloudCallsUsed=1;CloudApproved=$true;CloudData='ApprovedPublic'};action='blocked';target='none'},
        @{name='thinking failure requests approved cloud';changes=@{ThinkingFailures=1;CloudApproved=$true;CloudData='ApprovedSanitized'};action='handoff-cloud';target='cloud'},
        @{name='high risk is not a cheap local clearance';changes=@{TaskKind='HighRisk'};action='blocked';target='none'},
        @{name='independent review needs sharing review';changes=@{NeedsIndependentReview=$true;CloudApproved=$true};action='blocked';target='none'},
        @{name='passed checks and review stop calls';changes=@{Validation='Passed';RequiredReviewComplete=$true;Difficult=$true};action='complete';target='none'},
        @{name='model claim without checks not complete';changes=@{RequiredReviewComplete=$true};action='delegate-local';target='local-fast'},
        @{name='checks alone cannot skip required review';changes=@{Validation='Passed';NeedsIndependentReview=$true};action='blocked';target='none'},
        @{name='unresolved cancellation blocks local';changes=@{ContainmentUnresolved=$true};action='blocked';target='none'},
        @{name='unresolved cancellation blocks cloud';changes=@{ContainmentUnresolved=$true;Difficult=$true;CloudApproved=$true;CloudData='ApprovedPublic'};action='blocked';target='none'},
        @{name='cloud plan returns bounded work local';changes=@{Runtime='Cloud';RuntimeEvidence='TrustedRuntime';CloudCallsUsed=1;TaskKind='Implementation'};action='delegate-local';target='local-fast'}
    )
    foreach ($test in $tests) {
        $state = $defaults.Clone()
        foreach ($key in $test.changes.Keys) { $state[$key]=$test.changes[$key] }
        $result = Select-WorkRoute $state
        if ($result.action -ne $test.action -or $result.target -ne $test.target) {
            throw "$($test.name): expected $($test.action)/$($test.target); got $($result.action)/$($result.target)"
        }
        "PASS: $($test.name)"
    }
    $settingsTests = @(
        @{name='setting defaults off';explicit=$false;value=$false;environment='';expected=$false},
        @{name='environment enables delegation';explicit=$false;value=$false;environment='true';expected=$true},
        @{name='environment disables delegation';explicit=$false;value=$true;environment='false';expected=$false},
        @{name='explicit enable overrides environment';explicit=$true;value=$true;environment='false';expected=$true},
        @{name='explicit disable overrides environment';explicit=$true;value=$false;environment='true';expected=$false},
        @{name='invalid environment rejected';explicit=$false;value=$false;environment='yes';reject=$true},
        @{name='explicit override ignores invalid environment';explicit=$true;value=$false;environment='invalid';expected=$false}
    )
    foreach ($test in $settingsTests) {
        $rejected=$false; $result=$null
        try { $result=Get-CrossProviderSetting $test.explicit $test.value $test.environment } catch { $rejected=$true }
        if ($rejected -ne [bool]$test.reject -or (-not $rejected -and $result -ne $test.expected)) { throw "Setting failed: $($test.name)" }
        "PASS: $($test.name)"
    }
    "All $($tests.Count + $settingsTests.Count) routing/setting tests passed; no models, GPU, Ollama, credentials or network required"
    exit 0
}

$state = @{}
foreach ($key in 'Runtime','RuntimeEvidence','TaskKind','Difficult','NeedsIndependentReview','LocalAvailable','LocalThinkingAvailable','CloudAvailable','CloudApproved','CloudData','FastFailures','ThinkingFailures','ThinkingCallsUsed','LocalCallsUsed','CloudCallsUsed','LocalCallBudget','CloudCallBudget','Validation','RequiredReviewComplete','ContainmentUnresolved') {
    $state[$key] = Get-Variable -Name $key -ValueOnly
}
$state.CrossProviderDelegation = Get-CrossProviderSetting ($PSBoundParameters.ContainsKey('CrossProviderDelegation')) ([bool]$CrossProviderDelegation) $env:COUNCIL_CROSS_PROVIDER_DELEGATION
Select-WorkRoute $state | ConvertTo-Json