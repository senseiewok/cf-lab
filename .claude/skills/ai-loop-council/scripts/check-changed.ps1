<#
.SYNOPSIS
Checks staged scripts and data files for syntax errors before commit.
.DESCRIPTION
Reads the STAGED (index) version of each changed file and validates it by extension.
Also runs owning checkers when applicable. Never commits, unstages, or edits anything.
.EXAMPLE
pwsh -NoProfile -File check-changed.ps1 -RepoPath .
#>
[CmdletBinding()]
param(
    [string]$RepoPath = '.'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

try {
    $root = (& git -C $RepoPath rev-parse --show-toplevel 2>&1) -join "`n"
    if ($LASTEXITCODE -ne 0) { Write-Host "error: not a git repository"; exit 2 }
    $root = $root.Trim()

    $raw = (& git -C $RepoPath -c core.safecrlf=false diff --cached --name-only --diff-filter=ACMR -z 2>$null)
    if ($LASTEXITCODE -ne 0) { throw "git diff failed" }
    $files = @($raw -split "`0" | Where-Object { $_ })

    if (-not $files.Count) { Write-Host "no staged files"; Write-Host "OK"; exit 0 }

    $failures = 0

    function Get-PythonExe {
        if (Get-Command python -ErrorAction SilentlyContinue) { return 'python' }
        if (Get-Command py -ErrorAction SilentlyContinue) { return 'py' }
        return $null
    }

    function Get-StagedText([string]$p) {
        $t = (& git -C $root -c core.safecrlf=false show ":$p" 2>$null) -join "`n"
        if ($LASTEXITCODE -ne 0) { throw "git show failed" }
        return $t
    }

    foreach ($file in $files) {
        $ext = [System.IO.Path]::GetExtension($file).ToLowerInvariant()
        # A recorded wrong attempt is kept as a case on purpose; it is allowed to be broken.
        if ($file -match '(^|/)known-wrong/') { Write-Host "SKIP ${file}: a recorded known-wrong example"; continue }

        if ($ext -eq '.ps1' -or $ext -eq '.psm1') {
            try {
                $text = Get-StagedText $file
                $tokens = $null; $errors = $null
                [void][System.Management.Automation.Language.Parser]::ParseInput($text, [ref]$tokens, [ref]$errors)
                if ($errors.Count -gt 0) {
                    Write-Host "FAIL ${file}: line $($errors[0].Extent.StartLineNumber): $($errors[0].Message)"
                    $failures++
                } else { Write-Host "PASS $file" }
            } catch { Write-Host "FAIL ${file}: $_"; $failures++ }
        }
        elseif ($ext -eq '.json') {
            try {
                $text = Get-StagedText $file
                # ConvertFrom-Json accepts a trailing comma; Test-Json does not.
                if (Test-Json -Json $text -ErrorAction SilentlyContinue) { Write-Host "PASS $file" }
                else { Write-Host "FAIL ${file}: invalid JSON"; $failures++ }
            } catch { Write-Host "FAIL ${file}: invalid JSON"; $failures++ }
        }
        elseif ($ext -eq '.py') {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP ${file}: python not found"; continue }
            try {
                $text = Get-StagedText $file
                # Through a UTF-8 temp file, not stdin: piping text to python uses the console encoding and broke on non-ASCII characters.
                $tmp = [IO.Path]::GetTempFileName()
                try {
                    [IO.File]::WriteAllText($tmp, $text, [Text.UTF8Encoding]::new($false))
                    & $pyExe -c "import ast,sys; ast.parse(open(sys.argv[1], encoding='utf-8').read())" $tmp 2>&1 | Out-Null
                } finally { Remove-Item -LiteralPath $tmp -ErrorAction SilentlyContinue }
                if ($LASTEXITCODE -ne 0) { Write-Host "FAIL ${file}: syntax error"; $failures++ }
                else { Write-Host "PASS $file" }
            } catch { Write-Host "FAIL ${file}: $_"; $failures++ }
        }
        elseif ($ext -eq '.yml' -or $ext -eq '.yaml') {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP ${file}: python not found"; continue }
            try {
                $text = Get-StagedText $file
                $tmpy = [IO.Path]::GetTempFileName()
                try {
                    [IO.File]::WriteAllText($tmpy, $text, [Text.UTF8Encoding]::new($false))
                    $out = (& $pyExe -c "import sys,yaml; yaml.safe_load(open(sys.argv[1], encoding='utf-8').read())" $tmpy 2>&1)
                } finally { Remove-Item -LiteralPath $tmpy -ErrorAction SilentlyContinue }
                if ($LASTEXITCODE -ne 0) {
                    $s = ($out -join "`n")
                    if ($s -match 'No module named') { Write-Host "SKIP ${file}: yaml module not found" }
                    else { Write-Host "FAIL ${file}: invalid YAML"; $failures++ }
                } else { Write-Host "PASS $file" }
            } catch { Write-Host "FAIL ${file}: $_"; $failures++ }
        }
    }

    # Owning checkers
    if ($files | Where-Object { $_ -eq 'tasks/board.json' -or $_ -eq 'tasks/render-board.ps1' }) {
        if (Test-Path (Join-Path $root 'tasks/render-board.ps1')) {
            Push-Location $root
            try {
                & pwsh -NoProfile -File tasks/render-board.ps1 -Check 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) { Write-Host "FAIL owning checker render-board.ps1 -Check"; $failures++ }
            } finally { Pop-Location }
        }
    }

    $skillFiles = @($files | Where-Object { $_ -cmatch '^\.claude/skills/[^/]+/SKILL\.md$' })
    if ($skillFiles.Count -gt 0) {
        $sc = Join-Path $root 'tasks/check-skill-frontmatter.py'
        if (Test-Path $sc) {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP check-skill-frontmatter.py: python not found" }
            else {
                Push-Location $root
                try {
                    & $pyExe tasks/check-skill-frontmatter.py @skillFiles 2>&1 | Out-Null
                    if ($LASTEXITCODE -ne 0) { Write-Host "FAIL owning checker check-skill-frontmatter.py"; $failures++ }
                } finally { Pop-Location }
            }
        }
    }

    if ($failures -eq 0) { Write-Host "OK"; exit 0 }
    else { Write-Host "FAILED: $failures problem(s)"; exit 1 }
} catch {
    Write-Host "error: $_"
    exit 2
}
