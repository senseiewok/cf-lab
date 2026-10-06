$found = $false
foreach ($f in Get-ChildItem -Recurse -File -Include '*.js', '*.mjs') {
    $js = (Get-Content -Raw -LiteralPath $f.FullName) -replace '(?s)/\*.*?\*/', '' -replace '(?m)//.*$', ''
    $loopNames = @([regex]::Matches($js, '\.setAnimationLoop\(\s*([A-Za-z_$][\w$]*)\s*\)') | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -cne 'null' })
    $rafNames = @([regex]::Matches($js, '(?<![\w$.])(?:(?:window|globalThis|self)\.)?requestAnimationFrame\(\s*([A-Za-z_$][\w$]*)\s*\)') | ForEach-Object { $_.Groups[1].Value })
    Write-Output "[$($f.Name)] loop=[$($loopNames -join ',')] raf=[$($rafNames -join ',')]"
    if (@($loopNames | Where-Object { $_ -in $rafNames }).Count) { $found = $true }
}
if ($found) { exit 1 } else { exit 0 }
