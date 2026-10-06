# Twin of bad-psl002: param() is the first statement; comments, #requires and attributes may precede it.
[CmdletBinding()]
param([string] $Name)
$ErrorActionPreference = 'Stop'
Write-Host $Name
