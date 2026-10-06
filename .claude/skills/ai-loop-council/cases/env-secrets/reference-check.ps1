$found = $false
$secretParts = 'PASSWORD', 'PASSWD', 'PASS', 'PWD', 'SECRET', 'TOKEN', 'KEY', 'APIKEY'
$placeholder = '^(|your[_-].*|<.*>|change[_-]?me|x{3,}|placeholder.*|example.*|replace[_-]?me|\$\{.*\})$'
foreach ($f in Get-ChildItem -Recurse -File | Where-Object { $_.Name -in '.env.example', '.env.sample', '.env.template' }) {
    foreach ($line in Get-Content -LiteralPath $f.FullName) {
        $l = $line.Trim()
        if ($l -eq '' -or $l.StartsWith('#')) { continue }
        if ($l -notmatch '^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') { continue }
        $key = $Matches[1]; $value = $Matches[2].Trim() -replace '^"(.*)"$', '$1' -replace "^'(.*)'$", '$1'
        $isSecret = @($key.ToUpper().Split('_') | Where-Object { $_ -in $secretParts }).Count -gt 0
        Write-Output "[$($f.Name)] [$key] secret=$isSecret [$value]"
        if ($isSecret -and $value -notmatch $placeholder) { $found = $true }
    }
}
if ($found) { exit 1 } else { exit 0 }
