$found = $false
$habits = 'sudo', 'apt', 'apt-get', 'chmod', 'chown', 'touch', 'grep', 'which', 'export'
foreach ($f in Get-ChildItem -Recurse -File -Filter *.ps1) {
    $tokens = $null; $parseErrors = $null
    $ast = [System.Management.Automation.Language.Parser]::ParseInput((Get-Content -Raw -LiteralPath $f.FullName), [ref]$tokens, [ref]$parseErrors)
    foreach ($c in $ast.FindAll({ $args[0] -is [System.Management.Automation.Language.CommandAst] }, $true)) {
        $name = $c.GetCommandName()
        $params = @($c.CommandElements | Where-Object { $_ -is [System.Management.Automation.Language.CommandParameterAst] } | ForEach-Object { $_.ParameterName })
        $positional = @($c.CommandElements | Select-Object -Skip 1 | Where-Object { $_ -isnot [System.Management.Automation.Language.CommandParameterAst] })
        $devNull = @($c.Redirections | Where-Object { $_.Location -and $_.Location.Extent.Text -eq '/dev/null' }).Count
        Write-Output "[$($f.Name)] [$name] params=[$($params -join ',')] positional=$($positional.Count) devnull=$devNull"
        if ($name -in $habits) { $found = $true }
        if ($name -in 'ls', 'rm' -and @($params | Where-Object { $_ -match '^[a-z]{2,3}$' }).Count) { $found = $true }
        if ($name -eq 'mkdir' -and $params -contains 'p' -and $positional.Count -ge 2) { $found = $true }
        if ($devNull) { $found = $true }
    }
}
if ($found) { exit 1 } else { exit 0 }
