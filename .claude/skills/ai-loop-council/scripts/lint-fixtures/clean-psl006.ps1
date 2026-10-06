# Twin of bad-psl006: -NoProfile is passed to pwsh through -ArgumentList.
Start-Process pwsh -ArgumentList '-NoProfile', '-File', 'x.ps1'
