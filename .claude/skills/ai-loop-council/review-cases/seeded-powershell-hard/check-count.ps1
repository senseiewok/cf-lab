param([string] $Count)   # number of workers, passed on the command line

if ($Count -gt 9) {
    Write-Output 'Too many workers; the limit is 9.'
    exit 1
}
"Starting $Count workers"
