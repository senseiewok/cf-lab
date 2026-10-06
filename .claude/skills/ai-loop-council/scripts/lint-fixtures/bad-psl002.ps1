# Fixture for PSL002: a statement runs before param(), so param is parsed as a command.
$ErrorActionPreference = 'Stop'
param([string] $Name)
Write-Host $Name
