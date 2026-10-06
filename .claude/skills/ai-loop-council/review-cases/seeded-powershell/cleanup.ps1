param([string] $BuildDir = $env:BUILD_OUTPUT_DIR)

$ErrorActionPreference = 'Stop'
Write-Output "Cleaning $BuildDir"
Remove-Item -Recurse -Force "$BuildDir\*"
Write-Output 'Done'
