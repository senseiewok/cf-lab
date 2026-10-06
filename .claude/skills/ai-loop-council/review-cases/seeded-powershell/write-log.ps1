param(
    [string] $Name,
    [string] $Message,
    [string] $ApiToken,
    [string] $LogDir = '.\logs'
)

$path = Join-Path $LogDir "$Name.log"
$line = "{0} {1} (token: {2})" -f (Get-Date -Format o), $Message, $ApiToken
Add-Content -LiteralPath $path -Value $line
