$files = Get-ChildItem -Filter *.css
$foundViolations = $false
foreach ($file in $files) {
    $content = Get-Content -LiteralPath $file.FullName -Raw
    # Match @media blocks that contain prefers-reduced-motion: reduce
    # We need to find the full @media rule including nested braces
    # Use regex to extract media blocks with prefers-reduced-motion: reduce
    $mediaPattern = '(?s)@media[^{]*\{(?<block>[^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
    
    # Extract all media blocks first
    $mediaMatches = [regex]::Matches($content, $mediaPattern)
    
    foreach ($mediaMatch in $mediaMatches) {
        $mediaBlock = $mediaMatch.Groups['block'].Value
        # Check if this media block's condition contains prefers-reduced-motion: reduce
        $mediaCondition = $mediaMatch.Value
        if ($mediaCondition -match 'prefers-reduced-motion\s*:\s*reduce') {
            Write-Output "[Testing media block condition in file $($file.Name): $mediaCondition]"
            
            # Now parse declarations inside this media block
            # Extract all declaration blocks (selector { declarations })
            $rulePattern = '(?s)[^{]+\{(?<declarations>[^{}]*(?:\{[^{}]*\}[^{}]*)*)\}'
            $ruleMatches = [regex]::Matches($mediaBlock, $rulePattern)
            
            foreach ($ruleMatch in $ruleMatches) {
                $declarations = $ruleMatch.Groups['declarations'].Value
                
                # Split declarations by semicolon and process each
                $declarationList = $declarations -split ';' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
                
                foreach ($declaration in $declarationList) {
                    # Skip @-rules inside (like @keyframes) by checking for colon
                    if ($declaration -notmatch ':') { continue }
                    
                    # Split into property and value
                    $parts = $declaration -split ':', 2
                    $property = $parts[0].Trim()
                    $value = if ($parts.Count -gt 1) { $parts[1].Trim() } else { '' }
                    
                    # Strip !important for comparison
                    $value = $value -replace '\s*!important\s*$', ''
                    
                    # Normalize property name (case-insensitive, handle vendor prefixes)
                    $propLower = $property.ToLower()
                    
                    # Check if this is an animation/transition property
                    if ($propLower -match '^(animation|animation-name|transition|transition-property)$') {
                        Write-Output "[Found $property: $value in media prefers-reduced-motion: reduce block]"
                        
                        # Check if value is not 'none'
                        if ($value -notmatch '^none$') {
                            Write-Output "[VIOLATION: $property: $value should be 'none' in reduce-motion context]"
                            $foundViolations = $true
                        }
                    }
                }
            }
        }
    }
}

if ($foundViolations) {
    Write-Output "[Violations found, exiting with code 1]"
    exit 1
} else {
    Write-Output "[No violations found, exiting with code 0]"
    exit 0
}
