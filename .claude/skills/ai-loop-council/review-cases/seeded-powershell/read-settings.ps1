param([Parameter(Mandatory)] [string] $Path)

$settings = @{}
foreach ($line in Get-Content -LiteralPath $Path) {
    if ($line.Trim() -eq '' -or $line.StartsWith('#')) { continue }
    $parts = $line -split '='
    $settings[$parts[0].Trim()] = $parts[1].Trim()
}
$settings
