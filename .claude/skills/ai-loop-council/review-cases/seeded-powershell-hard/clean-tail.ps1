param(
    [Parameter(Mandatory)] [string] $Path,
    [ValidateRange(1, 10000)] [int] $Lines = 20
)

if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Not a file: $Path" }
Get-Content -LiteralPath $Path -Tail $Lines
