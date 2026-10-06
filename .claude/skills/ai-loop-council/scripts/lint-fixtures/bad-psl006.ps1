# Fixture for PSL006: -NoProfile belongs to pwsh, not to Start-Process.
Start-Process pwsh -NoProfile -ArgumentList '-File', 'x.ps1'
