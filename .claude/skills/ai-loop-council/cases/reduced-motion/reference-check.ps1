$found = $false
foreach ($f in Get-ChildItem -Filter *.css -File -Recurse) {
    $css = (Get-Content -Raw $f.FullName) -replace '(?s)/\*.*?\*/', ''
    foreach ($start in [regex]::Matches($css, '@media[^{]*\(\s*prefers-reduced-motion\s*(?::\s*reduce\s*)?\)[^{]*\{')) {
        # Walk braces to find the end of this media block, so nested rules and minified CSS both work.
        $depth = 1; $i = $start.Index + $start.Length
        while ($i -lt $css.Length -and $depth -gt 0) { if ($css[$i] -eq '{') { $depth++ } elseif ($css[$i] -eq '}') { $depth-- }; $i++ }
        $block = $css.Substring($start.Index + $start.Length, $i - 1 - ($start.Index + $start.Length))
        foreach ($d in [regex]::Matches($block, '(?<![\w-])(animation|animation-name|transition|transition-property)\s*:\s*([^;}]+)')) {
            $value = ($d.Groups[2].Value -replace '!important', '').Trim()
            Write-Output "[$($f.Name)] [$($d.Groups[1].Value)] [$value]"
            if ($value -ne 'none') { $found = $true }
        }
    }
}
if ($found) { exit 1 } else { exit 0 }
