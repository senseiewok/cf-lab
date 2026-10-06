$files = Get-ChildItem -Filter '*.css' -File
if (-not $files) { exit 0 }

foreach ($file in $files) {
    $content = Get-Content -LiteralPath $file.FullName -Raw
    $normalized = $content -replace '\s+', ' '
    
    # Match all @media blocks, handling combined media queries like "screen and (...)" and short form without value
    $mediaPattern = '(?s)@media\s+([^{{}}]+(?:\{[^{{}}]*\}(?:(?!@media)[^{{}}])*)*)'
    
    # Better approach: find @media ... { ... } using balanced braces
    $i = 0
    while ($i -lt $normalized.Length) {
        $mediaPos = $normalized.IndexOf('@media', $i, [StringComparison]::Ordinal)
        if ($mediaPos -lt 0) { break }
        
        # Find opening brace after @media
        $openBracePos = $normalized.IndexOf('{', $mediaPos)
        if ($openBracePos -lt 0) { break }
        
        # Extract condition (between @media and opening brace)
        $mediaCondition = $normalized.Substring($mediaPos + '@media'.Length, $openBracePos - $mediaPos - '@media'.Length).Trim()
        
        # Count braces to find matching closing brace
        $braceCount = 1
        $j = $openBracePos + 1
        while ($j -lt $normalized.Length -and $braceCount -gt 0) {
            if ($normalized[$j] -eq '{') { $braceCount++ }
            elseif ($normalized[$j] -eq '}') { $braceCount-- }
            $j++
        }
        
        if ($braceCount -ne 0) { break }  # Malformed, skip
        
        $mediaBody = $normalized.Substring($openBracePos + 1, $j - $openBracePos - 2)
        $i = $j  # Continue search after this block
        
        Write-Output "Testing media condition: [$mediaCondition]"
        
        # Check for reduce-motion: explicit (prefers-reduced-motion: reduce) or short form (prefers-reduced-motion without value)
        # Short form: the word 'prefers-reduced-motion' followed immediately by ')' or whitespace then ')'
        $hasReduceExplicit = $mediaCondition -match 'prefers-reduced-motion\s*:\s*reduce'
        $hasReduceShort = $mediaCondition -match 'prefers-reduced-motion\s*\)'
        $isReduceBlock = $hasReduceExplicit -or $hasReduceShort
        
        if ($isReduceBlock) {
            Write-Output "Detected reduce-motion block. Body: [$mediaBody]"
            
            # Process each rule block inside the media body
            $rulePos = 0
            while ($rulePos -lt $mediaBody.Length) {
                $braceStart = $mediaBody.IndexOf('{', $rulePos)
                if ($braceStart -lt 0) { break }
                
                $braceCount = 1
                $k = $braceStart + 1
                while ($k -lt $mediaBody.Length -and $braceCount -gt 0 -and $k -lt $mediaBody.Length) {
                    if ($mediaBody[$k] -eq '{') { $braceCount++ }
                    elseif ($mediaBody[$k] -eq '}') { $braceCount-- }
                    $k++
                }
                
                if ($braceCount -ne 0) { break }
                
                $blockContent = $mediaBody.Substring($braceStart + 1, $k - $braceStart - 2)
                $rulePos = $k
                Write-Output "Checking rule block: [$blockContent]"
                
                # Parse declarations
                $decalPattern = '([\w-]+)\s*:\s*([^;]+)'
                $decMatches = [regex]::Matches($blockContent, $decalPattern, 'IgnoreCase')
                
                foreach ($dec in $decMatches) {
                    $prop = $dec.Groups[1].Value.Trim()
                    $val = $dec.Groups[2].Value.Trim()
                    
                    Write-Output "Checking declaration: [$($prop): $val]"
                    
                    # Skip duration/delay/iteration-count (longhands allowed)
                    if ($prop -match '-(duration|delay|iteration-count)$') {
                        Write-Output "Skipping as it's a duration/delay/iteration-count property"
                        continue
                    }
                    
                    # Check if it's a flagged property (case-insensitive)
                    $propLower = $prop.ToLower()
                    $isFlaggedProp = $propLower -in @('animation', 'animation-name', 'transition', 'transition-property')
                    
                    if ($isFlaggedProp) {
                        # Normalize value: remove spaces, handle !important
                        $normalizedVal = $val -replace '\s', ''
                        # Remove !important if present (case-insensitive)
                        $normalizedVal = $normalizedVal -replace '!important$', ''
                        
                        Write-Output "Normalized value: [$normalizedVal]"
                        
                        # If value is 'none', skip
                        if ($normalizedVal -eq 'none') {
                            Write-Output "Skipping: motion property has 'none'"
                            continue
                        }
                        
                        # Flag this as a problem
                        Write-Output "PROBLEM: Motion property has non-none value: [$($prop): $val]"
                        exit 1
                    }
                }
            }
        }
    }
}

exit 0
