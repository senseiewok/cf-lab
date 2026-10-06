<#
.SYNOPSIS
  Check that the lab's local files folder (cf-lab-files) holds nothing it must not.

.DESCRIPTION
  The folder is not a git repository, agents can read it, and nothing reviews what is written there,
  so a key, a token, an email address or a private detail pasted into it would sit unseen. This
  checks five rules and prints one line per finding as `<rule>: <path relative to the folder>`.
  It never prints the text that matched, never writes, never touches the network, and reads only
  files under -Path.

    secret-file        a file anywhere under the folder named .env*, id_rsa*, id_ed25519*,
                       credentials.json, or ending .pem .key .p12 .pfx .ppk
    secret-content     a file under memory\ (not scratch\, not larger than 1 MB) that holds a private
                       key header, an sk-, ghp-, AKIA or xox token, or an email address
    git-dir            a .git folder or file anywhere under the folder
    memory-file-count  more than 3 files directly inside memory\
    private-term       a file under memory\ that holds, case-insensitively, a literal term from the
                       LAB_PRIVATE_TERMS variable (terms separated by ;). Keep that variable in the git-ignored
                       .env and load it with run-with-env.ps1; never write the terms into a repo.

  Exit codes: 0 clean, 1 findings, 2 usage error.

.EXAMPLE
  pwsh -NoProfile -File check-lab-files.ps1 -Path ..\..\..\..\..\cf-lab-files
  pwsh -NoProfile -File run-with-env.ps1 -- pwsh -NoProfile -File check-lab-files.ps1      # uses LAB_FILES and LAB_PRIVATE_TERMS from .env
  pwsh -NoProfile -File check-lab-files.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    [string] $Path,
    [switch] $SelfTest
)
$ErrorActionPreference = 'Stop'

$NamePattern = '(?i)^(\.env|id_rsa|id_ed25519)|\.(pem|key|p12|pfx|ppk)$|^credentials\.json$'
# Case-sensitive on purpose (.NET regex default): AKIA and xox tokens are upper/lower specific.
$ContentPatterns = [ordered]@{
    'private key header' = '-----BEGIN[ A-Z]*PRIVATE KEY-----'
    'sk- token'          = 'sk-[A-Za-z0-9]{20,}'
    'ghp_ token'         = 'ghp_[A-Za-z0-9]{30,}'
    'AWS key id'         = 'AKIA[0-9A-Z]{16}'
    'Slack token'        = 'xox[baprs]-[A-Za-z0-9-]{10,}'
    'email address'      = '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
}
# Non-personal addresses that legitimately appear in notes about commits (a Co-Authored-By trailer): noreply@host and
# id+name@users.noreply.github.com. They are removed before the content patterns run; every other address is still reported.
$AllowedEmailPattern = '(?i)\b(no-?reply@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|[A-Za-z0-9._%+-]+@users\.noreply\.github\.com)'
$MaxBytes = 1MB
$MaxMemoryFiles = 3

function Get-Rel([string] $Root, [string] $Full) { return ([IO.Path]::GetRelativePath($Root, $Full) -replace '\\', '/') }

# Each rule returns an array of finding lines (and nothing else), so the results cannot be mixed up with other output.
function Get-NameFindings([string] $Root) {
    $out = @()
    foreach ($i in @(Get-ChildItem -LiteralPath $Root -Recurse -Force)) {
        if (-not $i.PSIsContainer -and [regex]::IsMatch($i.Name, $NamePattern)) { $out += "secret-file: $(Get-Rel $Root $i.FullName)" }
    }
    return $out
}
function Get-GitFindings([string] $Root) {
    $out = @()
    foreach ($i in @(Get-ChildItem -LiteralPath $Root -Recurse -Force)) {
        if ($i.Name -eq '.git') { $out += "git-dir: $(Get-Rel $Root $i.FullName)" }
    }
    return $out
}
function Get-MemoryFindings([string] $Root, [string[]] $Terms) {
    $out = @()
    $mem = Join-Path $Root 'memory'
    if (-not (Test-Path -LiteralPath $mem -PathType Container)) { return $out }
    $direct = @(Get-ChildItem -LiteralPath $mem -File -Force)
    if ($direct.Count -gt $MaxMemoryFiles) { $out += 'memory-file-count: memory' }
    foreach ($f in @(Get-ChildItem -LiteralPath $mem -Recurse -File -Force)) {
        if ($f.Length -gt $MaxBytes) { continue }
        try { $text = [IO.File]::ReadAllText($f.FullName) } catch { continue }
        $rel = Get-Rel $Root $f.FullName
        $hit = $false
        $scan = [regex]::Replace($text, $AllowedEmailPattern, '')
        foreach ($p in $ContentPatterns.Values) { if ([regex]::IsMatch($scan, $p)) { $hit = $true; break } }
        if ($hit) { $out += "secret-content: $rel" }
        foreach ($t in $Terms) {
            if ($text.IndexOf($t, [StringComparison]::OrdinalIgnoreCase) -ge 0) { $out += "private-term: $rel"; break }
        }
    }
    return $out
}
function Get-PrivateTerms([string] $Raw) {
    if ([string]::IsNullOrWhiteSpace($Raw)) { return @() }
    return @($Raw -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
function Test-LabFiles([string] $Root, [string[]] $Terms) {
    $findings = @()
    $findings += Get-NameFindings $Root
    $findings += Get-GitFindings $Root
    $findings += Get-MemoryFindings $Root $Terms
    $checked = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force).Count
    return [pscustomobject]@{ Findings = @($findings | Sort-Object -Unique); Checked = $checked }
}

if ($SelfTest) {
    $fails = @()
    function Step([string] $name, [bool] $ok) { Write-Output ($(if ($ok) { 'PASS ' } else { 'FAIL ' }) + $name); if (-not $ok) { $script:fails += $name } }
    # Every pattern must match its own canary (and a near miss must not), so a broken pattern cannot make the self-test pass.
    foreach ($n in '.env', '.env.local', 'id_rsa', 'id_ed25519.pub', 'server.pem', 'a.KEY', 'x.p12', 'x.pfx', 'x.ppk', 'credentials.json') { Step "name canary matches: $n" ([regex]::IsMatch($n, $NamePattern)) }
    foreach ($n in 'README.md', 'handoff.md', 'environment.md', 'keynote.txt') { Step "name near miss does not match: $n" (-not [regex]::IsMatch($n, $NamePattern)) }
    $canary = @{
        'private key header' = "-----BEGIN RSA PRIVATE KEY-----"; 'sk- token' = ('sk-' + ('A1b2C3d4' * 3)); 'ghp_ token' = ('ghp_' + ('Zy9x8W7v' * 5))
        'AWS key id' = 'AKIAABCDEFGHIJKLMNOP'; 'Slack token' = 'xoxb-1234567890-abcdef'; 'email address' = 'someone@example.com'
    }
    foreach ($k in $ContentPatterns.Keys) { Step "content canary matches: $k" ([regex]::IsMatch($canary[$k], $ContentPatterns[$k])) }
    Step 'content near miss does not match: short sk-' (-not [regex]::IsMatch('sk-short', $ContentPatterns['sk- token']))
    Step 'content near miss does not match: not an email' (-not [regex]::IsMatch('at the end @ home', $ContentPatterns['email address']))

    $root = Join-Path ([IO.Path]::GetTempPath()) ('check-lab-files-' + [guid]::NewGuid().ToString('N'))
    function New-Case([string] $name, [scriptblock] $build) {
        $d = Join-Path $root $name
        New-Item -ItemType Directory (Join-Path $d 'memory') -Force | Out-Null
        New-Item -ItemType Directory (Join-Path $d 'scratch') -Force | Out-Null
        & $build $d
        return $d
    }
    function Rules([string] $dir, [string[]] $terms = @()) { return @((Test-LabFiles $dir $terms).Findings | ForEach-Object { ($_ -split ':')[0] }) }
    try {
        $d = New-Case 'clean' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') 'plain notes' }
        Step 'a clean folder has no findings' ((Test-LabFiles $d @()).Findings.Count -eq 0)
        $d = New-Case 'envfile' { param($d) Set-Content (Join-Path $d '.env.local') 'X=1' }
        Step 'secret-file is reported' ((Rules $d) -contains 'secret-file')
        $d = New-Case 'token' { param($d) Set-Content (Join-Path $d 'memory\n.md') $canary['sk- token'] }
        $f = (Test-LabFiles $d @()).Findings
        Step 'secret-content is reported and the finding does not contain the token' (($f -join "`n") -match 'secret-content: memory/n.md' -and -not (($f -join "`n").Contains($canary['sk- token'])))
        $d = New-Case 'noreply' { param($d) Set-Content (Join-Path $d 'memory\h.md') 'trailer Co-Authored-By: Claude <noreply@anthropic.com> and 123+ewok@users.noreply.github.com' }
        Step 'noreply addresses (commit trailers) are not reported' ((Test-LabFiles $d @()).Findings.Count -eq 0)
        $d = New-Case 'noreplyplus' { param($d) Set-Content (Join-Path $d 'memory\h.md') 'noreply@anthropic.com and also someone@example.com' }
        Step 'a personal address next to a noreply one is still reported' ((Rules $d) -contains 'secret-content')
        $d = New-Case 'scratchtoken' { param($d) Set-Content (Join-Path $d 'scratch\n.md') $canary['sk- token'] }
        Step 'a token in scratch is out of scope' ((Test-LabFiles $d @()).Findings.Count -eq 0)
        $d = New-Case 'git' { param($d) New-Item -ItemType Directory (Join-Path $d '.git') | Out-Null }
        Step 'git-dir is reported' ((Rules $d) -contains 'git-dir')
        $d = New-Case 'four' { param($d) 1..4 | ForEach-Object { Set-Content (Join-Path $d "memory\f$_.md") 'ok' } }
        Step 'memory-file-count is reported for 4 files' ((Rules $d) -contains 'memory-file-count')
        $d = New-Case 'three' { param($d) 1..3 | ForEach-Object { Set-Content (Join-Path $d "memory\f$_.md") 'ok' } }
        Step 'three files in memory are fine' ((Test-LabFiles $d @()).Findings.Count -eq 0)
        $d = New-Case 'term' { param($d) Set-Content (Join-Path $d 'memory\h.md') 'we deploy to Acme-Host-77' }
        Step 'private-term is reported, case-insensitively' ((Rules $d @('acme-host-77')) -contains 'private-term')
        Step 'private terms are literal, not regular expressions' ((Rules $d @('a.*host')).Count -eq 0)
        Step 'no private terms configured: nothing reported' ((Test-LabFiles $d @()).Findings.Count -eq 0)
    }
    finally { Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue }
    if ($fails.Count) { Write-Output "SELF-TEST FAILED: $($fails -join '; ')"; exit 1 }
    Write-Output 'SELF-TEST OK'
    exit 0
}

if (-not $Path) { $Path = $env:LAB_FILES }
if ([string]::IsNullOrWhiteSpace($Path)) { Write-Output 'error: no folder given. Pass -Path or set LAB_FILES (for example in the lab .env).'; exit 2 }
if (-not (Test-Path -LiteralPath $Path -PathType Container)) { Write-Output "error: not a folder: $Path"; exit 2 }
$root = (Resolve-Path -LiteralPath $Path).Path
$result = Test-LabFiles $root (Get-PrivateTerms $env:LAB_PRIVATE_TERMS)
if ($result.Findings.Count -eq 0) { Write-Output "lab files clean: $($result.Checked)"; exit 0 }
foreach ($line in $result.Findings) { Write-Output $line }
Write-Output "FAILED: $($result.Findings.Count) finding(s)"
exit 1
