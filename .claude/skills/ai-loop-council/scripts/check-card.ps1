<#
.SYNOPSIS
  Validate an agent playbook card file against the playbook card format and safety invariants.

.DESCRIPTION
  Playbook cards live in .claude/skills/ai-loop-council/cards/<name>.md and define structured
  task packets, worked examples, decomposition steps, verifier contracts, and failure modes.
  This script enforces:
    1. Valid YAML frontmatter with all required keys (card, class, when, not_when, verifier,
       profiles, max_output, budget_calls, status, and validated_against if status=validated).
    2. Card name in frontmatter matches the file basename without .md.
    3. Verifier resolves inside the skills tree and exists on disk.
    4. All 7 required markdown sections exist:
       - ## Packet skeleton
       - ## Worked example
       - ## Decomposition
       - ## Verifier contract
       - ## Known failure modes
       - ## Do-not examples
       - ## Escalation
    5. Worked example is at most 60 lines.
    6. Every symptom text in ## Known failure modes is literally produced by the verifier script.

.PARAMETER CardFile
  Path to a card .md file or directory of cards to check.

.PARAMETER SelfTest
  Run the test suite verifying that all guards reject invalid cards and accept valid ones.
#>
param(
    [string] $CardFile,
    [switch] $SelfTest
)

$ErrorActionPreference = 'Stop'

function Test-CardFileInternal([string] $Path, [ref] $ErrorMessage) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        $ErrorMessage.Value = "Card file not found: $Path"
        return $false
    }
    if (-not ($Path.EndsWith('.md', [StringComparison]::OrdinalIgnoreCase))) {
        $ErrorMessage.Value = "Card file must be a markdown (.md) file: $Path"
        return $false
    }

    $raw = Get-Content -Raw -LiteralPath $Path -Encoding utf8
    $fileNameWithoutExt = [IO.Path]::GetFileNameWithoutExtension($Path)

    # 1. Frontmatter check
    if ($raw -notmatch '(?s)^---\r?\n(.*?)\r?\n---\r?\n(.*)$') {
        $ErrorMessage.Value = "Card is missing YAML frontmatter enclosed in '---': $Path"
        return $false
    }

    $fmText = $matches[1]
    $bodyText = $matches[2]

    $fm = @{}
    foreach ($line in ($fmText -split '\r?\n')) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        if ($trimmed -match '^([a-zA-Z0-9_]+)\s*:\s*(.*?)(?:\s+#.*)?$') {
            $key = $matches[1].ToLowerInvariant()
            $val = $matches[2].Trim()
            $fm[$key] = $val
        }
    }

    $requiredKeys = @('card', 'class', 'when', 'not_when', 'verifier', 'profiles', 'max_output', 'budget_calls', 'status')
    foreach ($k in $requiredKeys) {
        if (-not $fm.ContainsKey($k) -or [string]::IsNullOrWhiteSpace($fm[$k])) {
            $ErrorMessage.Value = "Frontmatter missing required key '$k': $Path"
            return $false
        }
    }

    if ($fm['card'] -ne $fileNameWithoutExt) {
        $ErrorMessage.Value = "Frontmatter 'card: $($fm['card'])' does not match filename '$fileNameWithoutExt': $Path"
        return $false
    }

    $allowedClasses = @('generate', 'check', 'fix', 'review', 'convert', 'test')
    if ($allowedClasses -notcontains $fm['class']) {
        $ErrorMessage.Value = "Frontmatter 'class: $($fm['class'])' must be one of: $($allowedClasses -join ', '): $Path"
        return $false
    }

    $allowedStatuses = @('draft', 'validated')
    if ($allowedStatuses -notcontains $fm['status']) {
        $ErrorMessage.Value = "Frontmatter 'status: $($fm['status'])' must be one of: $($allowedStatuses -join ', '): $Path"
        return $false
    }

    if ($fm['status'] -eq 'validated') {
        if (-not $fm.ContainsKey('validated_against') -or [string]::IsNullOrWhiteSpace($fm['validated_against'])) {
            $ErrorMessage.Value = "Card status is 'validated' but missing required 'validated_against' key: $Path"
            return $false
        }
    }

    # 2. Verifier path check (must resolve inside skills folder and exist)
    $cardDir = Split-Path -Parent ([IO.Path]::GetFullPath($Path))
    $verifierRel = $fm['verifier']
    $verifierFull = [IO.Path]::GetFullPath((Join-Path $cardDir $verifierRel))

    if ($verifierFull -notmatch '[\\/](skills|\.claude[\\/]skills|\.github[\\/]skills|cf-skills)[\\/]') {
        $ErrorMessage.Value = "Verifier path '$verifierRel' resolves outside skills folder ($verifierFull): $Path"
        return $false
    }

    if (-not (Test-Path -LiteralPath $verifierFull -PathType Leaf)) {
        $ErrorMessage.Value = "Verifier script does not exist at resolved path '$verifierFull': $Path"
        return $false
    }

    # 3. Check 7 required sections
    $requiredSections = @(
        'Packet skeleton',
        'Worked example',
        'Decomposition',
        'Verifier contract',
        'Known failure modes',
        'Do-not examples',
        'Escalation'
    )

    foreach ($sec in $requiredSections) {
        $pattern = "(?m)^##\s+" + [regex]::Escape($sec) + "\b"
        if ($bodyText -notmatch $pattern) {
            $ErrorMessage.Value = "Missing required section '## $sec': $Path"
            return $false
        }
    }

    # 4. Check worked example length (at most 60 lines)
    if ($bodyText -match '(?ms)^##\s+Worked example\s*\r?\n(.*?)(?=\r?\n##\s+|\Z)') {
        $workedExample = $matches[1].Trim()
        $lines = $workedExample -split '\r?\n'
        if ($lines.Count -gt 60) {
            $ErrorMessage.Value = "Worked example longer than 60 lines ($($lines.Count) lines): $Path"
            return $false
        }
    }

    # 5. Check failure mode symptom alignment with verifier source
    $verifierSource = Get-Content -Raw -LiteralPath $verifierFull -Encoding utf8
    if ($bodyText -match '(?ms)^##\s+Known failure modes\s*\r?\n(.*?)(?=\r?\n##\s+|\Z)') {
        $fmSection = $matches[1]
        $symptoms = @()
        foreach ($line in ($fmSection -split '\r?\n')) {
            $trimmed = $line.Trim()
            if ($trimmed.StartsWith('|') -and $trimmed -match '\|\s*(?:`([^`]+)`|([^|]+))\s*\|') {
                $candidate = if ($matches[1]) { $matches[1].Trim() } else { $matches[2].Trim() }
                if ($candidate -and -not ($candidate -match '^[-\s:]+$') -and $candidate -ne 'Symptom' -and $candidate -match 'FAIL') {
                    $symptoms += $candidate
                }
            } elseif ($trimmed -match 'FAIL\s+[A-Za-z0-9_-]+') {
                if ($trimmed -match '`([^`]+)`') {
                    $symptoms += $matches[1].Trim()
                } else {
                    $symptoms += $trimmed
                }
            }
        }

        foreach ($sym in $symptoms) {
            # Normalize regex / literal check: symptom text or its primary token must appear in verifier
            $coreToken = if ($sym -match '(FAIL\s+[A-Za-z0-9_-]+(?::\s*[^,\r\n]+)?)') { $matches[1] } else { $sym }
            if (-not $verifierSource.Contains($coreToken) -and -not ($verifierSource -match [regex]::Escape($coreToken))) {
                $ErrorMessage.Value = "Failure-mode symptom '$coreToken' is not produced by verifier ($verifierRel): $Path"
                return $false
            }
        }
    }

    return $true
}

if ($SelfTest) {
    Write-Host "Running check-card.ps1 -SelfTest..."
    $testBase = Join-Path ([IO.Path]::GetTempPath()) ("check-card-selftest-" + [guid]::NewGuid().ToString('N'))
    $skillsDir = Join-Path $testBase "skills\test-skill\cards"
    $scriptsDir = Join-Path $skillsDir "scripts"
    New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null

    $passCount = 0
    $failCount = 0

    function Assert-Test([string] $Name, [bool] $Condition, [string] $Detail = "") {
        if ($Condition) {
            Write-Host "PASS $Name"
            $script:passCount++
        } else {
            Write-Host "FAIL $Name : $Detail"
            $script:failCount++
        }
    }

    try {
        # Create a valid stub verifier
        $vFile = Join-Path $scriptsDir "verify-test.py"
        $vLines = @(
            'import sys',
            '# FAIL R-01 usage: expected exit 2 got traceback',
            '# FAIL R-02 syntax: invalid syntax',
            'print("FAIL R-01 usage: expected exit 2 got traceback")',
            'print("FAIL R-02 syntax: invalid syntax")',
            'sys.exit(1)'
        )
        Set-Content -LiteralPath $vFile -Value ($vLines -join [Environment]::NewLine) -Encoding utf8

        # Helper to generate card text
        function Get-CardText([hashtable] $Overrides) {
            $cardName = if ($Overrides.ContainsKey('card')) { $Overrides['card'] } else { 'test-card' }
            $status = if ($Overrides.ContainsKey('status')) { $Overrides['status'] } else { 'draft' }
            $valAgainst = if ($Overrides.ContainsKey('validated_against')) { "validated_against: $($Overrides['validated_against'])`n" } elseif ($status -eq 'validated') { "validated_against: bare-run-1 2026-10-15 3/3`n" } else { "" }
            $verifier = if ($Overrides.ContainsKey('verifier')) { $Overrides['verifier'] } else { 'scripts/verify-test.py' }
            $workedEx = if ($Overrides.ContainsKey('worked_example')) { $Overrides['worked_example'] } else { "def test(): pass" }
            $row1 = '| FAIL R-01 usage: expected exit 2 got traceback | Cause | Fix |'
            $row2 = '| FAIL R-02 syntax: invalid syntax | Syntax error | Fix syntax |'
            $defaultFm = ($row1, $row2) -join [Environment]::NewLine
            $failureModes = if ($Overrides.ContainsKey('failure_modes')) { $Overrides['failure_modes'] } else { $defaultFm }
            $escalation = if ($Overrides.ContainsKey('omit_escalation')) { "" } else { "## Escalation`nEscalate to human maintainer if repeated failures.`n" }

            $cardLines = @(
                '---',
                "card: $cardName",
                'class: check',
                'when: Test condition when this card is selected.',
                'not_when: Do not select for other tasks.',
                "verifier: $verifier",
                'profiles: fast,fast,medium',
                'max_output: 8192',
                'budget_calls: 5',
                "status: $status"
            )
            if ($valAgainst) { $cardLines += $valAgainst.Trim() }
            $cardLines += @(
                '---',
                '## Packet skeleton',
                'Skeleton packet content.',
                '',
                '## Worked example',
                $workedEx,
                '',
                '## Decomposition',
                '1. Step one.',
                '2. Step two.',
                '',
                '## Verifier contract',
                'FAIL R-01 usage: expected exit 2 got traceback',
                'FAIL R-02 syntax: invalid syntax',
                '',
                '## Known failure modes',
                $failureModes,
                '',
                '## Do-not examples',
                'Do not use eval().',
                ''
            )
            if ($escalation) { $cardLines += $escalation.Trim() }
            return ($cardLines -join [Environment]::NewLine)
        }

        # Case 1: Missing section
        $c1 = Join-Path $skillsDir "case1-missing-sec.md"
        Set-Content -LiteralPath $c1 -Value (Get-CardText @{ card = 'case1-missing-sec'; omit_escalation = $true }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c1 ([ref]$err)
        Assert-Test "Guard 1: rejects card missing required section" (-not $ok -and $err -match "Missing required section '## Escalation'") $err

        # Case 2: Verifier path outside skills folder
        $c2 = Join-Path $skillsDir "case2-outside-verifier.md"
        $outsideVerifier = "../../../outside-verify.py"
        Set-Content -LiteralPath $c2 -Value (Get-CardText @{ card = 'case2-outside-verifier'; verifier = $outsideVerifier }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c2 ([ref]$err)
        Assert-Test "Guard 2: rejects verifier path outside skills folder" (-not $ok -and $err -match "resolves outside skills folder") $err

        # Case 3: Worked example longer than 60 lines
        $longEx = (1..65 | ForEach-Object { "# line $_" }) -join "`n"
        $c3 = Join-Path $skillsDir "case3-long-example.md"
        Set-Content -LiteralPath $c3 -Value (Get-CardText @{ card = 'case3-long-example'; worked_example = $longEx }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c3 ([ref]$err)
        Assert-Test "Guard 3: rejects worked example longer than 60 lines" (-not $ok -and $err -match "longer than 60 lines") $err

        # Case 4: Failure mode symptom not produced by verifier
        $badFm = '| FAIL R-99 imaginary symptom not in verifier | Unknown | Unknown |'
        $c4 = Join-Path $skillsDir "case4-unmatched-symptom.md"
        Set-Content -LiteralPath $c4 -Value (Get-CardText @{ card = 'case4-unmatched-symptom'; failure_modes = $badFm }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c4 ([ref]$err)
        Assert-Test "Guard 4: rejects failure-mode symptom not produced by verifier" (-not $ok -and $err -match "not produced by verifier") $err

        # Case 5: Status validated without validated_against
        $c5 = Join-Path $skillsDir "case5-no-val-against.md"
        Set-Content -LiteralPath $c5 -Value (Get-CardText @{ card = 'case5-no-val-against'; status = 'validated'; validated_against = $null }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c5 ([ref]$err)
        Assert-Test "Guard 5: rejects status 'validated' without validated_against" (-not $ok -and $err -match "missing required 'validated_against'") $err

        # Case 6: Positive control (valid draft card and valid validated card)
        $c6 = Join-Path $skillsDir "case6-valid-card.md"
        Set-Content -LiteralPath $c6 -Value (Get-CardText @{ card = 'case6-valid-card'; status = 'draft' }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c6 ([ref]$err)
        Assert-Test "Positive Control: accepts valid draft card" ($ok) $err

        $c7 = Join-Path $skillsDir "case7-valid-validated.md"
        Set-Content -LiteralPath $c7 -Value (Get-CardText @{ card = 'case7-valid-validated'; status = 'validated'; validated_against = 'bare-run-1 2026-10-15 3/3' }) -Encoding utf8
        $err = ""
        $ok = Test-CardFileInternal $c7 ([ref]$err)
        Assert-Test "Positive Control: accepts valid validated card" ($ok) $err
    }
    finally {
        if (Test-Path -LiteralPath $testBase) {
            Remove-Item -Recurse -Force -LiteralPath $testBase -ErrorAction SilentlyContinue
        }
    }

    Write-Host "SelfTest completed: $passCount passed, $failCount failed."
    if ($failCount -gt 0) { exit 1 } else { exit 0 }
}

# Normal execution on provided CardFile or cards directory
if (-not $CardFile) {
    $CardFile = Join-Path $PSScriptRoot "../cards"
}

$targetFiles = @()
if (Test-Path -LiteralPath $CardFile -PathType Container) {
    $targetFiles = Get-ChildItem -LiteralPath $CardFile -Filter "*.md" | ForEach-Object { $_.FullName }
} elseif (Test-Path -LiteralPath $CardFile -PathType Leaf) {
    $targetFiles = @($CardFile)
} else {
    Write-Host "error: Card path not found: $CardFile"
    exit 2
}

$anyFailed = $false
foreach ($file in $targetFiles) {
    $err = ""
    $ok = Test-CardFileInternal $file ([ref]$err)
    if ($ok) {
        Write-Host "PASS $($file)"
    } else {
        Write-Host "FAIL $($file): $err"
        $anyFailed = $true
    }
}

if ($anyFailed) { exit 1 } else { exit 0 }
