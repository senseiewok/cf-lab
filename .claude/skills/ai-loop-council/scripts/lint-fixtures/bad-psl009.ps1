# Fixture for PSL009: /dev/null is not a PowerShell device; this writes a file named dev\null.
Get-Item nothing-here 2>/dev/null
