# Fixture for PSL011: Invoke-Expression and its alias run a string as code.
$cmd = 'Get-Date'
Invoke-Expression $cmd
iex $cmd
