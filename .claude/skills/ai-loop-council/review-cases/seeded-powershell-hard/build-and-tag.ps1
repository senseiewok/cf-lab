$ErrorActionPreference = 'Stop'

dotnet build --configuration Release
git tag "build-$(Get-Date -Format yyyyMMdd)"
'Build finished and tagged'
