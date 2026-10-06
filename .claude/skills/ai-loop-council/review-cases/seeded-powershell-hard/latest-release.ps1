param(
    [Parameter(Mandatory)] [string] $Folder,
    [Parameter(Mandatory)] [int] $Major
)

# Find the release folders for one major version (release-1.0, release-1.4, ...).
Get-ChildItem -LiteralPath $Folder -Directory |
    Where-Object { $_.Name -match "^release-$Major" } |
    Select-Object -ExpandProperty Name
