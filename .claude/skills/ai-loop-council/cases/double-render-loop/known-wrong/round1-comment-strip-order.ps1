$files = Get-ChildItem -Path . -Recurse -Include *.js,*.mjs -File

$foundIssue = $false

foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw
    
    # Remove comments: first single-line (// ...), then multi-line (/* ... */)
    # Use non-greedy dot-all for multi-line comments
    $clean = $content -replace '//[^\r\n]*', ''
    $clean = $clean -replace '/\*[\s\S]*?\*/', ''
    
    Write-Output "[File: $( $file.FullName )]"
    Write-Output "[Cleaned content for analysis:]"
    Write-Output "[$clean]"

    # Extract setAnimationLoop argument names (only identifiers, not 'null')
    $setPattern = 'setAnimationLoop\s*\(\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\)'
    $setNames = [regex]::Matches($clean, $setPattern, 'Singleline') | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -ne 'null' -and $_ -ne '' }
    
    Write-Output "[setAnimationLoop names:]"
    Write-Output "[$($setNames -join ', ')]"

    # Extract requestAnimationFrame argument names (bare or window/globalThis/self.)
    $rafPattern = '(?:(?:window|globalThis|self)\s*\.\s*)?requestAnimationFrame\s*\(\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\)'
    $rafNames = [regex]::Matches($clean, $rafPattern, 'Singleline') | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -ne 'null' -and $_ -ne '' }
    
    Write-Output "[requestAnimationFrame names:]"
    Write-Output "[$($rafNames -join ', ')]"

    # Case-sensitive intersection
    $commonNames = $setNames | Where-Object { $rafNames -ccontains $_ }
    Write-Output "[Common names (case-sensitive):]"
    Write-Output "[$($commonNames -join ', ')]"

    if ($commonNames.Count -gt 0) {
        Write-Output "[Issue detected in file: $( $file.FullName )]"
        $foundIssue = $true
        break
    }
}

if ($foundIssue) {
    Write-Output "[Problem detected: exiting 1]"
    exit 1
} else {
    Write-Output "[No problem detected: exiting 0]"
    exit 0
}
