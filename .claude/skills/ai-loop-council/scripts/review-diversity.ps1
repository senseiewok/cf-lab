<#
.SYNOPSIS
  Compare how many planted defects each local model profile finds in a set of small scripts, and whether
  a second model finds defects the first one misses (review diversity).

.DESCRIPTION
  review-cases/<case>/ holds scripts with known planted defects (truth.json) plus clean scripts. Each profile
  reviews every script several times, with the same findings schema the council uses. A finding "hits" a
  defect when its quote contains the defect's anchor text, or its line number is the anchor's line.
  Findings that hit nothing are listed for a person to read: some are real problems nobody planted, and
  that judgement is not automatic. Any finding on a clean script is a candidate false alarm.

  Reports, per profile: distinct defects found, average per-sample recall, findings per script, parse
  failures. Then which defects each profile found that no other profile did, and the union of every pair.

  The scripts in review-cases are intentionally flawed. Nothing here runs them; they are only read as text.

.EXAMPLE
  ./review-diversity.ps1 -Samples 3 -RawLog reviews.jsonl -Profiles ../../model-qwen3-8-27b/ollama-profile.fast.json, ../../model-deepseek-r1-32b/ollama-profile.json
  ./review-diversity.ps1 -FromLog reviews.jsonl     # score again, no model
  ./review-diversity.ps1 -SelfTest                  # check the scoring rules, no model
#>
[CmdletBinding()]
param(
    [string[]] $Profiles,
    [ValidateRange(1, 10)] [int] $Samples = 3,
    [string] $CaseDir = (Join-Path $PSScriptRoot '../review-cases/seeded-powershell'),
    # Append every raw reply here (JSONL) so misses and false alarms can be read. Keep it local.
    [string] $RawLog,
    # Score a saved log again with the current rules. No model is called.
    [string] $FromLog,
    [switch] $SelfTest
)

$ErrorActionPreference = 'Stop'

function Format-Text([string] $text) { ($text -replace '\s+', ' ').Trim().ToLowerInvariant() }

# Collapse whitespace, then cut to at most $max characters. (Measure the length AFTER collapsing: cutting by the
# original length throws when the collapsed text is shorter.)
function Limit-Text($text, [int] $max) {
    $t = ([string]$text -replace '\s+', ' ').Trim()
    if ($t.Length -gt $max) { $t.Substring(0, $max) } else { $t }
}

function Get-Defects([string] $dir) {
    $truth = Get-Content -Raw (Join-Path $dir 'truth.json') | ConvertFrom-Json
    foreach ($d in $truth.defects) {
        $fileLines = @(Get-Content -LiteralPath (Join-Path $dir $d.file))
        # A defect can be described on more than one line (the bad split and the use of its result), so
        # truth.json may list extra anchors in "also". Any of them counts.
        $anchors = @(@($d.anchor) + @($d.also) | Where-Object { $_ } | ForEach-Object { Format-Text $_ })
        $found = [System.Collections.Generic.List[int]]::new()
        foreach ($a in $anchors) {
            for ($i = 0; $i -lt $fileLines.Count; $i++) { if ((Format-Text $fileLines[$i]).Contains($a)) { $found.Add($i + 1); break } }
        }
        [pscustomobject]@{ id = $d.id; file = $d.file; anchors = $anchors; lines = @($found); what = $d.what }
    }
}

# Which planted defects does one finding hit? A finding with no quote and no line hits nothing.
function Get-Hits($finding, $defects) {
    $quote = Format-Text ([string]$finding.quote)
    $file = Split-Path -Leaf ([string]$finding.file)
    foreach ($d in $defects) {
        if ($file -and $file -ne $d.file) { continue }
        $byQuote = $quote -and [bool]($d.anchors | Where-Object { $quote.Contains($_) })
        $byLine = $null -ne $finding.line -and ([string]$finding.line).Trim() -ne '' -and ([int]$finding.line -in $d.lines)
        if ($byQuote -or $byLine) { $d.id }
    }
}

function Get-Numbered([string] $path) {
    $i = 0; (Get-Content -LiteralPath $path | ForEach-Object { $i++; '{0,3}: {1}' -f $i, $_ }) -join "`n"
}

function New-ReviewPrompt([string] $name, [string] $numbered) {
@"
Review this PowerShell script for real defects: security problems, and bugs that would cause wrong behaviour in normal use. Report only defects you can point to in the code, and quote the exact line. Do not report style, naming, or missing comments. The file may contain none, one or several defects; if it has none, return an empty findings list.

File: $name
$numbered
"@
}

if ($SelfTest) {
    $defects = @(
        [pscustomobject]@{ id = 'a'; file = 'one.ps1'; anchors = @('--insecure'); lines = @(12); what = '' },
        [pscustomobject]@{ id = 'b'; file = 'one.ps1'; anchors = @('remove-item -recurse', 'param($dir)'); lines = @(20, 1); what = '' },
        [pscustomobject]@{ id = 'c'; file = 'two.ps1'; anchors = @('--insecure'); lines = @(3); what = '' }
    )
    $cases = @(
        @{ n = 'quote contains the anchor';      f = @{ file = 'one.ps1'; quote = '    --insecure `'; line = 99 };                   want = 'a' }
        @{ n = 'case and spacing ignored';       f = @{ file = 'one.ps1'; quote = 'REMOVE-ITEM   -Recurse -Force $x'; line = 99 };   want = 'b' }
        @{ n = 'matches by line number';         f = @{ file = 'one.ps1'; quote = 'something else'; line = 12 };                     want = 'a' }
        @{ n = 'right text, wrong file';         f = @{ file = 'two.ps1'; quote = '--insecure'; line = 99 };                         want = 'c' }
        @{ n = 'second anchor of one defect';    f = @{ file = 'one.ps1'; quote = 'PARAM($Dir)'; line = 99 };                        want = 'b' }
        @{ n = 'second anchor, by line';         f = @{ file = 'one.ps1'; quote = 'x'; line = 1 };                                    want = 'b' }
        @{ n = 'unrelated finding hits nothing'; f = @{ file = 'one.ps1'; quote = 'write-output'; line = 7 };                         want = '' }
        @{ n = 'blank line value hits nothing';  f = @{ file = 'one.ps1'; quote = 'write-output'; line = '' };                        want = '' }
        @{ n = 'missing quote and line';         f = @{ file = 'one.ps1' };                                                          want = '' }
        @{ n = 'path in the file field';         f = @{ file = 'C:\x\one.ps1'; quote = '--insecure'; line = 99 };                    want = 'a' }
    )
    $fail = 0
    # The printing step crashed once on text whose whitespace collapses to fewer characters than the original.
    $limits = @(
        @{ n = 'limit: spaced text shrinks';    got = (Limit-Text "a    b`n`n  c" 60);    want = 'a b c' }
        @{ n = 'limit: long text is cut';       got = (Limit-Text ('x' * 100) 10);        want = ('x' * 10) }
        @{ n = 'limit: empty and null';         got = ((Limit-Text '' 5) + (Limit-Text $null 5)); want = '' }
    )
    foreach ($l in $limits) { $ok = $l.got -ceq $l.want; if (-not $ok) { $fail++ }; '{0,-5} {1,-32} got [{2}]' -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $l.n, $l.got }
    foreach ($c in $cases) { $got = (@(Get-Hits ([pscustomobject]$c.f) $defects) -join ','); $ok = $got -eq $c.want; if (-not $ok) { $fail++ }; '{0,-5} {1,-32} expected [{2}] got [{3}]' -f $(if ($ok) { 'PASS' } else { 'FAIL' }), $c.n, $c.want, $got }
    $real = Get-Defects $CaseDir; $bad = @($real | Where-Object { $_.lines.Count -ne $_.anchors.Count })
    if ($bad) { $fail++; "FAIL  anchors not found in their files: $(($bad.id) -join ', ')" } else { "PASS  every anchor of all $($real.Count) planted defects is found in the fixture files" }
    if ($fail) { "$fail self-test(s) failed"; exit 1 } else { 'All self-tests passed'; exit 0 }
}

if (-not $Profiles -and -not $FromLog) { throw 'Pass -Profiles, -FromLog <raw log>, or -SelfTest.' }
$defects = @(Get-Defects $CaseDir)

# Raw rows: profile, file, sample, error, findings (array)
if ($FromLog) {
    $raw = foreach ($line in Get-Content $FromLog) { $line | ConvertFrom-Json }
}
else {
    $invoke = Join-Path $PSScriptRoot 'invoke-local-model.ps1'
    $schema = Join-Path $PSScriptRoot 'findings.schema.json'
    $files = @(Get-ChildItem -LiteralPath $CaseDir -Filter *.ps1 | Sort-Object Name)
    $work = Join-Path ([IO.Path]::GetTempPath()) ('review-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        $raw = foreach ($profilePath in $Profiles) {
            $pd = Get-Content -Raw $profilePath | ConvertFrom-Json
            $label = "$($pd.model)$(if ($null -ne $pd.think) { if ($pd.think) { ' (thinking)' } else { ' (fast)' } })"
            foreach ($f in $files) {
                $promptPath = Join-Path $work "$($f.BaseName).md"
                Set-Content -LiteralPath $promptPath -Value (New-ReviewPrompt $f.Name (Get-Numbered $f.FullName))
                for ($n = 1; $n -le $Samples; $n++) {
                    $err = $null; $found = @()
                    try {
                        $reply = (& $invoke -PromptFile $promptPath -SchemaFile $schema -ProfileFile (Resolve-Path $profilePath).Path | Out-String) | ConvertFrom-Json
                        $found = @($reply.findings)
                    }
                    catch { $err = $_.Exception.Message }
                    $row = [pscustomobject]@{ profile = $label; file = $f.Name; sample = $n; error = $err; findings = $found }
                    if ($RawLog) { $row | ConvertTo-Json -Compress -Depth 8 | Add-Content $RawLog }
                    $row
                }
            }
            # Unload before the next model so they don't compete for GPU memory.
            $null = Invoke-RestMethod -Uri 'http://localhost:11434/api/generate' -Method Post -Body (@{ model = $pd.model; keep_alive = 0 } | ConvertTo-Json) -ContentType 'application/json'
        }
    }
    finally { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}

$buggyFiles = @($defects.file | Sort-Object -Unique)
$rows = foreach ($r in $raw) {
    $hits = [System.Collections.Generic.HashSet[string]]::new()
    $other = @()
    foreach ($fd in @($r.findings)) {
        if ($null -eq $fd) { continue }
        $h = @(Get-Hits $fd $defects)
        if ($h.Count) { foreach ($x in $h) { $null = $hits.Add($x) } } else { $other += $fd }
    }
    [pscustomobject]@{ profile = $r.profile; file = $r.file; sample = $r.sample; error = $r.error; hits = @($hits); other = $other; count = @($r.findings | Where-Object { $null -ne $_ }).Count; clean = ($r.file -notin $buggyFiles) }
}

'=== Per profile ==='
$profilesSeen = @($rows.profile | Sort-Object -Unique)
$rows | Group-Object profile | ForEach-Object {
    $g = @($_.Group); $bugRows = @($g | Where-Object { -not $_.clean }); $cleanRows = @($g | Where-Object clean)
    $found = @($bugRows.hits | Sort-Object -Unique)
    # Average recall per sample = defects found in one pass over every buggy script, averaged over passes.
    $passes = $bugRows | Group-Object sample | ForEach-Object { @($_.Group.hits | Sort-Object -Unique).Count }
    [pscustomobject]@{
        profile = $_.Name
        distinct_found = "$($found.Count)/$($defects.Count)"
        avg_per_pass = [math]::Round((($passes | Measure-Object -Average).Average), 1)
        findings_per_script = [math]::Round((($g | Measure-Object count -Average).Average), 1)
        clean_script_findings = "$(($cleanRows | Measure-Object count -Sum).Sum)/$($cleanRows.Count) scripts-runs"
        failed_replies = @($g | Where-Object error).Count
    }
} | Format-Table -AutoSize | Out-String -Width 220

'=== Each defect: passes that found it, per profile ==='
$matrix = foreach ($d in $defects) {
    $row = [ordered]@{ defect = $d.id }
    foreach ($p in $profilesSeen) { $mine = @($rows | Where-Object { $_.profile -eq $p -and $_.file -eq $d.file }); $row[$p] = "$(@($mine | Where-Object { $_.hits -contains $d.id }).Count)/$($mine.Count)" }
    [pscustomobject]$row
}
$matrix | Format-Table -AutoSize -Wrap | Out-String -Width 240

'=== Diversity: defects found only by one profile, and the union of each pair ==='
$foundBy = @{}; foreach ($p in $profilesSeen) { $foundBy[$p] = @($rows | Where-Object { $_.profile -eq $p -and -not $_.clean } | ForEach-Object { $_.hits } | Sort-Object -Unique) }
foreach ($p in $profilesSeen) {
    $others = @($profilesSeen | Where-Object { $_ -ne $p } | ForEach-Object { $foundBy[$_] } | Sort-Object -Unique)
    $only = @($foundBy[$p] | Where-Object { $_ -notin $others })
    "{0,-30} found only by this profile: {1}" -f $p, $(if ($only) { $only -join ', ' } else { '(none)' })
}
''
for ($i = 0; $i -lt $profilesSeen.Count; $i++) { for ($j = $i + 1; $j -lt $profilesSeen.Count; $j++) {
    $u = @($foundBy[$profilesSeen[$i]] + $foundBy[$profilesSeen[$j]] | Sort-Object -Unique)
    '{0,-30} + {1,-30} union: {2}/{3}' -f $profilesSeen[$i], $profilesSeen[$j], $u.Count, $defects.Count
} }
''
'=== Findings that hit no planted defect (read these: some may be real, some are false alarms) ==='
$rows | Where-Object { $_.other.Count } | ForEach-Object { $row = $_; $row.other | ForEach-Object { [pscustomobject]@{ profile = $row.profile; file = $row.file; line = $_.line; quote = (Limit-Text $_.quote 60); problem = (Limit-Text $_.problem 110) } } } |
    Sort-Object profile, file, quote -Unique | Format-Table -AutoSize -Wrap | Out-String -Width 260
