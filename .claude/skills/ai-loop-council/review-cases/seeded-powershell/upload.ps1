param(
    [Parameter(Mandatory)] [string] $FtpHost,
    [Parameter(Mandatory)] [string] $User,
    [Parameter(Mandatory)] [string] $Password,
    [Parameter(Mandatory)] [string] $LocalFile
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $LocalFile -PathType Leaf)) { throw "No such file: $LocalFile" }

$name = Split-Path -Leaf $LocalFile
# Upload over FTPS.
curl.exe --ssl-reqd `
    --insecure `
    -u "${User}:${Password}" `
    -T $LocalFile "ftp://$FtpHost/$name"
if ($LASTEXITCODE -ne 0) { throw "Upload failed (curl exit $LASTEXITCODE)" }
"Uploaded $name"
