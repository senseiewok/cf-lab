param([Parameter(Mandatory)] [string] $Folder)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Folder -PathType Container)) { throw "Not a folder: $Folder" }

Get-ChildItem -LiteralPath $Folder -File -Recurse |
    Group-Object -Property Extension |
    ForEach-Object {
        [pscustomobject]@{
            Extension = if ($_.Name) { $_.Name } else { '(none)' }
            Files     = $_.Count
            MB        = [math]::Round(($_.Group | Measure-Object -Property Length -Sum).Sum / 1MB, 2)
        }
    } |
    Sort-Object -Property MB -Descending
