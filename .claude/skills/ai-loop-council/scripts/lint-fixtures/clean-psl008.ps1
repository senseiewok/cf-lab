# Twin of bad-psl008: a subexpression; a braced environment name with a dot is drive-qualified and fine.
$file = Get-Item .
Write-Host "name: $($file.Name)"
Write-Host "${env:a.b}"
