param(
    [Parameter(Mandatory)] [string] $Name,
    [Parameter(Mandatory)] [string] $Backup
)

# Copy one config file (names like app[1].config are common) into the backup folder.
if (Test-Path -Path $Name) {
    Copy-Item -Path $Name -Destination $Backup
    "Copied $Name"
}
else {
    Write-Warning "Not found: $Name"
}
