# Test for render-board.ps1 (board T-0024: complexity, recommended_route, route_rationale). Throwaway boards only: it never touches
# tasks/board.json or tasks/BOARD.md. No network, no model. Prints PASS/FAIL per check; exit 0 only when all pass.
param([string] $Script = (Join-Path $PSScriptRoot 'render-board.ps1'))
$ErrorActionPreference = 'Stop'
$base = Join-Path ([IO.Path]::GetTempPath()) ('render-board-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $base | Out-Null
$fail = @(); $n = 0
function Check([string] $name, [bool] $ok, [string] $detail = '') {
    $script:n++
    Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  ($detail)" }))
    if (-not $ok) { $script:fail += $name }
}
function New-Task([hashtable] $extra = @{}, [string] $id = 'T-0001') {
    $t = [ordered]@{
        id = $id; title = "A task $id"; repo = 'cf-lab'; area = 'tooling'; status = 'proposed'; priority = 'P2'
        created_at = '2026-10-05T00:00:00Z'; created_by = @{ kind = 'human'; name = 'tester' }
        source_evidence = 'test'; effort_hours = @{ low = 1; high = 2 }
        roi = @{ benefit = 3; rationale = 'r'; confidence = 'low'; measured = $false; actual_hours = $null; measured_outcome = $null }
        acceptance = 'a check'; review_tier = 'routine'; depends_on = @(); notes = ''
    }
    foreach ($k in $extra.Keys) { $t[$k] = $extra[$k] }
    return $t
}
function Run-Render([object[]] $tasks, [switch] $Check) {
    $b = Join-Path $base ('b-' + [guid]::NewGuid().ToString('N').Substring(0, 6) + '.json')
    $o = $b -replace '\.json$', '.md'
    (@{ schema_version = 1; tasks = $tasks } | ConvertTo-Json -Depth 10) | Set-Content $b -Encoding utf8
    $a = @('-NoProfile', '-File', $Script, '-BoardPath', $b, '-OutPath', $o)
    if ($Check) { $a += '-Check' }
    $out = & pwsh @a 2>&1 | Out-String
    return @{ Code = $LASTEXITCODE; Out = $out; Md = $(if (Test-Path $o) { Get-Content -Raw $o } else { '' }); Board = $b; OutPath = $o }
}
try {
    # the existing contract
    $r = Run-Render @((New-Task))
    Check 'a plain task still renders (exit 0) and is listed' ($r.Code -eq 0 -and $r.Md -match 'T-0001') $r.Out
    Check '-Check is current right after rendering' ((& pwsh -NoProfile -File $Script -BoardPath $r.Board -OutPath $r.OutPath -Check 2>&1 | Out-String) -match 'current') ''
    Set-Content $r.OutPath 'stale' -Encoding utf8
    $null = & pwsh -NoProfile -File $Script -BoardPath $r.Board -OutPath $r.OutPath -Check 2>&1
    Check '-Check exits 1 when BOARD.md is stale' ($LASTEXITCODE -eq 1) "exit=$LASTEXITCODE"

    # the new, optional fields
    $r = Run-Render @((New-Task @{ complexity = 'high'; recommended_route = 'frontier'; route_rationale = 'planning and risky design' }))
    Check 'complexity and route render as columns' ($r.Code -eq 0 -and $r.Md -match '\| Complexity \| Route \|' -and $r.Md -match '\| high \| frontier \|') $r.Out
    Check 'the route and its rationale appear in the task detail' ($r.Md -match '\*\*Route:\*\* frontier' -and $r.Md -match 'planning and risky design') $r.Md
    $r = Run-Render @((New-Task @{ complexity = 'low' }))
    Check 'complexity alone is fine (the route is optional)' ($r.Code -eq 0) $r.Out
    $r = Run-Render @((New-Task))
    Check 'a task with neither field renders with empty cells' ($r.Code -eq 0 -and $r.Md -notmatch 'Route:\*\*') $r.Out
    foreach ($route in 'local', 'cloud', 'frontier') {
        $r = Run-Render @((New-Task @{ recommended_route = $route; route_rationale = 'because' }))
        Check "route '$route' is accepted" ($r.Code -eq 0) $r.Out
    }
    $r = Run-Render @((New-Task @{ complexity = 'huge' }))
    Check 'a complexity outside low/medium/high is rejected with exit 2' ($r.Code -eq 2 -and $r.Out -match 'complexity') $r.Out
    $r = Run-Render @((New-Task @{ recommended_route = 'gpu'; route_rationale = 'x' }))
    Check 'a route outside local/cloud/frontier is rejected with exit 2' ($r.Code -eq 2 -and $r.Out -match 'recommended_route') $r.Out
    $r = Run-Render @((New-Task @{ recommended_route = 'local' }))
    Check 'a route with no rationale is rejected with exit 2' ($r.Code -eq 2 -and $r.Out -match 'route_rationale') $r.Out
    $r = Run-Render @((New-Task @{ recommended_route = 'local'; route_rationale = '   ' }))
    Check 'a blank rationale counts as none' ($r.Code -eq 2) $r.Out
    $r = Run-Render @((New-Task @{ recommended_route = 'Local'; route_rationale = 'x' }))
    Check 'values are case-sensitive (Local is rejected)' ($r.Code -eq 2) $r.Out

    # statuses are untouched by rendering, and the real board still renders as current
    $tasks = @((New-Task @{ status = 'in_progress' } 'T-0001'), (New-Task @{ status = 'proposed'; complexity = 'low' } 'T-0002'))
    $r = Run-Render $tasks
    Check 'task statuses are listed under their own headings' ($r.Md -match '## in progress \(1\)' -and $r.Md -match '## proposed \(1\)') $r.Md
    # dates are culture-invariant ISO, and Windows PowerShell 5.1 renders the same bytes as PowerShell 7
    $tasks = @((New-Task @{ created_at = '2026-10-05T23:30:00Z' } 'T-0002'), (New-Task @{} 'T-0001'))
    $r = Run-Render $tasks
    Check 'created_at renders as an ISO date (yyyy-MM-dd), not a culture date' ($r.Md -match '\| 2026-10-05 \|' -and $r.Md -notmatch '\d\d/\d\d/\d{4}') $r.Md
    Check 'tied tasks are ordered by id' ($r.Md.IndexOf('| T-0001 |') -lt $r.Md.IndexOf('| T-0002 |')) $r.Md
    $ps51 = Get-Command powershell.exe -ErrorAction SilentlyContinue
    if ($ps51) {
        $o51 = $r.OutPath -replace '\.md$', '-ps51.md'
        $null = & $ps51.Source -NoProfile -File $Script -BoardPath $r.Board -OutPath $o51 2>&1
        Check 'Windows PowerShell 5.1 renders byte-identical output' ((Test-Path $o51) -and (Get-FileHash $o51).Hash -eq (Get-FileHash $r.OutPath).Hash) "exit=$LASTEXITCODE"
    } else { Write-Output 'SKIP Windows PowerShell 5.1 comparison (powershell.exe not found)' }

    $real = Join-Path $PSScriptRoot 'board.json'
    if (Test-Path $real) {
        $o = & pwsh -NoProfile -File $Script -BoardPath $real -OutPath (Join-Path $PSScriptRoot 'BOARD.md') -Check 2>&1 | Out-String
        Check 'the real board renders as current' ($LASTEXITCODE -eq 0) $o
    }
} finally { Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
