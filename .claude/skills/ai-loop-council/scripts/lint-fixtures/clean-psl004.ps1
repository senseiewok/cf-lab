# Twin of bad-psl004: Write-Host for messages; a bare return; a return inside a nested script block.
function Test-Thing([string] $Name) {
    Write-Host "checking $Name"
    if ($Name) { return 0 }
    return 1
}
function Show-Names {
    Write-Output "names"
    $x = Get-ChildItem . | ForEach-Object { return $_.Name }
    return
}
exit (Test-Thing 'a')
