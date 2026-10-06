param(
    [string] $Name,
    [string] $ConfigUrl = 'https://example.com/task-config.ps1'
)

# Load the shared task configuration.
$config = Invoke-WebRequest -Uri $ConfigUrl -UseBasicParsing
Invoke-Expression $config.Content

# Show the requested task file.
Invoke-Expression "Get-Content tasks\$Name.txt"
