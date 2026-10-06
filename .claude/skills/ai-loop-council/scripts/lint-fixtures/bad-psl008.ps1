# Fixture for PSL008: ${file.Name} is a variable literally named "file.Name", which is empty.
$file = Get-Item .
Write-Host "name: ${file.Name}"
