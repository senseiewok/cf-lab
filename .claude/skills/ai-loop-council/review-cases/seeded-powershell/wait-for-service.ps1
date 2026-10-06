param([Parameter(Mandatory)] [string] $Url)

while ($true) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing
        if ($response.StatusCode -eq 200) { break }
    }
    catch { }
    Start-Sleep -Seconds 1
}
'Service is up'
