#Requires -Version 7
<#
.SYNOPSIS
    Links or verifies .claude/skills directories into .agents/skills for tools that discover .agents/skills.

.DESCRIPTION
    Creates local filesystem links (NTFS junctions on Windows, symbolic links on Linux/macOS)
    from .agents/skills/<name> to .claude/skills/<name>.
    This allows agents and IDEs looking for .agents/skills/ to discover skills natively
    without duplicating tracked files in git. The .agents/skills/ directory is git-ignored.

    Exit codes:
      0: All operations succeeded or all checks passed.
      1: An operation failed or a check reported missing/broken links.
      2: Usage error (invalid arguments, conflicting switches, or missing root).

.PARAMETER RepoRoot
    Path to the cf-lab repository root. Defaults to the repository root enclosing this script.

.PARAMETER Check
    Read-only check: verifies that every skill in .claude/skills has a corresponding valid link in .agents/skills.

.PARAMETER Remove
    Removes existing links in .agents/skills.

.PARAMETER Force
    Replaces existing links or conflicting directories.

.PARAMETER SelfTest
    Runs an isolated test suite in a temporary directory and exits.

.EXAMPLE
    pwsh -NoProfile -File link-agent-skills.ps1
    pwsh -NoProfile -File link-agent-skills.ps1 -Check
    pwsh -NoProfile -File link-agent-skills.ps1 -Remove
    pwsh -NoProfile -File link-agent-skills.ps1 -SelfTest
#>
[CmdletBinding(DefaultParameterSetName = 'Link')]
param(
    [Parameter(ParameterSetName = 'Link')]
    [Parameter(ParameterSetName = 'Check')]
    [Parameter(ParameterSetName = 'Remove')]
    [string] $RepoRoot,

    [Parameter(ParameterSetName = 'Check', Mandatory = $true)]
    [switch] $Check,

    [Parameter(ParameterSetName = 'Remove', Mandatory = $true)]
    [switch] $Remove,

    [Parameter(ParameterSetName = 'Link')]
    [switch] $Force,

    [Parameter(ParameterSetName = 'SelfTest', Mandatory = $true)]
    [switch] $SelfTest
)

$ErrorActionPreference = 'Stop'

function Invoke-SelfTest {
    $tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("link-agent-skills-test-" + [System.Guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    try {
        $claudeSkills = Join-Path $tempDir '.claude/skills'
        $agentsSkills = Join-Path $tempDir '.agents/skills'
        New-Item -ItemType Directory -Path (Join-Path $claudeSkills 'skill-one') | Out-Null
        Set-Content -LiteralPath (Join-Path $claudeSkills 'skill-one/SKILL.md') -Value "--`nname: skill-one`n--`n" -NoNewline
        New-Item -ItemType Directory -Path (Join-Path $claudeSkills 'skill-two') | Out-Null
        Set-Content -LiteralPath (Join-Path $claudeSkills 'skill-two/SKILL.md') -Value "--`nname: skill-two`n--`n" -NoNewline

        # 1. Link skills
        $linkRes = Invoke-LinkSkills -Root $tempDir -ForceOverwrite $false -Quiet $true
        if ($linkRes -ne 0) {
            throw "SelfTest failed: Invoke-LinkSkills returned $linkRes"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $agentsSkills 'skill-one'))) {
            throw "SelfTest failed: skill-one was not linked"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $agentsSkills 'skill-two'))) {
            throw "SelfTest failed: skill-two was not linked"
        }

        # 2. Check links
        $checkRes = Invoke-CheckSkills -Root $tempDir -Quiet $true
        if ($checkRes -ne 0) {
            throw "SelfTest failed: Invoke-CheckSkills returned $checkRes"
        }

        # 3. Remove links
        $removeRes = Invoke-RemoveSkills -Root $tempDir -Quiet $true
        if ($removeRes -ne 0) {
            throw "SelfTest failed: Invoke-RemoveSkills returned $removeRes"
        }
        if (Test-Path -LiteralPath (Join-Path $agentsSkills 'skill-one')) {
            throw "SelfTest failed: skill-one was not removed"
        }

        Write-Host "PASS link-agent-skills self-test: link, check, remove verified"
        return 0
    }
    finally {
        if (Test-Path -LiteralPath $tempDir) {
            $agentsSkills = Join-Path $tempDir '.agents/skills'
            if (Test-Path -LiteralPath $agentsSkills) {
                Invoke-RemoveSkills -Root $tempDir -Quiet $true | Out-Null
            }
            Remove-Item -LiteralPath $tempDir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-LinkSkills([string] $Root, [bool] $ForceOverwrite, [bool] $Quiet = $false) {
    $claudeDir = Join-Path $Root '.claude/skills'
    $agentsDir = Join-Path $Root '.agents/skills'

    if (-not (Test-Path -LiteralPath $claudeDir)) {
        [Console]::Error.WriteLine("Source skills directory not found: $claudeDir")
        return 1
    }

    if (-not (Test-Path -LiteralPath $agentsDir)) {
        New-Item -ItemType Directory -Path $agentsDir | Out-Null
    }

    $skillDirs = Get-ChildItem -LiteralPath $claudeDir -Directory | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')
    }

    $linkedCount = 0
    $skippedCount = 0
    $failedCount = 0

    foreach ($dir in $skillDirs) {
        $targetPath = $dir.FullName
        $linkPath = Join-Path $agentsDir $dir.Name

        if (Test-Path -LiteralPath $linkPath) {
            if ($ForceOverwrite) {
                try {
                    Remove-Item -LiteralPath $linkPath -Force -Recurse
                } catch {
                    [Console]::Error.WriteLine("Failed to remove existing item at $($linkPath): $_")
                    $failedCount++
                    continue
                }
            } else {
                $skippedCount++
                continue
            }
        }

        try {
            if ($IsWindows) {
                New-Item -ItemType Junction -Path $linkPath -Target $targetPath | Out-Null
            } else {
                New-Item -ItemType SymbolicLink -Path $linkPath -Target $targetPath | Out-Null
            }
            $linkedCount++
        } catch {
            [Console]::Error.WriteLine("Failed to link $($dir.Name): $_")
            $failedCount++
        }
    }

    if (-not $Quiet) {
        Write-Host "Linked $linkedCount skill(s) into $agentsDir ($skippedCount already present, $failedCount failed)."
    }

    if ($failedCount -gt 0) {
        return 1
    }
    return 0
}

function Invoke-CheckSkills([string] $Root, [bool] $Quiet = $false) {
    $claudeDir = Join-Path $Root '.claude/skills'
    $agentsDir = Join-Path $Root '.agents/skills'

    if (-not (Test-Path -LiteralPath $claudeDir)) {
        [Console]::Error.WriteLine("Source directory not found: $claudeDir")
        return 1
    }

    $skillDirs = Get-ChildItem -LiteralPath $claudeDir -Directory | Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md')
    }

    $missing = @()
    $invalid = @()

    foreach ($dir in $skillDirs) {
        $linkPath = Join-Path $agentsDir $dir.Name
        if (-not (Test-Path -LiteralPath $linkPath)) {
            $missing += $dir.Name
            continue
        }

        try {
            $item = Get-Item -LiteralPath $linkPath -Force
            if (-not ($item.LinkType -in @('Junction', 'SymbolicLink'))) {
                $invalid += "$($dir.Name) (not a link)"
            }
        } catch {
            $invalid += "$($dir.Name) (unreadable link)"
        }
    }

    if ($missing.Count -eq 0 -and $invalid.Count -eq 0) {
        if (-not $Quiet) {
            Write-Host "PASS agent skills links: all $($skillDirs.Count) skill(s) linked in $agentsDir"
        }
        return 0
    } else {
        if (-not $Quiet) {
            $issues = @()
            if ($missing.Count -gt 0) { $issues += "$($missing.Count) missing: $($missing -join ', ')" }
            if ($invalid.Count -gt 0) { $issues += "$($invalid.Count) invalid: $($invalid -join ', ')" }
            Write-Host "FAIL agent skills links: $($issues -join '; ')"
        }
        return 1
    }
}

function Invoke-RemoveSkills([string] $Root, [bool] $Quiet = $false) {
    $agentsDir = Join-Path $Root '.agents/skills'
    if (-not (Test-Path -LiteralPath $agentsDir)) {
        if (-not $Quiet) {
            Write-Host "Nothing to remove: $agentsDir does not exist."
        }
        return 0
    }

    $items = Get-ChildItem -LiteralPath $agentsDir -Force
    $removed = 0
    $failed = 0

    foreach ($item in $items) {
        try {
            Remove-Item -LiteralPath $item.FullName -Force -Recurse
            $removed++
        } catch {
            [Console]::Error.WriteLine("Failed to remove $($item.FullName): $_")
            $failed++
        }
    }

    if (-not $Quiet) {
        Write-Host "Removed $removed link(s) from $agentsDir ($failed failed)."
    }

    if ($failed -gt 0) {
        return 1
    }
    return 0
}

# --- Main Entry Point ---

if ($SelfTest) {
    $code = Invoke-SelfTest
    exit $code
}

if (-not $RepoRoot) {
    # Script is in .claude/skills/workspace-siblings/scripts/
    $scriptsDir = $PSScriptRoot
    $skillsDir = Split-Path -Parent (Split-Path -Parent $scriptsDir)
    $claudeDir = Split-Path -Parent $skillsDir
    $RepoRoot = Split-Path -Parent $claudeDir
}

if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) {
    [Console]::Error.WriteLine("Repository root directory not found or not a directory: $RepoRoot")
    exit 2
}

if ($Remove) {
    $code = Invoke-RemoveSkills -Root $RepoRoot
    exit $code
}

if ($Check) {
    $code = Invoke-CheckSkills -Root $RepoRoot
    exit $code
}

$code = Invoke-LinkSkills -Root $RepoRoot -ForceOverwrite $Force.IsPresent
exit $code
