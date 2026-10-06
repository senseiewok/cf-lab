<#
.SYNOPSIS
  Regression tests for the safety guard in distill-check.ps1. Run after any change to the
  guard or its allowlists. The hostile samples are only parsed, never executed.
#>
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot 'distill-check.ps1'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseInput((Get-Content -Raw $path), [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw "distill-check.ps1 does not parse: $($errors[0].Message)" }

# Load only the allowlists and guard functions, without running the loop.
$defs = ($ast.EndBlock.Statements | Where-Object {
        $_.Extent.Text -match '^\$allowed' -or
        ($_ -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $_.Name -in 'Test-CheckSafety', 'Repair-KnownTraps', 'Get-ModelHints')
    } | ForEach-Object { $_.Extent.Text }) -join "`n"
. ([scriptblock]::Create($defs))

$cases = @(
    # expect = 'allow' or 'reject'
    @{ name = 'regex check';               expect = 'allow';  code = '$c = Get-Content -Raw site.css; if ([regex]::IsMatch($c, "(?s)x")) { exit 1 }; exit 0' }
    @{ name = 'own helper function';       expect = 'allow';  code = 'function Strip-Comments($s) { $s -replace "/[*].*", "" }; Strip-Comments (Get-Content -Raw a.js)' }
    @{ name = 'hashtable helpers';         expect = 'allow';  code = '$h = @{}; if (-not $h.ContainsKey("a")) { $h.Add("a", 1) }' }
    @{ name = 'language parser';           expect = 'allow';  code = '$t = $null; $e = $null; $a = [System.Management.Automation.Language.Parser]::ParseInput("ls", [ref]$t, [ref]$e); $a.FindAll({ $true }, $true)' }
    @{ name = 'read $Matches';             expect = 'allow';  code = 'if ("ab" -match "a") { Write-Output $Matches[0] }' }
    @{ name = 'HashSet ::new()';           expect = 'allow';  code = '$s = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal); $s.Add("a")' }
    @{ name = 'New-Object (any type)';     expect = 'reject'; code = '$w = New-Object System.Net.WebClient' }
    @{ name = 'WebClient ::new()';         expect = 'reject'; code = '$w = [System.Net.WebClient]::new()' }
    @{ name = 'helper hiding a delete';    expect = 'reject'; code = 'function Clean-Up { Remove-Item placeholder-folder }; Clean-Up' }
    @{ name = 'delete cmdlet';             expect = 'reject'; code = 'Remove-Item placeholder-folder' }
    @{ name = 'FileInfo.Delete()';         expect = 'reject'; code = '(Get-ChildItem site.css).Delete()' }
    @{ name = 'FileInfo.MoveTo()';         expect = 'reject'; code = 'Get-ChildItem | ForEach-Object { $_.MoveTo("elsewhere") }' }
    @{ name = 'ForEach-Object Delete';     expect = 'reject'; code = 'Get-ChildItem -Recurse -File | ForEach-Object Delete' }
    @{ name = 'ForEach-Object -MemberName'; expect = 'reject'; code = 'Get-ChildItem | ForEach-Object -MemberName MoveTo -ArgumentList "elsewhere"' }
    @{ name = 'ForEach-Object quoted name'; expect = 'reject'; code = 'Get-ChildItem | ForEach-Object ("De" + "lete")' }
    @{ name = 'ForEach-Object -Process';   expect = 'allow';  code = 'Get-ChildItem | ForEach-Object -Begin { $n = 0 } -Process { $n++ } -End { $n }' }
    @{ name = 'set file property';         expect = 'reject'; code = '(Get-ChildItem site.css).IsReadOnly = $true' }
    @{ name = 'set property via variable'; expect = 'reject'; code = 'foreach ($f in Get-ChildItem) { $f.LastWriteTime = [datetime]::MinValue }' }
    @{ name = 'hashtable index assign';    expect = 'allow';  code = '$h = @{}; $h["a"] = 1; $h["a"] += 1' }
    @{ name = 'static file write';     expect = 'reject'; code = '[IO.File]::WriteAllText("x", "y")' }
    @{ name = 'Invoke-Expression';         expect = 'reject'; code = 'Invoke-Expression "Get-Date"' }
    @{ name = 'dynamic command name';      expect = 'reject'; code = '$x = "Get-Date"; & $x' }
    @{ name = 'redirect to file';          expect = 'reject'; code = '"data" > out.txt' }
    @{ name = 'web request';               expect = 'reject'; code = 'Invoke-WebRequest https://example.com' }
    @{ name = 'scriptblock .Invoke()';     expect = 'reject'; code = '{ Write-Output 1 }.Invoke()' }
    @{ name = 'lint: dotted braced var';   expect = 'reject'; code = 'Write-Output "${file.Name}"' }
    @{ name = 'lint: assign $matches';     expect = 'reject'; code = '$matches = 1' }
    @{ name = 'lint: $(.Name)';            expect = 'reject'; code = 'foreach ($file in Get-ChildItem) { $raw = Get-Content -Path $(.Name) -Raw }' }
    @{ name = '$($file.Name) is fine';     expect = 'allow';  code = 'foreach ($file in Get-ChildItem) { $raw = Get-Content -Path $($file.Name) -Raw }' }
)

$failures = 0
foreach ($c in $cases) {
    $reason = Test-CheckSafety $c.code
    $got = if ($reason) { 'reject' } else { 'allow' }
    $ok = $got -eq $c.expect
    if (-not $ok) { $failures++ }
    "{0,-5} {1,-26} expected {2,-6} got {3,-6} {4}" -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $c.name, $c.expect, $got,
        $(if ($reason) { $reason.Substring(0, [math]::Min(50, $reason.Length)) })
}

# The automatic repair must fix "$name:" and leave scope prefixes like $env: alone.
$repaired = Repair-KnownTraps 'Write-Output "[$prop: $value]"; $p = $env:PATH'
$repairOk = $repaired -eq 'Write-Output "[$($prop): $value]"; $p = $env:PATH'
if (-not $repairOk) { $failures++ }
"{0,-5} {1,-26} {2}" -f $(if ($repairOk) { 'PASS' } else { 'FAIL' }), 'repair "$name:"', $repaired

# hints_file must stay inside the skills folder: a profile can't pull an arbitrary file into a prompt.
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('hints-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$skills = Join-Path $tmp 'skills'; New-Item -ItemType Directory -Path (Join-Path $skills 'model'), (Join-Path $skills 'shared') | Out-Null
Set-Content (Join-Path $skills 'shared\ok.md') 'use single quotes'
Set-Content (Join-Path $tmp 'secret.md') 'outside the skills folder'
Set-Content (Join-Path $skills 'shared\notes.txt') 'not markdown'
$hintCases = @(
    @{ name = 'hints: no field';           json = '{"model":"m"}';                                          want = 'empty' }
    @{ name = 'hints: shared file';        json = '{"hints_file":"../shared/ok.md"}';                       want = 'loaded' }
    @{ name = 'hints: traversal out';      json = '{"hints_file":"../../secret.md"}';                       want = 'throw' }
    @{ name = 'hints: absolute outside';   json = ('{"hints_file":' + ((Join-Path $tmp 'secret.md') | ConvertTo-Json) + '}'); want = 'throw' }
    @{ name = 'hints: not markdown';       json = '{"hints_file":"../shared/notes.txt"}';                   want = 'throw' }
    @{ name = 'hints: missing file';       json = '{"hints_file":"../shared/nope.md"}';                     want = 'throw' }
)
foreach ($h in $hintCases) {
    $pf = Join-Path $skills 'model\profile.json'; Set-Content $pf $h.json
    $got = try { $r = Get-ModelHints $pf $skills; if ($r) { 'loaded' } else { 'empty' } } catch { 'throw' }
    $ok = $got -eq $h.want; if (-not $ok) { $failures++ }
    "{0,-5} {1,-26} expected {2,-6} got {3}" -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $h.name, $h.want, $got
}
Remove-Item $tmp -Recurse -Force

if ($failures) { "$failures guard test(s) failed"; exit 1 } else { 'All guard tests passed'; exit 0 }
