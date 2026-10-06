$files = Get-ChildItem -Recurse -File -Include '.env.example', '.env.sample', '.env.template' -Force
if (-not $files) { Write-Output '[No matching template files found. Exit 0.]'; exit 0 }
$foundProblem = $false
foreach ($file in $files) {
  Write-Output "[Scanning file: $($file.FullName)]"
  $content = Get-Content -Path $file.FullName -Raw
  $lines = $content -split '\r?\n'
  foreach ($line in $lines) {
    $trimmedLine = $line.Trim()
    if ([string]::IsNullOrEmpty($trimmedLine)) { continue }
    if ($trimmedLine.StartsWith('#')) { continue }
    $lineForParsing = $trimmedLine
    if ($lineForParsing.StartsWith('export ', [System.StringComparison]::OrdinalIgnoreCase)) {
      $lineForParsing = $lineForParsing.Substring(7).TrimStart()
    }
    # Match KEY = VALUE (allow spaces around =)
    if (-not ($lineForParsing -match '^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$')) { continue }
    $key = $matches[1]
    $rawValue = $matches[2].Trim()
    # Remove surrounding quotes (single or double) if present
    $value = $rawValue
    if ($value.Length -ge 2) {
      if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
        $value = $value.Substring(1, $value.Length - 2)
      }
    }
    # Determine if key is secret
    $parts = $key -split '_'
    $isSecret = $false
    foreach ($part in $parts) {
      $p = $part.ToUpper()
      if ($p -eq 'PASSWORD' -or $p -eq 'PASSWD' -or $p -eq 'PASS' -or $p -eq 'PWD' -or $p -eq 'SECRET' -or $p -eq 'TOKEN' -or $p -eq 'KEY' -or $p -eq 'APIKEY') {
        $isSecret = $true
        break
      }
    }
    if (-not $isSecret) { continue }
    # Diagnostics: show raw and processed value
    Write-Output "[Secret key '$key' detected with value: [$value]]"
    # Placeholder validation (case-insensitive)
    $v = $value.ToUpper()
    $isPlaceholder = $false
    if ($value -eq '') { $isPlaceholder = $true; Write-Output '[Value is empty -> placeholder]' }
    elseif (-not $isPlaceholder) {
      if (($value -match '^"?your[_-]' -or $value -match "^'your[_-]") -or ($value -match '^"?your[_-]' -or $value -match "^'your[_-]") ) {
        # Normalize first: remove surrounding quotes to check pattern
        $valueNoQuotes = $value
        if ($valueNoQuotes.Length -ge 2) {
          if (($valueNoQuotes.StartsWith('"') -and $valueNoQuotes.EndsWith('"')) -or ($valueNoQuotes.StartsWith("'") -and $valueNoQuotes.EndsWith("'"))) {
            $valueNoQuotes = $valueNoQuotes.Substring(1, $valueNoQuotes.Length - 2)
          }
        }
        if ($valueNoQuotes -match '^your[_-]') {
          $isPlaceholder = $true
          Write-Output "[Value starts with 'your_' or 'your-' -> placeholder]"
        }
      }
      elseif ($value -match '^<[^>]+>$') {
        $isPlaceholder = $true
        Write-Output '[Value is <...> -> placeholder]'
      }
      elseif ($v -eq 'CHANGE_ME' -or $v -eq 'CHANGEME') {
        $isPlaceholder = $true
        Write-Output '[Value is changeme/change_me -> placeholder]'
      }
      elseif ($value -match 'x{3,}') {
        $isPlaceholder = $true
        Write-Output '[Value contains 3+ consecutive x -> placeholder]'
      }
      elseif ($v -match '^PLACEHOLDER') {
        $isPlaceholder = $true
        Write-Output '[Value starts with placeholder -> placeholder]'
      }
      elseif ($v -match '^EXAMPLE') {
        $isPlaceholder = $true
        Write-Output '[Value starts with example -> placeholder]'
      }
      elseif ($v -match '^REPLACE_ME$' -or $v -match '^REPLACE-ME$') {
        $isPlaceholder = $true
        Write-Output '[Value is replace_me/replace-me -> placeholder]'
      }
      elseif ($value -match '\$\{[^}]+\}') {
        $isPlaceholder = $true
        Write-Output '[Value contains ${...} reference -> placeholder]'
      }
    }
    if (-not $isPlaceholder) {
      Write-Output "[*** NON-PLACEHOLDER SECRET VALUE FOUND: $key=$value ***]"
      $foundProblem = $true
    }
  }
}
if ($foundProblem) {
  Write-Output '[Problem detected. Exit 1.]'
  exit 1
} else {
  Write-Output '[No problems found. Exit 0.]'
  exit 0
}
