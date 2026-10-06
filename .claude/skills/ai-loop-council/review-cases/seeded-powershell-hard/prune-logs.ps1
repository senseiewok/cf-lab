param([Parameter(Mandatory)] [string] $LogDir)

# Delete logs that are older than 30 days AND bigger than 1 MB.
$cutoff = (Get-Date).AddDays(-30)
Get-ChildItem -LiteralPath $LogDir -Filter *.log |
    Where-Object { $_.LastWriteTime -lt $cutoff -or $_.Length -gt 1MB } |
    Remove-Item
