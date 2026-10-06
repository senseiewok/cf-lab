Get-ChildItem -Force
if (-not (Test-Path index.html)) { New-Item -ItemType File index.html }
