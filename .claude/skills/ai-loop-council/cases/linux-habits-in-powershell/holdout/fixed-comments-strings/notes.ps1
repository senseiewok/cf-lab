# Don't use ls -la or touch here; they fail in PowerShell.
Write-Host 'Linux users: sudo apt install jq'
Write-Output "On Linux you would run: grep ERROR app.log > /dev/null"
