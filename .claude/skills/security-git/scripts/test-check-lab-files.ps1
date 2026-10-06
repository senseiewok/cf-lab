# Outside-in test for check-lab-files.ps1 (board T-0056): runs the script against throwaway folders, one per rule, and checks its
# exit codes and output (a finding names the rule and the file and never echoes the matched text). Prints one FAIL line per
# problem and VERIFIED when there is none. No network, no model. Usage: pwsh -File test-check-lab-files.ps1 [-Script <path>]
param([string] $Script = (Join-Path $PSScriptRoot 'check-lab-files.ps1'))
$ErrorActionPreference = 'Stop'
$fails = [System.Collections.Generic.List[string]]::new()
function Fail([string] $m) { $fails.Add("FAIL $m") }
$root = Join-Path ([IO.Path]::GetTempPath()) ('lf-verify-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $root | Out-Null

function New-Folder([string] $name, [scriptblock] $build) {
    $d = Join-Path $root $name
    New-Item -ItemType Directory $d | Out-Null
    New-Item -ItemType Directory (Join-Path $d 'memory') | Out-Null
    New-Item -ItemType Directory (Join-Path $d 'scratch') | Out-Null
    & $build $d
    return $d
}
function Run([string[]] $ArgList, [hashtable] $Env = @{}) {
    $saved = @{}
    foreach ($k in $Env.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $Env[$k]) }
    try { $out = & pwsh -NoProfile -File $Script @ArgList 2>&1 | Out-String; $code = $LASTEXITCODE }
    finally { foreach ($k in $Env.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) } }
    return [pscustomobject]@{ Code = $code; Out = $out }
}
function Expect-Violation([string] $label, [string] $dir, [string] $rule, [string] $mustMention, [string[]] $mustNotEcho = @(), [hashtable] $Env = @{}) {
    $r = Run @('-Path', $dir) $Env
    if ($r.Code -ne 1) { Fail "$label : expected exit 1, got $($r.Code)" }
    if ($r.Out -notmatch [regex]::Escape($rule)) { Fail "$label : output must name the rule '$rule'" }
    if ($mustMention -and $r.Out -notmatch [regex]::Escape($mustMention)) { Fail "$label : output must name the file '$mustMention'" }
    foreach ($s in $mustNotEcho) { if ($r.Out.Contains($s)) { Fail "$label : output must not echo the matched text" } }
}

try {
    $tok = 'sk-' + ('A1b2C3d4' * 4)
    $gh = 'ghp_' + ('Zy9x8W7v' * 5)
    # clean folder
    $clean = New-Folder 'clean' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') 'plain session notes, nothing private' }
    $r = Run @('-Path', $clean)
    if ($r.Code -ne 0) { Fail "clean folder must exit 0, got $($r.Code): $($r.Out.Trim())" }
    # secret-file rule (whole folder, by name)
    $d = New-Folder 'envfile' { param($d) Set-Content (Join-Path $d '.env.local') 'X=1' }
    Expect-Violation 'a .env file' $d 'secret-file' '.env.local'
    $d = New-Folder 'pem' { param($d) Set-Content (Join-Path $d 'scratch\server.pem') 'x' }
    Expect-Violation 'a .pem file in scratch' $d 'secret-file' 'server.pem'
    $d = New-Folder 'idrsa' { param($d) Set-Content (Join-Path $d 'id_rsa') 'x' }
    Expect-Violation 'an id_rsa file' $d 'secret-file' 'id_rsa'
    # secret-content rule (memory/ only)
    $d = New-Folder 'privkey' { param($d) Set-Content (Join-Path $d 'memory\notes.md') "-----BEGIN RSA PRIVATE KEY-----`nabc" }
    Expect-Violation 'a private key header' $d 'secret-content' 'notes.md' @('BEGIN RSA PRIVATE KEY')
    $d = New-Folder 'sktoken' { param($d) Set-Content (Join-Path $d 'memory\notes.md') "token $tok here" }
    Expect-Violation 'an sk- token' $d 'secret-content' 'notes.md' @($tok)
    $d = New-Folder 'ghtoken' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') "gh $gh" }
    Expect-Violation 'a ghp_ token' $d 'secret-content' 'handoff.md' @($gh)
    $d = New-Folder 'email' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') 'ask someone@example.com about it' }
    Expect-Violation 'an email address' $d 'secret-content' 'handoff.md' @('someone@example.com')
    $d = New-Folder 'noreply' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') 'trailer: Co-Authored-By: Claude <noreply@anthropic.com>' }
    $r = Run @('-Path', $d)
    if ($r.Code -ne 0) { Fail "a noreply address (commit trailer) must not be reported: expected exit 0, got $($r.Code): $($r.Out.Trim())" }
    $d = New-Folder 'noreplyplus' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') 'noreply@anthropic.com and someone@example.com' }
    Expect-Violation 'a personal address beside a noreply one' $d 'secret-content' 'handoff.md' @('someone@example.com')
    $d = New-Folder 'scratchtoken' { param($d) Set-Content (Join-Path $d 'scratch\x.txt') "token $tok" }
    $r = Run @('-Path', $d)
    if ($r.Code -ne 0) { Fail "a token in scratch/ is out of scope (content is scanned in memory/ only): expected exit 0, got $($r.Code)" }
    # git-dir rule
    $d = New-Folder 'gitdir' { param($d) New-Item -ItemType Directory (Join-Path $d '.git') | Out-Null }
    Expect-Violation 'a .git folder' $d 'git-dir' '.git'
    # memory-file-count rule: 3 is fine, 4 is not
    $d = New-Folder 'three' { param($d) 1..3 | ForEach-Object { Set-Content (Join-Path $d "memory\f$_.md") 'ok' } }
    $r = Run @('-Path', $d)
    if ($r.Code -ne 0) { Fail "three files in memory/ must pass, got exit $($r.Code)" }
    $d = New-Folder 'four' { param($d) 1..4 | ForEach-Object { Set-Content (Join-Path $d "memory\f$_.md") 'ok' } }
    Expect-Violation 'four files in memory/' $d 'memory-file-count' 'memory'
    # private-term rule: LAB_PRIVATE_TERMS, ';' separated, case-insensitive, literal
    $d = New-Folder 'term' { param($d) Set-Content (Join-Path $d 'memory\handoff.md') 'we deploy to Acme-Host-77 nightly' }
    Expect-Violation 'a private term' $d 'private-term' 'handoff.md' @('Acme-Host-77') @{ LAB_PRIVATE_TERMS = 'other;acme-host-77;' }
    $r = Run @('-Path', $d) @{ LAB_PRIVATE_TERMS = '' }
    if ($r.Code -ne 0) { Fail "with no private terms configured the term file must pass, got exit $($r.Code)" }
    $r = Run @('-Path', $d) @{ LAB_PRIVATE_TERMS = 'a.*host' }
    if ($r.Code -ne 0) { Fail "private terms are literal text, not regular expressions: 'a.*host' must not match; got exit $($r.Code)" }
    # usage errors
    $r = Run @('-Path', (Join-Path $root 'does-not-exist'))
    if ($r.Code -ne 2) { Fail "a missing folder must exit 2, got $($r.Code)" }
    $r = Run @() @{ LAB_FILES = '' }
    if ($r.Code -ne 2) { Fail "no -Path and no LAB_FILES must exit 2, got $($r.Code)" }
    $r = Run @() @{ LAB_FILES = $clean }
    if ($r.Code -ne 0) { Fail "with LAB_FILES set to a clean folder and no -Path, expected exit 0, got $($r.Code)" }
    # self-test
    $r = Run @('-SelfTest')
    if ($r.Code -ne 0 -or $r.Out -notmatch 'SELF-TEST OK') { Fail "-SelfTest must exit 0 and print SELF-TEST OK; got exit $($r.Code): $($r.Out.Trim() -replace '\s+', ' ')" }
}
catch { Fail "the verifier could not finish: $($_.Exception.Message)" }
finally { Remove-Item -Recurse -Force $root -ErrorAction SilentlyContinue }

$fails | ForEach-Object { Write-Output $_ }
if ($fails.Count) { Write-Output "$($fails.Count) failure(s)"; exit 1 }
Write-Output 'VERIFIED'
exit 0
