# Twin of bad-psl005: -ErrorAction on a cmdlet; the native call checks its exit code instead.
Get-ChildItem . -ErrorAction SilentlyContinue | Out-Null
git status
if ($LASTEXITCODE -ne 0) { Write-Host "git failed" }
