# Fixture for PSL004: a function mixes Write-Output with return <value>, so the caller gets an array.
function Test-Thing([string] $Name) {
    Write-Output "checking $Name"
    if ($Name) { return 0 }
    return 1
}
exit (Test-Thing 'a')
