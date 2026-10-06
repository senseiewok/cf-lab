$files = Get-ChildItem -Recurse -File -Include '.env.example', '.env.sample', '.env.template' -ErrorAction SilentlyContinue
if (-not $files) { exit 0 }

$foundNonPlaceholder = $false
foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw
    $lines = $content -split '\r?\n'
    foreach ($line in $lines) {
        # Skip blank or comment lines
        if ($line.Trim() -eq '' -or $line.Trim().StartsWith('#')) { continue }

        # Strip 'export ' prefix if present
        $line = $line -replace '^\s*export\s+', ''

        # Match KEY=VALUE (allow spaces around =)
        if ($line -notmatch '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)') { continue }
        $key = $matches[1]
        $rawValue = $matches[2]

        # Determine if key is secret
        $parts = $key -split '_'
        $isSecret = $false
        foreach ($part in $parts) {
            if ($part -match '^(PASSWORD|PASSWD|PASS|PWD|SECRET|TOKEN|KEY|APIKEY)$' -and $part -ne '') {
                $isSecret = $true
                break
            }
        }
        if (-not $isSecret) { continue }

        # Normalize value: strip surrounding quotes (single or double), trim whitespace
        $value = $rawValue.Trim()
        if ($value -match '^"(.*)"$') { $value = $matches[1] }
        elseif ($value -match "^'(.*)'$") { $value = $matches[1] }
        $value = $value.Trim()

        # Write diagnostic
        Write-Output "[Testing secret key '$key' with normalized value: $value]"

        # Placeholder checks (case-insensitive)
        $isPlaceholder = $false
        if ($value -eq '') { $isPlaceholder = $true }
        elseif ($value -match '^(.*)$' -and $value.ToLower() -match '^your[-_].*') { $isPlaceholder = $true }
        elseif ($value -match '^<.*>$') { $isPlaceholder = $true }
        elseif ($value -match '^(changeme|change_me)$' -or $value -match '^changeme' -or $value -match '^change_me') { $isPlaceholder = $true }
        elseif ($value -match '^x{3,}$') { $isPlaceholder = $true }
        elseif ($value -match '^(placeholder|example)') { $isPlaceholder = $true }
        elseif ($value -match '^replace[-_]?me$') { $isPlaceholder = $true }
        elseif ($value -match '^\$\{.*\}$') { $isPlaceholder = $true }

        if (-not $isPlaceholder) {
            Write-Output "[NON-PLACEHOLDER SECRET FOUND: $key = $value]"
            $foundNonPlaceholder = $true
            break  # stop checking further lines in this file once one violation found
        }
    }
}

if ($foundNonPlaceholder) { exit 1 } else { exit 0 }
