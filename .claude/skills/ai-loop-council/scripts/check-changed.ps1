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

    if ($files | Where-Object { $_ -eq 'tasks/board.json' -or $_ -eq 'tasks/HUMAN-TASKS.md' -or $_ -eq 'tasks/sentinels.json' -or $_ -eq 'AGENTS.md' -or $_ -cmatch '^tasks/sentinel-prompts/' }) {
        $ah = Join-Path $root 'tasks/check_anti_hallucination.py'
        if (Test-Path $ah) {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP check_anti_hallucination.py: python not found" }
            else {
                Push-Location $root
                try {
                    $ahOut = (& $pyExe tasks/check_anti_hallucination.py 2>&1) -join "`n"
                    if ($LASTEXITCODE -ne 0) {
                        if ($ahOut) { Write-Host $ahOut }
                        Write-Host "FAIL owning checker check_anti_hallucination.py"
                        $failures++
                    }
                } finally { Pop-Location }
            }
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

    if ($files | Where-Object { $_ -eq 'THIRD_PARTY_SKILLS.md' -or $_ -eq 'tasks/check_third_party_skills.py' }) {
        $tps = Join-Path $root 'tasks/check_third_party_skills.py'
        if (Test-Path $tps) {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP check_third_party_skills.py: python not found" }
            else {
                Push-Location $root
                try {
                    $tpsOut = (& $pyExe tasks/check_third_party_skills.py 2>&1) -join "`n"
                    if ($LASTEXITCODE -ne 0) {
                        if ($tpsOut) { Write-Host $tpsOut }
                        Write-Host "FAIL owning checker check_third_party_skills.py"
                        $failures++
                    }
                } finally { Pop-Location }
            }
        }
    }

    if ($files | Where-Object { $_ -eq 'docs/biomcp-admission-review.md' -or $_ -eq 'tasks/check_biomcp_admission.py' }) {
        $bma = Join-Path $root 'tasks/check_biomcp_admission.py'
        if (Test-Path $bma) {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP check_biomcp_admission.py: python not found" }
            else {
                Push-Location $root
                try {
                    $bmaOut = (& $pyExe tasks/check_biomcp_admission.py 2>&1) -join "`n"
                    if ($LASTEXITCODE -ne 0) {
                        if ($bmaOut) { Write-Host $bmaOut }
                        Write-Host "FAIL owning checker check_biomcp_admission.py"
                        $failures++
                    }
                } finally { Pop-Location }
            }
        }
    }

    # Catalog snapshot and skill catalog drift checks (T-0051, T-0140)
    if ($files | Where-Object { $_ -eq 'sources/catalog.snapshot.yaml' -or $_ -eq 'tasks/sync_catalog_snapshot.py' }) {
        $scs = Join-Path $root 'tasks/sync_catalog_snapshot.py'
        if (Test-Path $scs) {
            $pyExe = Get-PythonExe
            if (-not $pyExe) { Write-Host "SKIP sync_catalog_snapshot.py: python not found" }
            else {
                $tmpSnap = $null
                try {
                    $snapTarget = Join-Path $root 'sources/catalog.snapshot.yaml'
                    if ($files -contains 'sources/catalog.snapshot.yaml') {
                        $tmpSnap = [IO.Path]::GetTempFileName()
                        $snapStaged = (Get-StagedText 'sources/catalog.snapshot.yaml')
                        if (-not $snapStaged.EndsWith("`n")) { $snapStaged += "`n" }
                        [IO.File]::WriteAllText($tmpSnap, $snapStaged, [Text.UTF8Encoding]::new($false))
                        $snapTarget = $tmpSnap
                    }
                    $scsOut = (& $pyExe $scs --check --snapshot $snapTarget 2>&1) -join "`n"
                    if ($LASTEXITCODE -ne 0) {
                        if ($scsOut) { Write-Host $scsOut }
                        Write-Host "FAIL owning checker sync_catalog_snapshot.py --check"
                        $failures++
                    }
                } finally {
                    if ($tmpSnap) { Remove-Item -LiteralPath $tmpSnap -ErrorAction SilentlyContinue }
                }
            }
        }
    }

    $catStaged = @($files | Where-Object { $_ -eq 'sources/catalog.yaml' -or $_ -eq '.claude/skills/cf-evidence-loop/catalog.yaml' })
    if ($catStaged.Count -gt 0) {
        $pyExe = Get-PythonExe
        if (-not $pyExe) { Write-Host "SKIP sync_skill_catalog.py: python not found" }
        else {
            $syncScript = $null
            foreach ($cand in @(
                (Join-Path $root 'tools/sources/sync_skill_catalog.py'),
                (Join-Path $root '../cf-research/tools/sources/sync_skill_catalog.py'),
                (Join-Path $root '../../cf-research/tools/sources/sync_skill_catalog.py'),
                (Join-Path $root '../../../cf-research/tools/sources/sync_skill_catalog.py')
            )) {
                if (Test-Path -LiteralPath $cand -PathType Leaf) { $syncScript = (Resolve-Path -LiteralPath $cand).Path; break }
            }
            $srcCat = $null
            foreach ($cand in @(
                (Join-Path $root 'sources/catalog.yaml'),
                (Join-Path $root '../cf-research/sources/catalog.yaml'),
                (Join-Path $root '../../cf-research/sources/catalog.yaml'),
                (Join-Path $root '../../../cf-research/sources/catalog.yaml')
            )) {
                if (Test-Path -LiteralPath $cand -PathType Leaf) { $srcCat = (Resolve-Path -LiteralPath $cand).Path; break }
            }
            $dstCat = $null
            foreach ($cand in @(
                (Join-Path $root '.claude/skills/cf-evidence-loop/catalog.yaml'),
                (Join-Path $root '../cf-skills/.claude/skills/cf-evidence-loop/catalog.yaml'),
                (Join-Path $root '../../cf-skills/.claude/skills/cf-evidence-loop/catalog.yaml'),
                (Join-Path $root '../../../cf-skills/.claude/skills/cf-evidence-loop/catalog.yaml')
            )) {
                if (Test-Path -LiteralPath $cand -PathType Leaf) { $dstCat = (Resolve-Path -LiteralPath $cand).Path; break }
            }
            if ($syncScript -and $srcCat -and $dstCat) {
                $tmpSrc = $null; $tmpDst = $null
                try {
                    if ($files -contains 'sources/catalog.yaml') {
                        $tmpSrc = [IO.Path]::GetTempFileName()
                        [IO.File]::WriteAllText($tmpSrc, (Get-StagedText 'sources/catalog.yaml'), [Text.UTF8Encoding]::new($false))
                        $srcCat = $tmpSrc
                    }
                    if ($files -contains '.claude/skills/cf-evidence-loop/catalog.yaml') {
                        $tmpDst = [IO.Path]::GetTempFileName()
                        [IO.File]::WriteAllText($tmpDst, (Get-StagedText '.claude/skills/cf-evidence-loop/catalog.yaml'), [Text.UTF8Encoding]::new($false))
                        $dstCat = $tmpDst
                    }
                    $syncOut = (& $pyExe $syncScript --source $srcCat --target $dstCat --check 2>&1) -join "`n"
                    if ($LASTEXITCODE -ne 0) {
                        if ($syncOut) { Write-Host $syncOut }
                        Write-Host "FAIL owning checker sync_skill_catalog.py --check"
                        $failures++
                    }
                } finally {
                    if ($tmpSrc) { Remove-Item -LiteralPath $tmpSrc -ErrorAction SilentlyContinue }
                    if ($tmpDst) { Remove-Item -LiteralPath $tmpDst -ErrorAction SilentlyContinue }
                }
            }
        }
    }

    # cf-research source-overlap, quotation-length, and stated-evidence number checks (T-0074)
    $csoScript = Join-Path $root 'tools/sources/check_source_overlap.py'
    $csoFiles = @($files | Where-Object {
        $_ -notmatch '(^|/)known-wrong/' -and
        ([System.IO.Path]::GetExtension($_).ToLowerInvariant() -in @('.md', '.yaml', '.yml'))
    })
    if ((Test-Path -LiteralPath $csoScript -PathType Leaf) -and $csoFiles.Count -gt 0) {
        $pyExe = Get-PythonExe
        if (-not $pyExe) { Write-Host "SKIP check_source_overlap.py: python not found" }
        else {
            $stageMirror = Join-Path ([IO.Path]::GetTempPath()) ('cso-staged-' + [guid]::NewGuid().ToString('N'))
            New-Item -ItemType Directory -Force -Path $stageMirror | Out-Null
            try {
                foreach ($f in $files) {
                    $dest = Join-Path $stageMirror $f
                    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
                    [IO.File]::WriteAllText($dest, (Get-StagedText $f), [Text.UTF8Encoding]::new($false))
                }
                $stagedMd = @($csoFiles | Where-Object { [System.IO.Path]::GetExtension($_).ToLowerInvariant() -eq '.md' } | ForEach-Object { Join-Path $stageMirror $_ })
                $stagedOverlap = @($csoFiles | ForEach-Object { Join-Path $stageMirror $_ })

                if ($stagedMd.Count -gt 0) {
                    $qOut = (& $pyExe $csoScript --quotes-only @stagedMd 2>&1) -join "`n"
                    if ($LASTEXITCODE -ne 0) {
                        if ($qOut) { Write-Host $qOut }
                        Write-Host "FAIL owning checker check_source_overlap.py --quotes-only"
                        $failures++
                    }
                }

                $dlDir = Join-Path $root 'sources/downloads'
                if (-not (Test-Path -LiteralPath $dlDir -PathType Container)) {
                    Write-Host "SKIP check_source_overlap.py: sources/downloads does not exist"
                } else {
                    $oOut = (& $pyExe $csoScript --max-quote 0 --sources $dlDir @stagedOverlap 2>&1) -join "`n"
                    if ($LASTEXITCODE -eq 2 -and $oOut -match 'no \.txt or \.pdf files|pdftotext is not installed') {
                        Write-Host "SKIP check_source_overlap.py: $oOut"
                    } elseif ($LASTEXITCODE -ne 0) {
                        if ($oOut) { Write-Host $oOut }
                        Write-Host "FAIL owning checker check_source_overlap.py"
                        $failures++
                    }
                }

                $cnScript = Join-Path $root 'tools/sources/check_numbers.py'
                if (Test-Path -LiteralPath $cnScript -PathType Leaf) {
                    foreach ($mdRel in @($csoFiles | Where-Object { [System.IO.Path]::GetExtension($_).ToLowerInvariant() -eq '.md' })) {
                        $mdStagedPath = Join-Path $stageMirror $mdRel
                        $mdText = [IO.File]::ReadAllText($mdStagedPath, [Text.UTF8Encoding]::new($false))
                        $evList = @()
                        foreach ($m in [regex]::Matches($mdText, '(?im)^(?:<!--\s*)?evidence(?:-file)?\s*:\s*([^\r\n>]+?)(?:\s*-->)?\s*$')) {
                            $rawEv = $m.Groups[1].Value.Trim()
                            $candStage = Join-Path $stageMirror $rawEv
                            $candRoot = Join-Path $root $rawEv
                            $candRel = Join-Path (Split-Path -Parent (Join-Path $root $mdRel)) $rawEv
                            if (Test-Path -LiteralPath $candStage) { $evList += $candStage }
                            elseif (Test-Path -LiteralPath $candRoot) { $evList += $candRoot }
                            elseif (Test-Path -LiteralPath $candRel) { $evList += $candRel }
                            else { $evList += $candRoot }
                        }
                        $stemRel = [IO.Path]::ChangeExtension($mdRel, $null).TrimEnd('.')
                        $compEvStage = Join-Path $stageMirror ($stemRel + '-evidence.txt')
                        $compEvRoot = Join-Path $root ($stemRel + '-evidence.txt')
                        if ($evList.Count -eq 0) {
                            if (Test-Path -LiteralPath $compEvStage -PathType Leaf) { $evList += $compEvStage }
                            elseif (Test-Path -LiteralPath $compEvRoot -PathType Leaf) { $evList += $compEvRoot }
                        }
                        if ($evList.Count -gt 0) {
                            $allowPath = $null
                            $am = [regex]::Match($mdText, '(?im)^(?:<!--\s*)?allow-file\s*:\s*([^\r\n>]+?)(?:\s*-->)?\s*$')
                            if ($am.Success) {
                                $rawAl = $am.Groups[1].Value.Trim()
                                $alStage = Join-Path $stageMirror $rawAl
                                $alRoot = Join-Path $root $rawAl
                                if (Test-Path -LiteralPath $alStage -PathType Leaf) { $allowPath = $alStage }
                                else { $allowPath = $alRoot }
                            } else {
                                foreach ($suf in @('-allow.txt', '-numbers-allow.txt')) {
                                    $alStage = Join-Path $stageMirror ($stemRel + $suf)
                                    $alRoot = Join-Path $root ($stemRel + $suf)
                                    if (Test-Path -LiteralPath $alStage -PathType Leaf) { $allowPath = $alStage; break }
                                    if (Test-Path -LiteralPath $alRoot -PathType Leaf) { $allowPath = $alRoot; break }
                                }
                            }
                            $cnArgs = @()
                            foreach ($ep in $evList) { $cnArgs += @('--evidence', $ep) }
                            if ($allowPath) { $cnArgs += @('--allow-file', $allowPath) }
                            $cnArgs += $mdStagedPath
                            $cnOut = (& $pyExe $cnScript @cnArgs 2>&1) -join "`n"
                            if ($LASTEXITCODE -ne 0) {
                                if ($cnOut) { Write-Host $cnOut }
                                Write-Host "FAIL owning checker check_numbers.py ($mdRel)"
                                $failures++
                            }
                        }
                    }
                }
            } finally {
                Remove-Item -LiteralPath $stageMirror -Recurse -Force -ErrorAction SilentlyContinue
            }
        }
    }

    if ($failures -eq 0) { Write-Host "OK"; exit 0 }
    else { Write-Host "FAILED: $failures problem(s)"; exit 1 }
} catch {
    Write-Host "error: $_"
    exit 2
}
