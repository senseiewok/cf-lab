$files = Get-ChildItem -File -Recurse -Include *.js,*.mjs
if (-not $files) { exit 0 }

foreach ($file in $files) {
    $content = Get-Content -Raw -Path $file
    
    # Remove comments: handle block comments first, then line comments
    $contentNoComments = $content -replace '/\*[*\s\S]*?\*/', ''
    $contentNoComments = $contentNoComments -replace '//[^\r\n]*', ''
    
    Write-Output "[Processing file: $(Split-Path -Leaf $file)]"
    
    # Extract function names used in setAnimationLoop(...) calls
    # Allow optional leading object: word. (e.g., renderer.)
    $setLoopCalls = [regex]::Matches($contentNoComments, '(?s)(?:\b\w+\.)?setAnimationLoop\s*\(\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\)') | ForEach-Object { $_.Groups[1].Value }
    
    Write-Output "[setAnimationLoop function names: $(($setLoopCalls -join ', ')))]"
    
    if ($setLoopCalls.Count -eq 0) { continue }
    
    # Extract function names used in requestAnimationFrame(...) calls
    # Allow optional leading object: window., globalThis., self.
    $rafaCalls = [regex]::Matches($contentNoComments, '(?s)(?:(?:window|globalThis|self)\.)?requestAnimationFrame\s*\(\s*([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\)') | ForEach-Object { $_.Groups[1].Value }
    
    Write-Output "[requestAnimationFrame function names: $(($rafaCalls -join ', ')))]"
    
    # Case-sensitive intersection using -ccontains (PowerShell 7)
    $found = $false
    foreach ($func in $setLoopCalls) {
        if ($rafaCalls -ccontains $func) {
            $found = $true
            break
        }
    }
    
    if ($found) {
        Write-Output "[Found problematic overlap: $func in $file]"
        exit 1
    }
}
exit 0
