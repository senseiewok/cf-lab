param([Parameter(Mandatory)] [string] $Folder)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Folder -PathType Container)) { throw "Not a folder: $Folder" }

Get-ChildItem -LiteralPath $Folder -File -Recurse |
    Get-FileHash -Algorithm SHA256 |
    Group-Object -Property Hash |
    Where-Object { $_.Count -gt 1 } |
    ForEach-Object { [pscustomobject]@{ Hash = $_.Name; Files = $_.Group.Path } }
