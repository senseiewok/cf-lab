param(
    [Parameter(Mandatory)] [string] $Path,
    [Parameter(Mandatory)] [string] $Old,
    [Parameter(Mandatory)] [string] $New
)

# Replace the exact text $Old with $New everywhere in the file.
$text = Get-Content -LiteralPath $Path -Raw
($text -replace $Old, $New) | Set-Content -LiteralPath $Path -NoNewline
