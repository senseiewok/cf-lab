Get-ChildItem -Force
Copy-Item -Recurse -Force src dist
ls -Force
$null = git fetch origin
