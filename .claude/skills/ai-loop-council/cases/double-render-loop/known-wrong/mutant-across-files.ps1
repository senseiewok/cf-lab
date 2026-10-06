$loopAll = @(); $rafAll = @()
foreach ($f in Get-ChildItem -Recurse -File -Include '*.js', '*.mjs') {
    $js = (Get-Content -Raw -LiteralPath $f.FullName) -replace '(?s)/\*.*?\*/', '' -replace '(?m)//.*$', ''
    $loopAll += @([regex]::Matches($js, '\.setAnimationLoop\(\s*([A-Za-z_$][\w$]*)\s*\)') | ForEach-Object { $_.Groups[1].Value } | Where-Object { $_ -cne 'null' })
    $rafAll += @([regex]::Matches($js, '(?<![\w$.])(?:(?:window|globalThis|self)\.)?requestAnimationFrame\(\s*([A-Za-z_$][\w$]*)\s*\)') | ForEach-Object { $_.Groups[1].Value })
}
Write-Output "[all files] loop=[$($loopAll -join ',')] raf=[$($rafAll -join ',')]"
if (@($loopAll | Where-Object { $_ -cin $rafAll }).Count) { exit 1 } else { exit 0 }
