<#
.SYNOPSIS
Counts occurrences of a literal string or regex in a file and asserts the count.

.DESCRIPTION
Reads a UTF-8 text file and counts non-overlapping occurrences of -Pattern.
Supports whole-file counting or only inside the first fenced code block.
Exits 0 on match, 1 on mismatch, 2 on usage errors.

.EXAMPLE
pwsh -NoProfile -File count-rendered.ps1 -File README.md -Pattern "rose" -Expected 65
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$File,
    [Parameter(Mandatory=$true)][AllowEmptyString()][string]$Pattern,
    [Parameter(Mandatory=$true)][int]$Expected,
    [ValidateSet('Whole','FirstFence')][string]$Region = 'Whole',
    [switch]$Regex
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Fail([string]$msg) { Write-Host "error: $msg"; exit 2 }

try {
    if ([string]::IsNullOrEmpty($Pattern)) { Fail("empty pattern") }
    if (-not (Test-Path -LiteralPath $File)) { Fail("file missing") }

    $text = [IO.File]::ReadAllText($File, [Text.Encoding]::UTF8)

    if ($Region -eq 'FirstFence') {
        $lines = $text -split "`n"
        $start = -1; $end = -1
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i].TrimStart().StartsWith('```')) {
                if ($start -eq -1) { $start = $i } else { $end = $i; break }
            }
        }
        if ($start -eq -1 -or $end -eq -1) { Fail("FirstFence with no closed fence") }
        # An empty block (adjacent fences) has no lines; a reversed range would return the fence lines.
        $text = if ($end -eq $start + 1) { '' } else { ($lines[($start+1)..($end-1)]) -join "`n" }
    }

    if ($Regex) {
        try {
            $rx = [regex]::new($Pattern)
        } catch { Fail("invalid regex") }
        $count = @($rx.Matches($text)).Count
    } else {
        $count = 0
        $idx = $text.IndexOf($Pattern, 0, [StringComparison]::Ordinal)
        while ($idx -ge 0) {
            $count++
            $idx = $text.IndexOf($Pattern, $idx + $Pattern.Length, [StringComparison]::Ordinal)
        }
    }

    Write-Host "count=$count expected=$Expected region=$Region file=$File"
    if ($count -eq $Expected) { Write-Host "OK"; exit 0 } else { Write-Host "MISMATCH"; exit 1 }
} catch {
    Fail($_.Exception.Message)
}
