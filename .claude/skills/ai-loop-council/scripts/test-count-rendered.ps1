param([string] $Script = (Join-Path $PSScriptRoot 'count-rendered.ps1'))
# Independent verifier for count-rendered.ps1 (written by the orchestrator, not the model).
$ErrorActionPreference = 'Stop'
$rose = [char]::ConvertFromUtf32(0x1F339)
$tmp = Join-Path ([IO.Path]::GetTempPath()) ('count-verify-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $tmp | Out-Null
$fail = @(); $n = 0
function Case([string] $name, [int] $wantCode, [string[]] $argv, [string] $needle = '') {
    $script:n++
    $o = & pwsh -NoProfile -File $Script @argv 2>&1
    $code = $LASTEXITCODE; $text = ($o | Out-String)
    $ok = ($code -eq $wantCode) -and ((-not $needle) -or $text.Contains($needle))
    Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  (exit $code, wanted $wantCode; output: " + ($text -replace '\s+', ' ').Trim() + ')' }))
    if (-not $ok) { $script:fail += $name }
}
try {
    $row = (@($rose) * 13) -join ' '
    $f65 = Join-Path $tmp 'whole65.md'; [IO.File]::WriteAllText($f65, ((1..5 | ForEach-Object { $row }) -join "`n") + "`n", [Text.UTF8Encoding]::new($false))
    $fFence = Join-Path $tmp 'fence.md'
    $inside = (@($rose) * 37) -join ''; $outside = (@($rose) * 28) -join ''
    [IO.File]::WriteAllText($fFence, "# T`n`n" + '```text' + "`n$inside`n" + '```' + "`n`nafter $outside`n", [Text.UTF8Encoding]::new($false))
    $fOpen = Join-Path $tmp 'open.md'; [IO.File]::WriteAllText($fOpen, "x`n" + '```' + "`n$rose`n", [Text.UTF8Encoding]::new($false))
    $fOverlap = Join-Path $tmp 'overlap.md'; [IO.File]::WriteAllText($fOverlap, 'aaaa', [Text.UTF8Encoding]::new($false))
    $fCase = Join-Path $tmp 'case.md'; [IO.File]::WriteAllText($fCase, 'Rose rose ROSE rose', [Text.UTF8Encoding]::new($false))
    $fDigits = Join-Path $tmp 'digits.md'; [IO.File]::WriteAllText($fDigits, 'a1b22c333', [Text.UTF8Encoding]::new($false))
    $fEmpty = Join-Path $tmp 'empty-fence.md'; [IO.File]::WriteAllText($fEmpty, "x `n" + '```' + "`n" + '```' + "`n" + $rose + "`n", [Text.UTF8Encoding]::new($false))
    $before = (Get-FileHash $f65).Hash

    Case 'whole file 65 expected 65 -> 0' 0 @('-File', $f65, '-Pattern', $rose, '-Expected', '65') 'count=65'
    Case 'whole file 65 expected 37 -> 1' 1 @('-File', $f65, '-Pattern', $rose, '-Expected', '37') 'MISMATCH'
    Case 'first fence 37 expected 37 -> 0' 0 @('-File', $fFence, '-Pattern', $rose, '-Expected', '37', '-Region', 'FirstFence') 'count=37'
    Case 'first fence 37 expected 65 -> 1 (the README case)' 1 @('-File', $fFence, '-Pattern', $rose, '-Expected', '65', '-Region', 'FirstFence') 'MISMATCH'
    Case 'whole file of the fence fixture counts 65' 0 @('-File', $fFence, '-Pattern', $rose, '-Expected', '65') 'count=65'
    Case 'an empty fence block counts zero, not the fence lines' 0 @('-File', $fEmpty, '-Pattern', '`', '-Expected', '0', '-Region', 'FirstFence') 'count=0'
    Case 'an empty fence block ignores glyphs outside it' 0 @('-File', $fEmpty, '-Pattern', $rose, '-Expected', '0', '-Region', 'FirstFence') 'count=0'
    Case 'unclosed fence is a usage error' 2 @('-File', $fOpen, '-Pattern', $rose, '-Expected', '1', '-Region', 'FirstFence') 'error:'
    Case 'missing file is a usage error' 2 @('-File', (Join-Path $tmp 'nope.md'), '-Pattern', 'x', '-Expected', '0') 'error:'
    Case 'empty pattern is a usage error' 2 @('-File', $f65, '-Pattern', '', '-Expected', '0') 'error:'
    Case 'non-overlapping literal count (aa in aaaa = 2)' 0 @('-File', $fOverlap, '-Pattern', 'aa', '-Expected', '2') 'count=2'
    Case 'case-sensitive literal (rose appears 2 times)' 0 @('-File', $fCase, '-Pattern', 'rose', '-Expected', '2') 'count=2'
    Case 'regex digits runs = 3' 0 @('-File', $fDigits, '-Pattern', '\d+', '-Expected', '3', '-Regex') 'count=3'
    Case 'invalid regex is a usage error' 2 @('-File', $fDigits, '-Pattern', '(', '-Expected', '0', '-Regex') 'error:'
    $script:n++
    $same = ((Get-FileHash $f65).Hash -eq $before)
    Write-Output (('PASS ', 'FAIL ')[-not $same] + 'input file unchanged (read-only)'); if (-not $same) { $fail += 'read-only' }
} finally { Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
