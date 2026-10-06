$foundViolations = $false

$files = Get-ChildItem -Path '*.css' -File

foreach ($file in $files) {
    $css = Get-Content -Path $file.FullName -Raw
    Write-Output "Processing file: [$($file.Name)]"
    
    # Regex to find media blocks with prefers-reduced-motion: reduce
    # (?s) for single-line mode, case-insensitive
    # Match @media block including any media conditions (e.g. 'screen and (...)')
    $mediaPattern = '(?is)@media\s*\{(?:[^{}]*(?:\{[^{}]*\}[^{}]*)*)*\}|(?is)@media\s+((?:[^{}]|\{[^{}]*\})*)\{\s*([^}]*)\}'
    
    # Simpler pattern: capture media block content by tracking braces manually is hard; use iterative stripping
    # Instead, use robust pattern: match from '@media' up to first '{' and then find matching '}' depth
    # But allowed only regex. Use pattern that captures up to the last '}' after balanced braces (imperfect but practical)
    # Better: match the media query condition first, then capture the block.
    
    # Strategy: extract all @media blocks by greedy non-greedy hybrid
    # Pattern: @media ... ( condition ) { ... } (only one level of braces for simplicity, as CSS minified often has no nesting)
    $mediaPattern = '(?is)@media\s*(?:(?:and|not|only|,)?\s*[^{])*\{((?:[^{}]|\{[^{}]*\})*)\}'
    
    # Simpler approach: use split to get @media blocks
    $cssSplit = $css -split '@media'
    
    # Skip first chunk (before any @media)
    for ($i = 1; $i -lt $cssSplit.Count; $i++) {
        $chunk = $cssSplit[$i]
        
        # Extract condition: everything up to the opening brace
        $braceIndex = $chunk.IndexOf('{')
        if ($braceIndex -lt 0) { continue }
        
        $condition = $chunk.Substring(0, $braceIndex)
        $blockContent = $chunk.Substring($braceIndex + 1)
        
        # Remove trailing closing brace(s) and whitespace from blockContent
        # Find the last '}' not part of a nested brace pair (simplified: trim until last '}')
        # Find last } in blockContent (since nested braces unlikely in minified or common CSS)
        $lastBraceIndex = $blockContent.LastIndexOf('}')
        if ($lastBraceIndex -ge 0) {
            $blockContent = $blockContent.Substring(0, $lastBraceIndex)
        }
        
        Write-Output "Checking media block condition: [$condition]"
        Write-Output "Testing reduced-motion block content: [$blockContent]"
        
        # Check if condition contains prefers-reduced-motion: reduce (case-insensitive)
        if ($condition -match 'prefers-reduced-motion\s*:\s*reduce') {
            # Define pattern to find motion-related declarations
            # Case-insensitive, match property: value pairs
            $motionPropsPattern = '(?i)\b(animation|animation-name|transition|transition-property)\s*:\s*([^{};]*)'
            
            $propMatches = [regex]::Matches($blockContent, $motionPropsPattern)
            
            foreach ($propMatch in $propMatches) {
                $property = $propMatch.Groups[1].Value.Trim()
                $value = $propMatch.Groups[2].Value.Trim()
                
                # Remove !important and whitespace
                $valueClean = $value -replace '\s*!\s*important\s*', ''
                $valueClean = $valueClean.Trim()
                
                Write-Output "Found motion property: [$($property): $($value)] => clean value: [$valueClean]"
                
                # Check if value is NOT 'none' (case-insensitive)
                if ($valueClean -notmatch '^[nN][oO][nN][eE]$') {
                    Write-Output "VIOLATION: Motion enabled when reduced motion requested. [$($property): $($valueClean)]"
                    $foundViolations = $true
                }
            }
        }
    }
}

# Exit based on findings
if ($foundViolations) {
    Write-Output "[Result: Exit code 1 - violations detected]"
    exit 1
} else {
    Write-Output "[Result: Exit code 0 - no violations]"
    exit 0
}
