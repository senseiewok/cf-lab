<#
.SYNOPSIS
  Pre-commit check: is the staged set what you meant, and does it add anything that must
  never be public?

.DESCRIPTION
  1. Prints the staged files (with status). With -Expected, exits 1 if the staged set
     differs from that list. A promise like "I will leave that file staged for you" is only
     true if the staged set is checked before every commit.
  2. Scans ADDED lines only for the categories in security-git section 3 (local paths,
     personal email, hardware, network details, secrets, private project names), using
     privacy-patterns.txt. Each pattern carries a canary it must match; a pattern that
     misses its own canary fails the run, so "none found" cannot be a broken scan.
  3. Hits are listed as path:line and category. The matched text is not echoed.

  It never commits, unstages or edits anything. It checks drift, not intent: the agent
  supplies -Expected, so a human still reads the printed list.

.EXAMPLE
  pwsh -NoProfile -File check-staged.ps1 -Expected README.md,tasks/board.json
  pwsh -NoProfile -File check-staged.ps1 -SelfTest

.NOTES
  Exit codes: 0 clean, 1 staged set differs / privacy hit / broken pattern, 2 usage error.
#>
[CmdletBinding(DefaultParameterSetName = 'Check')]
param(
    [Parameter(ParameterSetName = 'Check')] [string[]] $Expected,
    [Parameter(ParameterSetName = 'Check')] [string] $RepoPath = '.',
    [string] $PatternFile = (Join-Path $PSScriptRoot 'privacy-patterns.txt'),
    [string] $AllowFile = (Join-Path $PSScriptRoot 'privacy-allow.txt'),
    [Parameter(Mandatory, ParameterSetName = 'SelfTest')] [switch] $SelfTest
)

$ErrorActionPreference = 'Stop'

function Read-Table([string] $Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Missing file: $Path" }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*(#|$)') { continue }
        , ($line -split "`t")
    }
}

function Test-Patterns($Patterns) {
    $broken = @()
    foreach ($p in $Patterns) {
        if ($p.Count -lt 3) { $broken += "malformed pattern line: $($p -join ' | ')"; continue }
        try { $ok = [regex]::IsMatch($p[2], $p[1]) } catch { $ok = $false }
        if (-not $ok) { $broken += "pattern for '$($p[0])' does not match its own canary" }
    }
    return $broken
}

function Get-StagedStatus([string] $Repo) {
    $raw = & git -C $Repo -c core.safecrlf=false diff --cached --name-status -z --no-renames 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git diff --cached failed in $Repo" }
    $parts = ($raw -join '') -split "`0" | Where-Object { $_ }
    $out = @()
    for ($i = 0; $i + 1 -lt $parts.Count; $i += 2) { $out += [pscustomobject]@{ Status = $parts[$i]; Path = ($parts[$i + 1] -replace '\\', '/') } }
    return $out
}

function Get-AddedLines([string] $Repo) {
    $diff = & git -C $Repo -c core.safecrlf=false diff --cached -U0 --no-color --no-renames 2>$null
    if ($LASTEXITCODE -ne 0) { throw "git diff --cached -U0 failed in $Repo" }
    $file = $null; $ln = 0
    foreach ($l in $diff) {
        if ($l -match '^\+\+\+ b/(.+)$') { $file = $Matches[1]; continue }
        if ($l -match '^\+\+\+ /dev/null') { $file = $null; continue }
        if ($l -match '^@@ -\d+(?:,\d+)? \+(\d+)') { $ln = [int]$Matches[1] - 1; continue }
        if ($file -and $l.StartsWith('+') -and -not $l.StartsWith('+++')) { $ln++; [pscustomobject]@{ Path = $file; Line = $ln; Text = $l.Substring(1) } }
    }
}

function Invoke-Check([string] $Repo, [string[]] $Want, [string] $PatFile, [string] $AllowPath) {
    $problems = 0
    $patterns = @(Read-Table $PatFile)
    $allow = @(Read-Table $AllowPath)
    $broken = @(Test-Patterns $patterns)
    foreach ($b in $broken) { Write-Host "BROKEN SCAN: $b"; $problems++ }

    $staged = @(Get-StagedStatus $Repo)
    Write-Host ("staged files ({0}):" -f $staged.Count)
    foreach ($s in $staged) { Write-Host ("  {0}  {1}" -f $s.Status, $s.Path) }
    # A real env file holds secrets and must never be committed. Templates (.env.example, .env.sample)
    # are fine; a deletion (D) of one that was wrongly tracked is also fine.
    foreach ($s in $staged) {
        $leaf = Split-Path -Leaf $s.Path
        if ($leaf -match '^\.env(\..+)?$' -and $leaf -notmatch '^\.env\.(example|sample)$' -and $s.Status -ne 'D') {
            Write-Host "FORBIDDEN STAGED: $($s.Path) is an env file; it holds secrets and must not be committed"; $problems++
        }
    }
    if ($PSBoundParameters.ContainsKey('Want') -or $null -ne $Want) {
        $have = $staged.Path | Sort-Object
        $exp = $Want | ForEach-Object { $_ -replace '\\', '/' } | Sort-Object
        $extra = @($have | Where-Object { $_ -notin $exp })
        $missing = @($exp | Where-Object { $_ -notin $have })
        foreach ($e in $extra) { Write-Host "UNEXPECTED STAGED: $e"; $problems++ }
        foreach ($m in $missing) { Write-Host "EXPECTED BUT NOT STAGED: $m"; $problems++ }
        if (-not $extra -and -not $missing) { Write-Host 'staged set equals the expected set' }
    } else {
        Write-Host 'no -Expected given: the list above is printed, not checked'
    }

    if ($broken.Count -eq 0) {
        $hits = 0
        foreach ($a in (Get-AddedLines $Repo)) {
            if ($a.Text -match 'privacy-scan:\s*allow') { continue }
            foreach ($p in $patterns) {
                if ($p.Count -lt 3 -or -not [regex]::IsMatch($a.Text, $p[1])) { continue }
                $allowed = $false
                foreach ($al in $allow) { if ($a.Path -match $al[0] -and ($al[1] -eq '*' -or $al[1] -eq $p[0])) { $allowed = $true; break } }
                if (-not $allowed) { Write-Host ("PRIVACY: {0}:{1}  [{2}]" -f $a.Path, $a.Line, $p[0]); $hits++ }
            }
        }
        $problems += $hits
        if ($hits -eq 0) { Write-Host ('privacy scan: clean ({0} patterns, each matched its canary)' -f $patterns.Count) }
    }
    if ($problems -gt 0) { Write-Host "FAILED: $problems problem(s)"; return 1 }
    Write-Host 'OK'
    return 0
}

if ($SelfTest) {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("check-staged-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    $script = $PSCommandPath
    $fail = @()
    try {
        $env:GIT_AUTHOR_NAME = 't'; $env:GIT_AUTHOR_EMAIL = 't@example.invalid'; $env:GIT_COMMITTER_NAME = 't'; $env:GIT_COMMITTER_EMAIL = 't@example.invalid'
        & git -C $tmp init -q 2>&1 | Out-Null
        Set-Content -Path (Join-Path $tmp 'base.txt') -Value 'base' -Encoding utf8
        & git -C $tmp add base.txt; & git -C $tmp -c core.safecrlf=false commit -q -m base 2>&1 | Out-Null
        function Run([string[]] $a) { $o = & pwsh -NoProfile -File $script -RepoPath $tmp @a 2>&1; return @{ Code = $LASTEXITCODE; Out = ($o -join "`n") } }
        function Exp([string[]] $want, [string[]] $extra = @()) { return @('-Expected', ($want -join ',')) + $extra }
        function Expect([string] $name, [int] $code, [hashtable] $r, [string] $needle) {
            $ok = ($r.Code -eq $code) -and (-not $needle -or $r.Out -match [regex]::Escape($needle))
            Write-Output (('PASS ' , 'FAIL ')[-not $ok] + $name)
            if (-not $ok) { $script:fail += $name; Write-Output ("   exit=$($r.Code) wanted=$code; output: " + ($r.Out -replace "`n", ' / ')) }
        }
        # a) clean file, expected set matches
        Set-Content (Join-Path $tmp 'a.md') 'plain text' -Encoding utf8; & git -C $tmp add a.md
        Expect 'clean staged set equal to expected' 0 (Run (Exp 'a.md')) 'staged set equals the expected set'
        # b) an extra staged file the agent did not expect
        Set-Content (Join-Path $tmp 'protected.md') 'other' -Encoding utf8; & git -C $tmp add protected.md
        Expect 'extra staged file is reported (the E9 case)' 1 (Run (Exp 'a.md')) 'UNEXPECTED STAGED: protected.md'
        Expect 'expected file missing from the index is reported' 1 (Run (Exp 'a.md','protected.md','ghost.md')) 'EXPECTED BUT NOT STAGED: ghost.md'
        & git -C $tmp reset -q protected.md
        # c) planted privacy hits, one per category, each in its own commit-less index
        $plants = @{ 'local-path' = ('C:' + '\Users\someone\x'); 'hardware' = 'runs on an RTX 5090'; 'network' = 'host 192.168.1.20'; 'identity-email' = 'mail someone@gmail.com'; 'private-project' = 'see deploy-to-godaddy.ps1' }
        foreach ($k in $plants.Keys) {
            Set-Content (Join-Path $tmp 'a.md') $plants[$k] -Encoding utf8; & git -C $tmp add a.md
            Expect "planted $k is blocked" 1 (Run (Exp 'a.md')) "[$k]"
        }
        # d) allow marker and allow file
        Set-Content (Join-Path $tmp 'a.md') ('documented example ' + 'C:' + '\Users\x\ privacy-scan: allow') -Encoding utf8; & git -C $tmp add a.md
        Expect 'inline allow marker passes' 0 (Run (Exp 'a.md')) 'privacy scan: clean'
        Set-Content (Join-Path $tmp 'a.md') 'plain again' -Encoding utf8; & git -C $tmp add a.md
        # e) a broken pattern (canary not matched) must fail even when the content is clean
        $badPat = Join-Path $tmp 'bad-patterns.txt'; "local-path`tZZZ-never-matches`tC:\Users\x\" | Set-Content $badPat -Encoding utf8
        Expect 'a pattern that misses its canary fails the run' 1 (Run (Exp 'a.md' @('-PatternFile', $badPat))) 'BROKEN SCAN'
        # e2) a real env file staged is refused even when it is the expected set; templates are allowed
        & git -C $tmp reset -q a.md 2>&1 | Out-Null
        Set-Content (Join-Path $tmp '.env') 'SOME_KEY=zz' -Encoding utf8; & git -C $tmp -c core.safecrlf=false add -f .env
        Expect 'a staged .env is refused (the leak case)' 1 (Run (Exp '.env')) 'FORBIDDEN STAGED: .env'
        & git -C $tmp reset -q .env
        Set-Content (Join-Path $tmp '.env.local') 'X=1' -Encoding utf8; & git -C $tmp -c core.safecrlf=false add -f .env.local
        Expect 'a staged .env.local is refused too' 1 (Run (Exp '.env.local')) 'FORBIDDEN STAGED: .env.local'
        & git -C $tmp reset -q .env.local
        Set-Content (Join-Path $tmp '.env.example') 'SOME_KEY=your_key_here' -Encoding utf8; & git -C $tmp -c core.safecrlf=false add .env.example
        Expect 'a staged .env.example template is allowed' 0 (Run (Exp '.env.example')) 'staged set equals the expected set'
        & git -C $tmp reset -q .env.example
        Set-Content (Join-Path $tmp 'a.md') 'plain again' -Encoding utf8; & git -C $tmp add a.md
        # f) deletion is a staged change and must be listed
        & git -C $tmp rm -q base.txt
        Expect 'a staged deletion is part of the staged set' 1 (Run (Exp 'a.md')) 'UNEXPECTED STAGED: base.txt'
        # g) the repo's real pattern file loads and every canary matches
        $own = @(Test-Patterns @(Read-Table $PatternFile))
        Write-Output (('PASS ', 'FAIL ')[$own.Count -gt 0] + "shipped patterns all match their canaries ($((Read-Table $PatternFile).Count) patterns)")
        if ($own.Count -gt 0) { $fail += 'shipped patterns' }
    } finally {
        Remove-Item -Recurse -Force -LiteralPath $tmp -ErrorAction SilentlyContinue
        Remove-Item Env:GIT_AUTHOR_NAME, Env:GIT_AUTHOR_EMAIL, Env:GIT_COMMITTER_NAME, Env:GIT_COMMITTER_EMAIL -ErrorAction SilentlyContinue
    }
    if ($fail.Count -gt 0) { Write-Output "SELF-TEST FAILED: $($fail -join '; ')"; exit 1 }
    Write-Output 'SELF-TEST OK'
    exit 0
}

if ($PSBoundParameters.ContainsKey('Expected')) { $Expected = @($Expected | ForEach-Object { $_ -split ',' } | Where-Object { $_ }) }
try {
    $repo = (& git -C $RepoPath rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $repo) { Write-Error "Not a git repository: $RepoPath" -ErrorAction Continue; exit 2 }
    $code = if ($PSBoundParameters.ContainsKey('Expected')) { Invoke-Check -Repo $repo -Want $Expected -PatFile $PatternFile -AllowPath $AllowFile }
            else { Invoke-Check -Repo $repo -Want $null -PatFile $PatternFile -AllowPath $AllowFile }
    exit $code
} catch {
    Write-Error $_.Exception.Message -ErrorAction Continue
    exit 2
}
