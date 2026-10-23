#Requires -Version 7
<#
.SYNOPSIS
  Run every offline check in this repository and print one PASS, FAIL or SKIPPED line per check.

.DESCRIPTION
  The list of checks is written out below (the $Checks table), not discovered by globbing: each row names a check,
  the command it runs from the repository root, and what it needs. A check whose needs are missing on this machine
  is SKIPPED with the reason (needs Windows, needs PyYAML, needs git ...). Checks that need a browser or a model are
  listed so they stay visible, and are always SKIPPED: this runner never starts a browser, calls Ollama or a model,
  uses the network or runs an installer.

  Each check runs in its own process with a timeout (-TimeoutSec, default 300). A failure does not stop the run.
  The last line is the count. Exit 0 when nothing FAILED (SKIPPED does not fail), 1 when anything FAILED,
  2 for a usage error (an unknown -Only name, a malformed table).

  When you add a test to the repository, add a row to $Checks.

.PARAMETER List
  Print the table (name, needs, command) and run nothing.

.PARAMETER Only
  Run only the named checks (names as -List prints them).

.PARAMETER SelfTest
  Test this runner on a stub table (one passing, one failing, one skipped and one timed-out check). Runs no repo check.

.EXAMPLE
  pwsh -NoProfile -File ./check-all.ps1
  pwsh -NoProfile -File ./check-all.ps1 -List
  pwsh -NoProfile -File ./check-all.ps1 -Only render-board,test-render-board
  pwsh -NoProfile -File ./check-all.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    [switch] $List,
    [string[]] $Only,
    [ValidateRange(1, 86400)] [int] $TimeoutSec = 300,
    [switch] $SelfTest,
    # For -SelfTest only: a JSON file with a stub table in place of $Checks.
    [string] $TableFile,
    [switch] $Parallel,
    [ValidateRange(1, 32)] [int] $ThrottleLimit = 4,
    [switch] $CheckSkips,
    [string] $ExpectedSkipsFile
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot

# exe: pwsh (PowerShell 7), python (3.10 or newer).
# needs: pwsh, python, git, pyyaml, sh, windows; browser and model are never met here.
$s = '.claude/skills'
$Checks = @(
    # long-running ai-loop-council suites started first so -Parallel schedules them at t=0s
    @{ name = 'test-delegate';            exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-delegate.ps1");                                    needs = @() }
    @{ name = 'test-verifier-freeze';     exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-verifier-freeze.ps1");                             needs = @() }
    @{ name = 'test-review-diff';         exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-review-diff.ps1");                                 needs = @('python', 'git') }
    @{ name = 'test-run-gate';            exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-run-gate.ps1");                                    needs = @('git') }
    # the task board
    @{ name = 'render-board';             exe = 'pwsh';       args = @('tasks/render-board.ps1', '-Check');                                                needs = @() }
    @{ name = 'test-render-board';        exe = 'pwsh';       args = @('tasks/test-render-board.ps1');                                                     needs = @() }
    @{ name = 'test-triage-board';        exe = 'python';     args = @('tasks/test_triage_board.py');                                                      needs = @('python') }
    @{ name = 'test-audit-session-errors'; exe = 'python';    args = @('tasks/test_audit_session_errors.py');                                               needs = @('python') }
    @{ name = 'test-fast-sentinel-gate';  exe = 'pwsh';       args = @('tasks/test-fast-sentinel-gate.ps1');                                              needs = @('git') }
    @{ name = 'test-run-sentinel';        exe = 'pwsh';       args = @('tasks/test-run-sentinel.ps1');                                                    needs = @('git') }
    @{ name = 'test-pick-bold-task';      exe = 'python';     args = @('tasks/test_pick_bold_task.py');                                                    needs = @('python') }
    @{ name = 'check-anti-hallucination'; exe = 'python';     args = @('tasks/check_anti_hallucination.py');                                               needs = @('python') }
    @{ name = 'test-check-anti-hallucination'; exe = 'python'; args = @('tasks/test_check_anti_hallucination.py');                                         needs = @('python') }
    @{ name = 'check-third-party-skills'; exe = 'python';     args = @('tasks/check_third_party_skills.py');                                               needs = @('python') }
    @{ name = 'test-check-third-party-skills'; exe = 'python'; args = @('tasks/test_check_third_party_skills.py');                                         needs = @('python') }
    @{ name = 'check-biomcp-admission';   exe = 'python';     args = @('tasks/check_biomcp_admission.py');                                                 needs = @('python') }
    @{ name = 'test-check-biomcp-admission'; exe = 'python';  args = @('tasks/test_check_biomcp_admission.py');                                            needs = @('python') }
    @{ name = 'test-svg-freeze-contract'; exe = 'python';     args = @('tasks/test_svg_freeze_contract.py');                                                needs = @('python') }
    @{ name = 'skill-frontmatter';        exe = 'python';     args = @('tasks/check-skill-frontmatter.py');                                                needs = @('python', 'pyyaml') }
    # setup and the workspace
    @{ name = 'test-setup';               exe = 'python';     args = @("$s/lab-versioning/scripts/test-setup.py");                                         needs = @('python') }
    @{ name = 'check-workspace-selftest'; exe = 'python';     args = @("$s/workspace-siblings/scripts/check-workspace.py", '--self-test');                 needs = @('python', 'git') }
    @{ name = 'check-merged-selftest';    exe = 'pwsh';       args = @("$s/workspace-siblings/scripts/check-merged.ps1", '-SelfTest');                     needs = @() }
    @{ name = 'link-agent-skills-selftest'; exe = 'pwsh';     args = @("$s/workspace-siblings/scripts/link-agent-skills.ps1", '-SelfTest');                 needs = @() }
    @{ name = 'test-check-workspace';     exe = 'python';     args = @("$s/workspace-siblings/scripts/test_check_workspace.py");                           needs = @('python', 'git') }
    @{ name = 'test-worktrees';           exe = 'python';     args = @("$s/workspace-siblings/scripts/test_worktrees.py");                                 needs = @('python', 'git') }
    # ai-loop-council: routing, delegation and gate scripts (stub workers; no model)
    @{ name = 'select-work-route';        exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/select-work-route.ps1", '-SelfTest');                   needs = @() }
    @{ name = 'invoke-local-model';       exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/invoke-local-model.ps1", '-SelfTest');                  needs = @() }
    @{ name = 'test-invoke-config';       exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-invoke-config.ps1");                               needs = @() }
    @{ name = 'new-cloud-handoff';        exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/new-cloud-handoff.ps1", '-SelfTest');                   needs = @() }
    @{ name = 'injection-probe';          exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/injection-probe.ps1", '-SelfTest');                     needs = @() }
    @{ name = 'review-diversity';         exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/review-diversity.ps1", '-SelfTest');                    needs = @() }
    @{ name = 'lint-powershell';          exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/lint-powershell.ps1", '-SelfTest');                     needs = @() }
    @{ name = 'test-lint-powershell';     exe = 'python';     args = @("$s/ai-loop-council/scripts/test_lint_powershell.py");                              needs = @('python') }
    @{ name = 'test-check-changed';       exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-check-changed.ps1");                               needs = @('git') }
    @{ name = 'test-count-rendered';      exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-count-rendered.ps1");                              needs = @() }
    @{ name = 'test-guard';               exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-guard.ps1");                                       needs = @() }
    @{ name = 'test-build-review-packet'; exe = 'python';     args = @("$s/ai-loop-council/scripts/test_build_review_packet.py");                          needs = @('python', 'git') }
    @{ name = 'test-delegate-batch';      exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/test-delegate-batch.ps1");                              needs = @() }
    @{ name = 'check-quote-completeness'; exe = 'python';     args = @("$s/ai-loop-council/scripts/check-quote-completeness.py", '--self-test');           needs = @('python') }
    @{ name = 'test-check-quote';         exe = 'python';     args = @("$s/ai-loop-council/scripts/test-check-quote-completeness.py");                     needs = @('python') }
    @{ name = 'depth-probe';              exe = 'pwsh';       args = @("$s/ai-loop-council/scripts/depth-probe.ps1", '-SelfTest');                         needs = @('python') }
    @{ name = 'test-depth-probe';         exe = 'python';     args = @("$s/ai-loop-council/scripts/test_depth_probe.py");                                  needs = @('python') }
    @{ name = 'test-filter-findings';     exe = 'python';     args = @("$s/ai-loop-council/scripts/test_filter_review_findings.py");                       needs = @('python') }
    @{ name = 'test-findings-evidence';   exe = 'python';     args = @("$s/ai-loop-council/scripts/test_check_findings_evidence.py");                      needs = @('python') }
    @{ name = 'test-loop-report';         exe = 'python';     args = @("$s/ai-loop-council/scripts/test_loop_report.py");                                  needs = @('python') }
    @{ name = 'test-verify-in-copy';      exe = 'python';     args = @("$s/ai-loop-council/scripts/test_verify_in_copy.py");                               needs = @('python') }
    # security-git
    @{ name = 'run-with-env';             exe = 'pwsh';       args = @("$s/security-git/scripts/run-with-env.ps1", '-SelfTest');                           needs = @('git') }
    @{ name = 'check-staged';             exe = 'pwsh';       args = @("$s/security-git/scripts/check-staged.ps1", '-SelfTest');                           needs = @('git') }
    @{ name = 'check-lab-files';          exe = 'pwsh';       args = @("$s/security-git/scripts/check-lab-files.ps1", '-SelfTest');                        needs = @() }
    @{ name = 'test-check-lab-files';     exe = 'pwsh';       args = @("$s/security-git/scripts/test-check-lab-files.ps1");                                needs = @() }
    # security-browsing & catalog host boundaries
    @{ name = 'check-restricted-hosts';   exe = 'python';     args = @('tasks/check_restricted_hosts.py');                                                 needs = @('python', 'pyyaml') }
    @{ name = 'test-check-restricted-hosts'; exe = 'python';  args = @('tasks/test_check_restricted_hosts.py');                                            needs = @('python') }
    @{ name = 'scan-person-generalization'; exe = 'python';   args = @('tasks/scan_person_generalization.py', '--self-test');                               needs = @('python') }
    @{ name = 'test-scan-person-generalization'; exe = 'python'; args = @('tasks/test_scan_person_generalization.py');                                    needs = @('python') }
    @{ name = 'check-catalog-snapshot';   exe = 'python';     args = @('tasks/sync_catalog_snapshot.py', '--check', '--max-age-days', '3650');             needs = @('python') }
    @{ name = 'test-sync-catalog-snapshot'; exe = 'python';   args = @('tasks/test_sync_catalog_snapshot.py');                                             needs = @('python') }
    @{ name = 'check-pr-body';            exe = 'python';     args = @('tasks/check_pr_body.py', '--self-test');                                           needs = @('python') }
    @{ name = 'test-check-pr-body';       exe = 'python';     args = @('tasks/test_check_pr_body.py');                                                     needs = @('python') }
    @{ name = 'check-ci-workflows';       exe = 'python';     args = @('tasks/check_ci_workflows.py');                                                     needs = @('python') }
    @{ name = 'test-check-ci-workflows';  exe = 'python';     args = @('tasks/test_check_ci_workflows.py');                                                needs = @('python') }
    @{ name = 'test-check-codeql-patterns'; exe = 'python';   args = @('tasks/test_check_codeql_patterns.py');                                             needs = @('python') }
    @{ name = 'test-evidence-cli-launcher'; exe = 'python';   args = @('tasks/test_evidence_cli_launcher.py');                                             needs = @('python') }
    @{ name = 'check-i18n-parity';        exe = 'python';     args = @('tasks/check_i18n_parity.py', '--check');                                           needs = @('python') }
    @{ name = 'test-check-i18n-parity';   exe = 'python';     args = @('tasks/test_check_i18n_parity.py');                                                 needs = @('python') }
    @{ name = 'check-markdown-links';     exe = 'python';     args = @('tasks/check_markdown_link_integrity.py', '--check');                               needs = @('python') }
    @{ name = 'test-check-markdown-links'; exe = 'python';    args = @('tasks/test_check_markdown_link_integrity.py');                                     needs = @('python') }
    @{ name = 'check-sentinel-telemetry'; exe = 'python';     args = @('tasks/check_sentinel_telemetry_linter.py', '--check');                             needs = @('python') }
    @{ name = 'test-sentinel-telemetry';  exe = 'python';     args = @('tasks/test_check_sentinel_telemetry_linter.py');                                   needs = @('python') }
    @{ name = 'check-env-canary';         exe = 'python';     args = @('tasks/check_env_canary_isolation.py', '--check');                                  needs = @('python') }
    @{ name = 'test-env-canary';          exe = 'python';     args = @('tasks/test_check_env_canary_isolation.py');                                         needs = @('python') }
    @{ name = 'check-tool-permissions';   exe = 'python';     args = @('tasks/check_tool_permission_invariants.py', '--check');                             needs = @('python') }
    @{ name = 'test-tool-permissions';    exe = 'python';     args = @('tasks/test_check_tool_permission_invariants.py');                                    needs = @('python') }
    @{ name = 'check-git-hooks';          exe = 'python';     args = @('tasks/check_git_hooks_invariants.py', '--check');                                       needs = @('python') }
    @{ name = 'test-git-hooks';           exe = 'python';     args = @('tasks/test_check_git_hooks_invariants.py');                                            needs = @('python') }
    @{ name = 'check-playwright-hygiene'; exe = 'python';     args = @('tasks/check_playwright_test_hygiene.py', '--check');                                     needs = @('python') }
    @{ name = 'test-playwright-hygiene';  exe = 'python';     args = @('tasks/test_check_playwright_test_hygiene.py');                                           needs = @('python') }
    @{ name = 'check-supply-chain';       exe = 'python';     args = @('tasks/check_git_supply_chain_integrity.py', '--check');                                  needs = @('python') }
    @{ name = 'test-supply-chain';        exe = 'python';     args = @('tasks/test_check_git_supply_chain_integrity.py');                                       needs = @('python') }
    @{ name = 'check-unicode-homoglyphs'; exe = 'python';     args = @('tasks/check_unicode_homoglyphs.py', '--check');                                          needs = @('python') }
    @{ name = 'test-unicode-homoglyphs';  exe = 'python';     args = @('tasks/test_check_unicode_homoglyphs.py');                                               needs = @('python') }
    @{ name = 'check-env-sanitization';   exe = 'python';     args = @('tasks/check_env_sanitization_invariants.py', '--check');                                  needs = @('python') }
    @{ name = 'test-env-sanitization';    exe = 'python';     args = @('tasks/test_check_env_sanitization_invariants.py');                                       needs = @('python') }
    @{ name = 'check-file-permissions';   exe = 'python';     args = @('tasks/check_file_permission_invariants.py', '--check');                                  needs = @('python') }
    @{ name = 'test-file-permissions';    exe = 'python';     args = @('tasks/test_check_file_permission_invariants.py');                                       needs = @('python') }
    @{ name = 'check-ast-obfuscation';    exe = 'python';     args = @('tasks/check_ast_obfuscation_invariants.py', '--check');                                  needs = @('python') }
    @{ name = 'test-ast-obfuscation';     exe = 'python';     args = @('tasks/test_check_ast_obfuscation_invariants.py');                                       needs = @('python') }
    @{ name = 'check-git-author';         exe = 'python';     args = @('tasks/check_git_author_integrity.py', '--check');                                        needs = @('python') }
    @{ name = 'test-git-author';          exe = 'python';     args = @('tasks/test_check_git_author_integrity.py');                                             needs = @('python') }
    @{ name = 'check-prompt-injection';   exe = 'python';     args = @('tasks/check_prompt_injection_invariants.py', '--check');                                  needs = @('python') }
    @{ name = 'test-prompt-injection';    exe = 'python';     args = @('tasks/test_check_prompt_injection_invariants.py');                                       needs = @('python') }
    @{ name = 'check-workflow-permissions'; exe = 'python';   args = @('tasks/check_github_workflow_permissions.py', '--check');                                  needs = @('python') }
    @{ name = 'test-workflow-permissions'; exe = 'python';    args = @('tasks/test_check_github_workflow_permissions.py');                                       needs = @('python') }
    @{ name = 'check-shell-pipe-safety';   exe = 'python';     args = @('tasks/check_shell_pipe_safety.py', '--check');                                             needs = @('python') }
    @{ name = 'test-shell-pipe-safety';    exe = 'python';     args = @('tasks/test_check_shell_pipe_safety.py');                                                  needs = @('python') }
    @{ name = 'check-import-shadowing';    exe = 'python';     args = @('tasks/check_import_shadowing.py', '--check');                                              needs = @('python') }
    @{ name = 'test-import-shadowing';     exe = 'python';     args = @('tasks/test_check_import_shadowing.py');                                                   needs = @('python') }
    # models (the guard only; nothing here talks to Ollama)
    @{ name = 'test-restart-ollama';      exe = 'pwsh';       args = @("$s/model-qwen3-8-27b/test-restart-ollama.ps1");                                    needs = @() }
    @{ name = 'test-score-claim-mapping'; exe = 'python';     args = @("$s/model-onboarding/scripts/test_score_claim_mapping.py");                         needs = @('python') }
    # ascii-art
    @{ name = 'test-asciicanvas';         exe = 'python';     args = @("$s/ascii-art/scripts/test-asciicanvas.py");                                        needs = @('python') }
    @{ name = 'test-check-ascii';         exe = 'python';     args = @("$s/ascii-art/scripts/test-check-ascii.py");                                        needs = @('python') }
    # lab-voice
    @{ name = 'test-check-voice';         exe = 'python';     args = @("$s/lab-voice/scripts/test-check-voice.py");                                        needs = @('python') }
    @{ name = 'check-voice-selftest';     exe = 'python';     args = @("$s/lab-voice/scripts/check-voice.py", '--self-test');                              needs = @('python') }
    # browser testing: the setup script's own test downloads nothing; everything that starts a browser is skipped
    @{ name = 'test-setup-browser';       exe = 'python';     args = @("$s/playwright-browser-testing/scripts/test-setup-browser-testing.py");             needs = @('python') }
    @{ name = 'observe-page-selftest';    exe = 'python';     args = @("$s/playwright-browser-testing/scripts/observe-page.py", '--self-test');            needs = @('python', 'browser') }
    @{ name = 'test-pr-screenshots';      exe = 'python';     args = @("$s/playwright-browser-testing/scripts/test-pr-screenshots.py");                    needs = @('python', 'git') }
    @{ name = 'pr-screenshots-selftest';  exe = 'python';     args = @("$s/playwright-browser-testing/scripts/pr-screenshots.py", '--self-test');          needs = @('python', 'browser') }
    @{ name = 'test-check-webgl';         exe = 'python';     args = @("$s/webgl-threejs-graphics/scripts/test-check-webgl.py");                           needs = @('python', 'browser') }
    @{ name = 'test-check-animated-page'; exe = 'python';     args = @("$s/webgl-threejs-graphics/scripts/test-check-animated-page.py");                   needs = @('python', 'browser') }
    @{ name = 'webgl-playwright';         exe = 'python';     args = @("$s/webgl-threejs-graphics/scripts/test-playwright.py");                            needs = @('python', 'browser') }
    @{ name = 'svg-examples';             exe = 'python';     args = @("$s/svg-animation/scripts/test-examples.py");                                       needs = @('python', 'browser') }
    @{ name = 'svg-playwright';           exe = 'python';     args = @("$s/svg-animation/scripts/test-playwright.py");                                     needs = @('python', 'browser') }
    # this runner
    @{ name = 'check-all-selftest';       exe = 'pwsh';       args = @('check-all.ps1', '-SelfTest');                                                      needs = @() }
)

$Reasons = [ordered]@{
    pwsh = 'needs PowerShell 7'; python = 'needs Python 3.10 or newer'; git = 'needs git'
    pyyaml = 'needs PyYAML (python -m pip install "PyYAML>=6.0")'; sh = 'needs a POSIX sh'
    windows = 'needs Windows'
    browser = 'needs a browser (not started by this runner)'; model = 'needs a model (not called by this runner)'
}

function Get-Python {
    foreach ($name in 'python', 'python3') {
        $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $cmd) { continue }
        try { $v = & $cmd.Source -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0 -and $v -and [version]"$v" -ge [version]'3.10') { return $cmd.Source }
    }
    return $null
}

$script:needCache = @{}
function Test-Need([string] $need) {
    if ($script:needCache.ContainsKey($need)) { return $script:needCache[$need] }
    $ok = switch ($need) {
        'pwsh'         { $true }
        'python'       { [bool](Get-Python) }
        'git'          { [bool](Get-Command git -CommandType Application -ErrorAction SilentlyContinue) }
        'pyyaml'       { $py = Get-Python; if ($py) { & $py -c 'import yaml' 2>$null; $LASTEXITCODE -eq 0 } else { $false } }
        'sh'           { [bool](Get-Command sh -CommandType Application -ErrorAction SilentlyContinue) }
        'windows'      { $IsWindows -eq $true }
        default        { $false }   # browser, model: never met by this runner
    }
    $script:needCache[$need] = [bool]$ok
    return [bool]$ok
}

function Get-Exe([string] $exe) {
    switch ($exe) {
        'pwsh'       { return (Get-Process -Id $PID).Path }
        'python'     { return (Get-Python) }
    }
    throw "unknown exe '$exe'"
}

function Get-ArgList($c) {
    if ($c.exe -eq 'pwsh') { return @('-NoProfile', '-File') + @($c.args) }
    return @($c.args)
}

function Format-Command($c) {
    $shown = switch ($c.exe) { 'pwsh' { 'pwsh' } default { 'python' } }
    $parts = @(Get-ArgList $c | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } })
    return ($shown + ' ' + ($parts -join ' ')).Trim()
}

function Assert-Table($table) {
    $known = @($Reasons.Keys)
    $names = @{}
    foreach ($c in $table) {
        if (-not $c.name -or $c.exe -notin 'pwsh', 'python') { throw "malformed check row: $($c | ConvertTo-Json -Compress)" }
        if ($names.ContainsKey($c.name)) { throw "duplicate check name '$($c.name)'" }
        $names[$c.name] = $true
        foreach ($n in @($c.needs)) { if ($n -notin $known) { throw "check '$($c.name)': unknown need '$n'" } }
    }
}

# Runs one command in its own process from the repo root, stdin closed, with a timeout. Returns code, output, timed-out flag.
function Invoke-One([string] $exePath, [string[]] $argList, [int] $timeout) {
    $psi = [System.Diagnostics.ProcessStartInfo]::new($exePath)
    foreach ($a in $argList) { $psi.ArgumentList.Add($a) }
    $psi.WorkingDirectory = $Root
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.RedirectStandardInput = $true
    $psi.StandardOutputEncoding = [Text.UTF8Encoding]::new($false); $psi.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $psi.Environment['PYTHONIOENCODING'] = 'utf-8'   # piped Python output would otherwise use the locale code page
    $p = [System.Diagnostics.Process]::Start($psi)
    $p.StandardInput.Close()
    $out = $p.StandardOutput.ReadToEndAsync(); $err = $p.StandardError.ReadToEndAsync()
    $timedOut = -not $p.WaitForExit($timeout * 1000)
    if ($timedOut) { try { $p.Kill($true) } catch { }; $null = $p.WaitForExit(10000) } else { $p.WaitForExit() }
    $text = ''
    try { $text = $out.GetAwaiter().GetResult() + $err.GetAwaiter().GetResult() } catch { }
    return @{ Code = $(if ($timedOut) { -1 } else { $p.ExitCode }); Out = $text; TimedOut = $timedOut }
}

function Invoke-Checks($table, [int] $timeout, [switch] $parallel, [int] $throttle = 4, [switch] $checkSkips, [string] $expectedSkipsFile) {
    $counts = [ordered]@{ PASS = 0; FAIL = 0; SKIPPED = 0 }
    $skippedItems = @()
    $width = ($table | ForEach-Object { $_.name.Length } | Measure-Object -Maximum).Maximum
    $started = Get-Date

    if ($parallel) {
        $prep = @($table | ForEach-Object {
            $c = $_
            $missing = @(@($c.needs) | Where-Object { -not (Test-Need $_) })
            [pscustomobject]@{
                Name    = $c.name
                ExePath = if ($missing.Count -eq 0) { Get-Exe $c.exe } else { '' }
                ArgList = if ($missing.Count -eq 0) { Get-ArgList $c } else { @() }
                Cmd     = Format-Command $c
                Missing = $missing
            }
        })

        $root = $script:Root
        $reasons = $script:Reasons
        $results = $prep | ForEach-Object -Parallel {
            $item = $_
            $root = $using:root
            $timeout = $using:timeout
            $reasons = $using:reasons

            if ($item.Missing.Count -gt 0) {
                $reasonText = ($item.Missing | ForEach-Object { $reasons[$_] }) -join '; '
                return [pscustomobject]@{
                    Name       = $item.Name
                    Cmd        = $item.Cmd
                    Skipped    = $true
                    SkipReason = $reasonText
                    Ok         = $false
                    TimedOut   = $false
                    Code       = 0
                    Secs       = 0
                    Tail       = @()
                }
            }

            $psi = [System.Diagnostics.ProcessStartInfo]::new($item.ExePath)
            foreach ($a in $item.ArgList) { $psi.ArgumentList.Add($a) }
            $psi.WorkingDirectory = $root
            $psi.UseShellExecute = $false
            $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true; $psi.RedirectStandardInput = $true
            $psi.StandardOutputEncoding = [System.Text.UTF8Encoding]::new($false); $psi.StandardErrorEncoding = [System.Text.UTF8Encoding]::new($false)
            $psi.Environment['PYTHONIOENCODING'] = 'utf-8'

            $t0 = [System.DateTime]::Now
            $p = [System.Diagnostics.Process]::Start($psi)
            $p.StandardInput.Close()
            $outAsync = $p.StandardOutput.ReadToEndAsync(); $errAsync = $p.StandardError.ReadToEndAsync()
            $timedOut = -not $p.WaitForExit($timeout * 1000)
            if ($timedOut) { try { $p.Kill($true) } catch { }; $null = $p.WaitForExit(10000) } else { $p.WaitForExit() }
            $text = ''
            try { $text = $outAsync.GetAwaiter().GetResult() + $errAsync.GetAwaiter().GetResult() } catch { }
            $secs = [System.Math]::Round(([System.DateTime]::Now - $t0).TotalSeconds, 1)
            $ok = (-not $timedOut) -and ($p.ExitCode -eq 0)

            $tail = if (-not $ok) {
                @(($text -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 15)
            } else { @() }

            return [pscustomobject]@{
                Name       = $item.Name
                Cmd        = $item.Cmd
                Skipped    = $false
                SkipReason = ''
                Ok         = $ok
                TimedOut   = $timedOut
                Code       = $p.ExitCode
                Secs       = $secs
                Tail       = $tail
            }
        } -ThrottleLimit $throttle

        foreach ($r in $results) {
            if ($r.Skipped) {
                $counts.SKIPPED++
                $skippedItems += [pscustomobject]@{ Name = $r.Name; Reason = $r.SkipReason }
                Write-Output ("SKIPPED {0}  {1}  ({2})" -f $r.Name.PadRight($width), $r.Cmd, $r.SkipReason)
            } else {
                $note = if ($r.TimedOut) { "timed out after $timeout s" } elseif (-not $r.Ok) { "exit $($r.Code)" } else { "$($r.Secs) s" }
                Write-Output ("{0} {1}  {2}  ({3})" -f $(if ($r.Ok) { 'PASS   ' } else { 'FAIL   ' }), $r.Name.PadRight($width), $r.Cmd, $note)
                if ($r.Ok) {
                    $counts.PASS++
                } else {
                    $counts.FAIL++
                    foreach ($l in $r.Tail) { Write-Output "          | $l" }
                }
            }
        }
    } else {
        foreach ($c in $table) {
            $cmd = Format-Command $c
            $missing = @(@($c.needs) | Where-Object { -not (Test-Need $_) })
            if ($missing) {
                $counts.SKIPPED++
                $reasonText = (($missing | ForEach-Object { $Reasons[$_] }) -join '; ')
                $skippedItems += [pscustomobject]@{ Name = $c.name; Reason = $reasonText }
                Write-Output ("SKIPPED {0}  {1}  ({2})" -f $c.name.PadRight($width), $cmd, $reasonText)
                continue
            }
            $t0 = Get-Date
            $r = Invoke-One (Get-Exe $c.exe) (Get-ArgList $c) $timeout
            $secs = [math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
            $ok = (-not $r.TimedOut) -and $r.Code -eq 0
            $note = if ($r.TimedOut) { "timed out after $timeout s" } elseif (-not $ok) { "exit $($r.Code)" } else { "$secs s" }
            Write-Output ("{0} {1}  {2}  ({3})" -f $(if ($ok) { 'PASS   ' } else { 'FAIL   ' }), $c.name.PadRight($width), $cmd, $note)
            if ($ok) { $counts.PASS++ } else {
                $counts.FAIL++
                $tail = @(($r.Out -split "`r?`n") | Where-Object { $_.Trim() } | Select-Object -Last 15)
                foreach ($l in $tail) { Write-Output "          | $l" }
            }
        }
    }
    $total = [math]::Round(((Get-Date) - $started).TotalSeconds)
    Write-Output ("{0} passed, {1} failed, {2} skipped ({3} checks, {4} s)" -f $counts.PASS, $counts.FAIL, $counts.SKIPPED, $table.Count, $total)

    if ($checkSkips -or $expectedSkipsFile) {
        $expectedPath = if ($expectedSkipsFile) { $expectedSkipsFile } else { Join-Path $script:Root 'tasks/expected-skips.json' }
        $mdLines = @(
            '### Test Skip Summary',
            '',
            "**Total Skipped Checks:** $($skippedItems.Count)",
            '',
            '| Check Name | Reason |',
            '| :--- | :--- |'
        )
        if ($skippedItems.Count -eq 0) {
            $mdLines += '| *(none)* | All checks ran without skipping |'
        } else {
            foreach ($s in ($skippedItems | Sort-Object { $_.Name })) {
                $escaped = if ($s.Reason) { $s.Reason.Replace('|', '\|') } else { '' }
                $mdLines += "| ``$($s.Name)`` | $escaped |"
            }
        }
        $mdLines += ''
        $summaryText = $mdLines -join "`n"
        Write-Output ''
        Write-Output $summaryText

        if ($env:GITHUB_STEP_SUMMARY) {
            try {
                [IO.File]::AppendAllText($env:GITHUB_STEP_SUMMARY, "`n" + $summaryText + "`n", [System.Text.Encoding]::UTF8)
            } catch { }
        }

        if (Test-Path -LiteralPath $expectedPath) {
            $expectedData = Get-Content -Raw -LiteralPath $expectedPath | ConvertFrom-Json
            $expectedNames = @($expectedData.expected_skips | ForEach-Object { $_.name })
            $actualNames = @($skippedItems | ForEach-Object { $_.Name })

            $unexpected = @($actualNames | Where-Object { $_ -notin $expectedNames })
            $stale = @($expectedNames | Where-Object { $_ -notin $actualNames })

            if ($unexpected.Count -gt 0) {
                $counts.FAIL++
                Write-Output "::error::Skipped checks list grew! Unexpected skipped check(s): $($unexpected -join ', ')"
                Write-Output ("FAIL   skip-guard (unexpected skips: {0})" -f ($unexpected -join ', '))
            }
            if ($stale.Count -gt 0) {
                $counts.FAIL++
                Write-Output "::error::Expected-skips list is stale! Check(s) no longer skip: $($stale -join ', ')"
                Write-Output ("FAIL   skip-guard (stale expected skips: {0})" -f ($stale -join ', '))
            }
            if ($unexpected.Count -eq 0 -and $stale.Count -eq 0) {
                Write-Output ("PASS   skip-guard ({0} skipped checks match committed baseline)" -f $actualNames.Count)
            }
        } else {
            $counts.FAIL++
            Write-Output "FAIL   skip-guard (expected skips file not found: $expectedPath)"
        }
    }
    $script:Counts = $counts
}

if ($SelfTest) {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('check-all-selftest-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $tmp | Out-Null
    $fail = @(); $n = 0
    function Check([string] $name, [bool] $ok, [string] $detail = '') {
        $script:n++
        Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" }))
        if (-not $ok) { $script:fail += $name }
    }
    try {
        $marker = Join-Path $tmp 'ran.txt'
        $stub = @(
            @{ name = 'stub-pass'; exe = 'pwsh'; args = @((Join-Path $tmp 'pass.ps1')); needs = @() }
            @{ name = 'stub-fail'; exe = 'pwsh'; args = @((Join-Path $tmp 'fail.ps1')); needs = @() }
            @{ name = 'stub-skip'; exe = 'pwsh'; args = @((Join-Path $tmp 'pass.ps1')); needs = @('browser') }
        )
        Set-Content (Join-Path $tmp 'pass.ps1') "Add-Content -LiteralPath '$marker' 'pass'; Write-Output 'stub ok'; exit 0" -Encoding utf8
        Set-Content (Join-Path $tmp 'fail.ps1') "Write-Output 'stub broke here'; exit 3" -Encoding utf8
        Set-Content (Join-Path $tmp 'slow.ps1') "Start-Sleep -Seconds 60; exit 0" -Encoding utf8
        $tableFile = Join-Path $tmp 'table.json'
        $stub | ConvertTo-Json -Depth 5 | Set-Content $tableFile -Encoding utf8
        function Run([string[]] $extra) {
            $o = & (Get-Process -Id $PID).Path -NoProfile -File $PSCommandPath -TableFile $tableFile @extra 2>&1 | Out-String
            return @{ Code = $LASTEXITCODE; Out = $o }
        }

        $r = Run @()
        Check 'a failing check makes the run exit 1' ($r.Code -eq 1) "exit=$($r.Code)"
        Check 'the count line says 1 passed, 1 failed, 1 skipped' ($r.Out -match '(?m)^1 passed, 1 failed, 1 skipped \(3 checks') $r.Out
        Check 'each check gets its own line with the command it ran' ($r.Out -match '(?m)^PASS\s+stub-pass .*pass\.ps1' -and $r.Out -match '(?m)^FAIL\s+stub-fail .*fail\.ps1 .*exit 3' -and $r.Out -match '(?m)^SKIPPED stub-skip') $r.Out
        Check 'a skip names its reason' ($r.Out -match 'stub-skip .*needs a browser') $r.Out
        Check 'a failure shows the tail of its output' ($r.Out -match '\| stub broke here') $r.Out
        Check 'the run continues after a failure and the skipped check is not run' (@(Get-Content $marker).Count -eq 1) "marker lines: $(@(Get-Content $marker -ErrorAction SilentlyContinue).Count)"

        Remove-Item $marker -ErrorAction SilentlyContinue
        $r = Run @('-Only', 'stub-pass,stub-skip')
        Check '-Only runs only the named checks; pass and skip exit 0' ($r.Code -eq 0 -and $r.Out -match '(?m)^1 passed, 0 failed, 1 skipped \(2 checks' -and $r.Out -notmatch 'stub-fail') "exit=$($r.Code) $($r.Out)"
        $r = Run @('-Only', 'no-such-check')
        Check '-Only with an unknown name is a usage error (exit 2)' ($r.Code -eq 2 -and $r.Out -match 'no-such-check') "exit=$($r.Code) $($r.Out)"

        Remove-Item $marker -ErrorAction SilentlyContinue
        $r = Run @('-List')
        $stub | ConvertTo-Json -Depth 5 | Set-Content $tableFile -Encoding utf8
        Remove-Item $marker -ErrorAction SilentlyContinue
        $r = Run @('-Parallel')
        Check '-Parallel runs and produces identical PASS/FAIL/SKIPPED results' ($r.Code -eq 1 -and $r.Out -match '(?m)^1 passed, 1 failed, 1 skipped \(3 checks' -and $r.Out -match '(?m)^PASS\s+stub-pass' -and $r.Out -match '(?m)^FAIL\s+stub-fail') "exit=$($r.Code) $($r.Out)"

        @(@{ name = 'stub-slow'; exe = 'pwsh'; args = @((Join-Path $tmp 'slow.ps1')); needs = @() }) | ConvertTo-Json -Depth 5 -AsArray | Set-Content $tableFile -Encoding utf8
        $t0 = Get-Date
        $r = Run @('-TimeoutSec', '3')
        $took = ((Get-Date) - $t0).TotalSeconds
        Check 'a check that runs past -TimeoutSec fails as timed out, and the run ends' ($r.Code -eq 1 -and $r.Out -match 'timed out after 3 s' -and $took -lt 45) "exit=$($r.Code) took=$took $($r.Out)"

        # Skip guard self-tests (T-0131)
        $stub | ConvertTo-Json -Depth 5 | Set-Content $tableFile -Encoding utf8
        $expectedSkipsJson = Join-Path $tmp 'expected-skips-test.json'
        @{
            schema_version = 1
            expected_skips = @(
                @{ name = 'stub-skip'; reason = 'needs a browser' }
            )
        } | ConvertTo-Json -Depth 5 | Set-Content $expectedSkipsJson -Encoding utf8

        # 1. Matching skips pass
        $r = Run @('-Only', 'stub-pass,stub-skip', '-CheckSkips', '-ExpectedSkipsFile', $expectedSkipsJson)
        Check 'skip guard passes when actual skips match expected' ($r.Code -eq 0 -and $r.Out -match 'PASS\s+skip-guard \(1 skipped checks match committed baseline\)') $r.Out

        # 2. Added skip fails guard (unexpected skip)
        $expectedEmptyJson = Join-Path $tmp 'expected-skips-empty.json'
        @{
            schema_version = 1
            expected_skips = @()
        } | ConvertTo-Json -Depth 5 | Set-Content $expectedEmptyJson -Encoding utf8
        $r = Run @('-Only', 'stub-pass,stub-skip', '-CheckSkips', '-ExpectedSkipsFile', $expectedEmptyJson)
        Check 'skip guard fails when an unexpected skip is added' ($r.Code -eq 1 -and $r.Out -match 'unexpected skips: stub-skip') $r.Out

        # 3. Removed skip fails guard (stale entry)
        $expectedStaleJson = Join-Path $tmp 'expected-skips-stale.json'
        @{
            schema_version = 1
            expected_skips = @(
                @{ name = 'stub-skip'; reason = 'needs a browser' },
                @{ name = 'stub-stale-skip'; reason = 'needs a browser' }
            )
        } | ConvertTo-Json -Depth 5 | Set-Content $expectedStaleJson -Encoding utf8
        $r = Run @('-Only', 'stub-pass,stub-skip', '-CheckSkips', '-ExpectedSkipsFile', $expectedStaleJson)
        Check 'skip guard fails when an expected skip is removed (stale entry)' ($r.Code -eq 1 -and $r.Out -match 'stale expected skips: stub-stale-skip') $r.Out

        # 4. GITHUB_STEP_SUMMARY gets the markdown table
        $stepSummaryFile = Join-Path $tmp 'step-summary.md'
        $oldStepSummary = $env:GITHUB_STEP_SUMMARY
        try {
            $env:GITHUB_STEP_SUMMARY = $stepSummaryFile
            $r = Run @('-Only', 'stub-pass,stub-skip', '-CheckSkips', '-ExpectedSkipsFile', $expectedSkipsJson)
            $summaryContent = if (Test-Path $stepSummaryFile) { Get-Content -Raw $stepSummaryFile } else { '' }
            Check 'skip guard writes markdown summary to GITHUB_STEP_SUMMARY' ($summaryContent -match '### Test Skip Summary' -and $summaryContent -match 'stub-skip') $summaryContent
        } finally {
            $env:GITHUB_STEP_SUMMARY = $oldStepSummary
        }
    } finally { Remove-Item -Recurse -Force -LiteralPath $tmp -ErrorAction SilentlyContinue }
    Write-Output "$($n - $fail.Count)/$n passed"
    exit ([int]($fail.Count -gt 0))
}

try {
    $table = if ($TableFile) {
        @(Get-Content -Raw -LiteralPath $TableFile | ConvertFrom-Json -AsHashtable)
    } else { $Checks }
    Assert-Table $table
    if ($Only) {
        $wanted = @($Only | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        $unknown = @($wanted | Where-Object { $_ -notin @($table | ForEach-Object { $_.name }) })
        if ($unknown) { throw "unknown check name(s): $($unknown -join ', '). Run with -List to see the names." }
        $table = @($table | Where-Object { $_.name -in $wanted })
    }
} catch {
    [Console]::Error.WriteLine("error: $($_.Exception.Message)")
    exit 2
}

if ($List) {
    $width = ($table | ForEach-Object { $_.name.Length } | Measure-Object -Maximum).Maximum
    foreach ($c in $table) {
        $needs = if (@($c.needs).Count) { @($c.needs) -join ',' } else { '-' }
        Write-Output ("{0}  {1}  {2}" -f $c.name.PadRight($width), $needs.PadRight(20), (Format-Command $c))
    }
    Write-Output "$($table.Count) checks; needs browser or model are always skipped by this runner"
    exit 0
}

Invoke-Checks $table $TimeoutSec -parallel:$Parallel -throttle $ThrottleLimit -checkSkips:$CheckSkips -expectedSkipsFile:$ExpectedSkipsFile
exit ([int]($script:Counts.FAIL -gt 0))
