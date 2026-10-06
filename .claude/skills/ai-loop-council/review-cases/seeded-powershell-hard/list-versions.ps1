param([Parameter(Mandatory)] [string] $Folder)

# Print the release folders from newest to oldest (names look like 1.9.0, 1.10.0, 2.0.1).
$releases = Get-ChildItem -LiteralPath $Folder -Directory | Select-Object -ExpandProperty Name
$releases | Sort-Object -Descending
