<#
.SYNOPSIS
  Run one command with the variables from a local .env file, without printing them.

.DESCRIPTION
  Keys belong in a git-ignored .env, never on a command line, in a task packet or in chat.
  This loads NAME=value lines from .env into the environment of the one command you run
  after `--` and exits with that command's exit code. It prints nothing about the values.

  There is ONE lab env file: the `.env` in the cf-lab control repo, whatever folder you run this from
  (override with -EnvFile or the LAB_ENV_FILE variable). Values that start with ./ or ../ are
  resolved relative to that file's folder, so one file can point at the single source catalog.

  It refuses to run when .env is tracked by git (a key that is tracked is already leaked),
  when the file is missing, or when a line is malformed. A variable whose value is empty or
  still the placeholder `your_key_here` is skipped (the command simply does not see it) and
  named in a note, so one unfilled key does not block everything else. Messages name the
  variable or the line number, never the value.

.EXAMPLE
  pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -- python tool.py --flag
  pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -EnvFile D:\keys\lab.env -- mycmd
  pwsh -NoProfile -File .claude/skills/security-git/scripts/run-with-env.ps1 -SelfTest

.NOTES
  Exit codes: the command's own code, or 2 for a refusal or usage error.
#>
# No param() block on purpose: PowerShell would bind the child command's own flags (-Command,
# -Verbose, --flag) to this script's parameters. $args keeps every token literally.
$ErrorActionPreference = 'Stop'
$SelfTest = ($args.Count -eq 1 -and $args[0] -eq '-SelfTest')

function Read-EnvFile([string] $Path) {
    $vars = [ordered]@{}
    $script:Skipped = @()
    $envDir = Split-Path -Parent (Resolve-Path -LiteralPath $Path)
    $n = 0
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $n++
        if ($line -match '^\s*(#|$)') { continue }
        if ($line -notmatch '^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$') { throw "line ${n}: not NAME=value" }
        $name = $Matches[1]; $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) { $value = $value.Substring(1, $value.Length - 2) }
        if ([string]::IsNullOrWhiteSpace($value) -or $value -ceq 'your_key_here') { $script:Skipped += $name; continue }
        if ($value -match '^\.\.?[\\/]') { $value = [IO.Path]::GetFullPath((Join-Path $envDir $value)) }
        $vars[$name] = $value
    }
    return $vars
}

# Messages go to stderr: when this wraps a server that speaks a protocol on stdout (an MCP server over
# stdio), anything extra on stdout would corrupt the stream.
function Say-Err([string] $Message) { [Console]::Error.WriteLine($Message) }

function Invoke-WithEnv([string] $Path, [string[]] $Cmd) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { Say-Err "error: $Path not found. Copy .env.example to .env and fill it in."; return 2 }
    $dir = Split-Path -Parent (Resolve-Path -LiteralPath $Path)
    & git -C $dir ls-files --error-unmatch -- (Split-Path -Leaf $Path) 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { Say-Err 'error: that file is tracked by git. Treat every key in it as leaked: revoke it, then untrack the file.'; return 2 }
    try { $vars = Read-EnvFile $Path } catch { Say-Err "error: $($_.Exception.Message)"; return 2 }
    if (-not $Cmd -or $Cmd.Count -eq 0) { Say-Err 'error: no command given. Usage: run-with-env.ps1 -- <command> [args]'; return 2 }
    if ($script:Skipped.Count -gt 0) { Say-Err "note: skipped $($script:Skipped -join ', ') (empty or still the placeholder; the command will not see it)" }
    foreach ($k in $vars.Keys) { [Environment]::SetEnvironmentVariable($k, $vars[$k], 'Process') }
    # Do NOT run the command in here: a function's command output becomes part of its return value
    # and the child's output would be swallowed. -1 means "ready; run it at script level".
    return -1
}

if ($SelfTest) {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('run-with-env-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $tmp | Out-Null
    $fails = @()
    function Expect([string] $name, [bool] $ok, [string] $detail = '') { Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" })); if (-not $ok) { $script:fails += $name } }
    try {
        & git -C $tmp init -q 2>&1 | Out-Null
        $secret = 'zz-not-a-real-key-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
        Set-Content (Join-Path $tmp '.env') "# comment`nFAKE_KEY=$secret`nexport QUOTED=`"a b`"" -Encoding utf8
        $child = "if (`$env:FAKE_KEY -eq '$secret' -and `$env:QUOTED -eq 'a b') { exit 0 } else { exit 1 }"
        $out = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp '.env') -- pwsh -NoProfile -Command $child 2>&1 | Out-String
        Expect 'the child command sees the variables (including a quoted value)' ($LASTEXITCODE -eq 0) "exit=$LASTEXITCODE"
        Expect 'nothing about the value is printed' (-not $out.Contains($secret)) 'the secret appeared in output'
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp '.env') -- pwsh -NoProfile -Command 'Write-Output "hello-from-child"; exit 0' 2>&1 | Out-String
        Expect "the child's own output reaches the caller" ($o -match 'hello-from-child') "output was: $o"
        $code = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp '.env') -- pwsh -NoProfile -Command 'exit 7' 2>&1 | Out-Null; $c = $LASTEXITCODE
        Expect "the child's exit code is passed through" ($c -eq 7) "exit=$c"
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp 'missing.env') -- pwsh -NoProfile -Command 'exit 0' 2>&1 | Out-String
        Expect 'a missing file is refused with exit 2 and a hint' ($LASTEXITCODE -eq 2 -and $o -match 'Copy \.env\.example') $o
        Set-Content (Join-Path $tmp 'ph.env') "DC_API_KEY=your_key_here`nOTHER=kept`nEMPTY=" -Encoding utf8
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp 'ph.env') -- pwsh -NoProfile -Command 'if ($null -eq $env:DC_API_KEY -and $null -eq $env:EMPTY -and $env:OTHER -eq "kept") { exit 0 } else { exit 1 }' 2>&1 | Out-String
        Expect 'a placeholder or empty value is skipped and named; other variables still load' ($LASTEXITCODE -eq 0 -and $o -match 'skipped DC_API_KEY, EMPTY') $o
        New-Item -ItemType Directory (Join-Path $tmp 'sub') | Out-Null
        Set-Content (Join-Path $tmp 'sub\cat.yaml') 'x: 1' -Encoding utf8
        Set-Content (Join-Path $tmp 'rel.env') "CATALOG=./sub/cat.yaml`nUP=../elsewhere.yaml`nPLAIN=notapath" -Encoding utf8
        $expect = (Join-Path $tmp 'sub\cat.yaml')
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp 'rel.env') -- pwsh -NoProfile -Command "if (`$env:CATALOG -eq '$expect' -and [IO.Path]::IsPathRooted(`$env:UP) -and `$env:PLAIN -eq 'notapath') { exit 0 } else { exit 1 }" 2>&1 | Out-String
        Expect 'values starting with ./ or ../ become absolute paths relative to the env file; others are untouched' ($LASTEXITCODE -eq 0) $o
        [Environment]::SetEnvironmentVariable('LAB_ENV_FILE', (Join-Path $tmp 'rel.env'), 'Process')
        $o = & pwsh -NoProfile -File $PSCommandPath -- pwsh -NoProfile -Command 'if ($env:PLAIN -eq "notapath") { exit 0 } else { exit 1 }' 2>&1 | Out-String
        $viaVar = $LASTEXITCODE
        [Environment]::SetEnvironmentVariable('LAB_ENV_FILE', $null, 'Process')
        Expect 'LAB_ENV_FILE selects the env file when no -EnvFile is given' ($viaVar -eq 0) $o
        Set-Content (Join-Path $tmp 'bad.env') 'this is not a pair' -Encoding utf8
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp 'bad.env') -- pwsh -NoProfile -Command 'exit 0' 2>&1 | Out-String
        Expect 'a malformed line is refused by line number' ($LASTEXITCODE -eq 2 -and $o -match 'line 1') $o
        & git -C $tmp -c core.safecrlf=false add .env 2>&1 | Out-Null
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp '.env') -- pwsh -NoProfile -Command 'exit 0' 2>&1 | Out-String
        Expect 'a git-tracked .env is refused' ($LASTEXITCODE -eq 2 -and $o -match 'tracked by git' -and -not $o.Contains($secret)) $o
        $o = & pwsh -NoProfile -File $PSCommandPath -EnvFile (Join-Path $tmp 'ph.env') 2>&1 | Out-String
        Expect 'no command given is a usage error' ($LASTEXITCODE -eq 2) $o
    } finally { Remove-Item -Recurse -Force -LiteralPath $tmp -ErrorAction SilentlyContinue }
    if ($fails.Count) { Write-Output "SELF-TEST FAILED: $($fails -join '; ')"; exit 1 }
    Write-Output 'SELF-TEST OK'; exit 0
}

$rest = @($args)
$EnvFile = $null
if ($rest.Count -ge 2 -and $rest[0] -eq '-EnvFile') { $EnvFile = $rest[1]; $rest = @($rest | Select-Object -Skip 2) }
if ($rest.Count -gt 0 -and $rest[0] -eq '--') { $rest = @($rest | Select-Object -Skip 1) }
if (-not $EnvFile -and $env:LAB_ENV_FILE) { $EnvFile = $env:LAB_ENV_FILE }
if (-not $EnvFile) {
    # The single lab env: the .env in the cf-lab control repo (this script lives four folders below it).
    $hqRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
    $EnvFile = Join-Path $hqRoot '.env'
}
$rc = Invoke-WithEnv -Path $EnvFile -Cmd $rest
if ($rc -ge 0) { exit $rc }
& $rest[0] @($rest | Select-Object -Skip 1)
exit $LASTEXITCODE
