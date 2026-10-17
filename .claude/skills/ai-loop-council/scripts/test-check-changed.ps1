param([string] $Script = (Join-Path $PSScriptRoot 'check-changed.ps1'))
# Independent verifier for check-changed.ps1 (written by the orchestrator, not the model).
$ErrorActionPreference = 'Stop'
$base = Join-Path ([IO.Path]::GetTempPath()) ('changed-verify-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $base | Out-Null
$fail = @(); $n = 0
function NewRepo([string] $name) { $r = Join-Path $base $name; New-Item -ItemType Directory $r | Out-Null; & git -C $r init -q 2>&1 | Out-Null; return $r }
function W([string] $repo, [string] $rel, [string] $text) { $p = Join-Path $repo $rel; New-Item -ItemType Directory -Force (Split-Path $p) | Out-Null; [IO.File]::WriteAllText($p, $text, [Text.UTF8Encoding]::new($false)) }
function Stage([string] $repo, [string[]] $paths) { & git -C $repo -c core.safecrlf=false add -- @paths 2>&1 | Out-Null }
function Case([string] $name, [int] $want, [string] $repo, [string] $needle = '') {
    $script:n++
    $o = & pwsh -NoProfile -File $Script -RepoPath $repo 2>&1; $code = $LASTEXITCODE; $text = ($o | Out-String)
    $ok = ($code -eq $want) -and ((-not $needle) -or $text.Contains($needle))
    Write-Output (('PASS ', 'FAIL ')[-not $ok] + $name + $(if (-not $ok) { "  (exit $code, wanted $want; output: " + ($text -replace '\s+', ' ').Trim() + ')' }))
    if (-not $ok) { $script:fail += $name }
}
try {
    $hasYaml = $false; try { & python -c "import yaml" 2>$null; $hasYaml = ($LASTEXITCODE -eq 0) } catch {}
    # nothing staged
    $r = NewRepo 'empty'; Case 'nothing staged -> 0 and says so' 0 $r 'no staged files'
    # not a repo
    $nr = Join-Path $base 'notrepo'; New-Item -ItemType Directory $nr | Out-Null; Case 'outside a git repository -> 2' 2 $nr 'error:'
    # valid files
    $r = NewRepo 'good'; W $r 'a.ps1' 'Write-Output "hi"'; W $r 'a.json' '{"a": 1}'; W $r 'a.py' 'x = 1'; W $r 'notes.md' 'text {{{'; Stage $r @('a.ps1', 'a.json', 'a.py', 'notes.md')
    Case 'valid ps1, json, py and a markdown file -> 0' 0 $r 'OK'
    # each kind of break
    $r = NewRepo 'badps1'; W $r 'b.ps1' 'if ($x { Write-Output 1'; Stage $r @('b.ps1'); Case 'staged ps1 with a syntax error -> 1' 1 $r 'FAIL b.ps1'
    $r = NewRepo 'badjson'; W $r 'b.json' '{"a": 1,}'; Stage $r @('b.json'); Case 'staged invalid json -> 1' 1 $r 'FAIL b.json'
    $r = NewRepo 'badpy'; W $r 'b.py' "def f(:`n    pass"; Stage $r @('b.py'); Case 'staged py with a syntax error -> 1' 1 $r 'FAIL b.py'
    if ($hasYaml) { $r = NewRepo 'badyaml'; W $r 'b.yaml' "a: [1, 2`nb: : :"; Stage $r @('b.yaml'); Case 'staged invalid yaml -> 1' 1 $r 'FAIL b.yaml'
                    $r = NewRepo 'goodyaml'; W $r 'g.yaml' "a: 1`nb: [1, 2]"; Stage $r @('g.yaml'); Case 'staged valid yaml -> 0' 0 $r 'PASS g.yaml' }
    # the index, not the working tree
    $r = NewRepo 'index'; W $r 'c.ps1' 'if ($x { broken'; Stage $r @('c.ps1'); W $r 'c.ps1' 'Write-Output "fixed but not staged"'
    Case 'checks the STAGED version even if the working copy was fixed' 1 $r 'FAIL c.ps1'
    $r = NewRepo 'index2'; W $r 'd.ps1' 'Write-Output "ok"'; Stage $r @('d.ps1'); W $r 'd.ps1' 'if ($x { broken but unstaged'
    Case 'ignores a broken working copy when the staged version is fine' 0 $r 'PASS d.ps1'
    # a recorded known-wrong example is kept on purpose, so it is skipped, not failed
    $r = NewRepo 'knownwrong'; W $r 'cases/x/known-wrong/bad.ps1' 'if ($x { broken'; Stage $r @('cases/x/known-wrong/bad.ps1'); Case 'a staged known-wrong example is skipped, not failed' 0 $r 'SKIP'
    # non-ASCII text in a Python or YAML file is not a syntax error (the check used to pipe the text through the console encoding)
    $r = NewRepo 'nonascii'; W $r 'u.py' ("s = '" + [char]0xFEFF + "caf" + [char]0xE9 + "'`nprint(s.lstrip('" + [char]0xFEFF + "'))"); Stage $r @('u.py'); Case 'a python file with a BOM character and an accent parses' 0 $r 'PASS u.py'
    if ($hasYaml) { $r = NewRepo 'nonasciiyaml'; W $r 'u.yaml' ("name: caf" + [char]0xE9 + "`nnote: " + [char]0xFEFF + "x"); Stage $r @('u.yaml'); Case 'a yaml file with non-ASCII text parses' 0 $r 'PASS u.yaml' }
    # paths with spaces
    $r = NewRepo 'space'; W $r 'my dir/bad file.json' '{'; Stage $r @('my dir/bad file.json'); Case 'path with spaces is handled' 1 $r 'FAIL my dir/bad file.json'
    # owning checkers
    $r = NewRepo 'board'; W $r 'tasks/board.json' '{}'; W $r 'tasks/render-board.ps1' 'exit 7'; Stage $r @('tasks/board.json', 'tasks/render-board.ps1')
    Case 'staging tasks/board.json runs render-board.ps1 -Check and a failure fails' 1 $r 'owning checker render-board.ps1'
    $r = NewRepo 'board-ok'; W $r 'tasks/board.json' '{}'; W $r 'tasks/render-board.ps1' 'exit 0'; Stage $r @('tasks/board.json');
    Case 'owning checker that passes does not fail the run' 0 $r 'OK'
    $r = NewRepo 'noboardscript'; W $r 'tasks/board.json' '{}'; Stage $r @('tasks/board.json'); Case 'no render-board.ps1 in the repo: nothing to run -> 0' 0 $r 'OK'
    $r = NewRepo 'skill'; W $r '.claude/skills/x/SKILL.md' "---`nname: x`n---"; W $r 'tasks/check-skill-frontmatter.py' 'import sys; sys.exit(3)'; Stage $r @('.claude/skills/x/SKILL.md')
    Case 'staging a SKILL.md runs check-skill-frontmatter.py and a failure fails' 1 $r 'owning checker check-skill-frontmatter.py'
    $r = NewRepo 'skill-ok'; W $r '.claude/skills/x/SKILL.md' "---`nname: x`n---"; W $r 'tasks/check-skill-frontmatter.py' 'import sys; sys.exit(0)'; Stage $r @('.claude/skills/x/SKILL.md')
    Case 'passing skill checker -> 0' 0 $r 'OK'
    # T-0074: cf-research source-overlap, quotation-length, and stated-evidence number checks
    $realCso = Join-Path $PSScriptRoot '../../../../../cf-research/tools/sources/check_source_overlap.py'
    $realCn  = Join-Path $PSScriptRoot '../../../../../cf-research/tools/sources/check_numbers.py'
    if ((Test-Path -LiteralPath $realCso) -and (Test-Path -LiteralPath $realCn)) {
        $csoCode = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $realCso).Path, [Text.UTF8Encoding]::new($false))
        $cnCode  = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $realCn).Path, [Text.UTF8Encoding]::new($false))
        $thirtyWords = (0..29 | ForEach-Object { "wordtoken$_" }) -join ' '

        # 1. When sources/downloads does not exist, skips with a visible message and runs --quotes-only
        $r = NewRepo 'cso-nodl'
        W $r 'tools/sources/check_source_overlap.py' $csoCode
        W $r 'notes/clean.md' 'A short paraphrased note with no long quotes.'
        Stage $r @('tools/sources/check_source_overlap.py', 'notes/clean.md')
        Case 'T-0074: skips check_source_overlap when sources/downloads does not exist' 0 $r 'SKIP check_source_overlap.py: sources/downloads does not exist'

        # 2. --quotes-only fails when a staged markdown note has a >8-word quote even without sources/downloads
        $r = NewRepo 'cso-quote'
        W $r 'tools/sources/check_source_overlap.py' $csoCode
        W $r 'notes/quoted.md' 'The report states "one two three four five six seven eight nine ten" verbatim.'
        Stage $r @('tools/sources/check_source_overlap.py', 'notes/quoted.md')
        Case 'T-0074: check_source_overlap --quotes-only fails on a 10-word quote' 1 $r 'FAIL owning checker check_source_overlap.py --quotes-only'

        # 3. When sources/downloads exists, a 30-word copy in a staged .md or .yaml fails
        $r = NewRepo 'cso-copy'
        W $r 'tools/sources/check_source_overlap.py' $csoCode
        W $r 'sources/downloads/report.txt' ("Header text. " + $thirtyWords + " trailing source words.")
        W $r 'notes/copy.md' ("Our note: " + $thirtyWords + " end.")
        Stage $r @('tools/sources/check_source_overlap.py', 'notes/copy.md')
        Case 'T-0074: a 30-word copy in staged markdown fails when sources/downloads exists' 1 $r 'FAIL owning checker check_source_overlap.py'

        # 4. For a note with a stated evidence file, check_numbers.py runs and fails on an invented number
        $r = NewRepo 'cn-bad'
        W $r 'tools/sources/check_source_overlap.py' $csoCode
        W $r 'tools/sources/check_numbers.py' $cnCode
        W $r 'notes/ev.txt' 'The cohort included 33,782 genotyped people and 99.4 percent coverage.'
        W $r 'notes/draft.md' "Evidence: notes/ev.txt`n`nThe cohort included 33,785 genotyped people."
        Stage $r @('tools/sources/check_source_overlap.py', 'tools/sources/check_numbers.py', 'notes/ev.txt', 'notes/draft.md')
        Case 'T-0074: check_numbers.py fails when a note with a stated evidence file has an unmatched number' 1 $r 'FAIL owning checker check_numbers.py'

        $r = NewRepo 'cn-ok'
        W $r 'tools/sources/check_source_overlap.py' $csoCode
        W $r 'tools/sources/check_numbers.py' $cnCode
        W $r 'notes/draft-evidence.txt' 'The cohort included 33,782 genotyped people and 99.4 percent coverage.'
        W $r 'notes/draft.md' 'The cohort included 33,782 genotyped people and 99.4 percent coverage.'
        Stage $r @('tools/sources/check_source_overlap.py', 'tools/sources/check_numbers.py', 'notes/draft-evidence.txt', 'notes/draft.md')
        Case 'T-0074: check_numbers.py passes when all numbers match the companion evidence file' 0 $r 'OK'
    }
    # read-only
    $r = NewRepo 'ro'; W $r 'e.json' '{"a":1}'; Stage $r @('e.json'); $before = (& git -C $r status --porcelain) -join '|'
    $null = & pwsh -NoProfile -File $Script -RepoPath $r 2>&1; $after = (& git -C $r status --porcelain) -join '|'
    $script:n++; $same = ($before -eq $after); Write-Output (('PASS ', 'FAIL ')[-not $same] + 'does not change the index or working tree'); if (-not $same) { $fail += 'read-only' }
} finally { Remove-Item -Recurse -Force $base -ErrorAction SilentlyContinue }
Write-Output "$($n - $fail.Count)/$n passed"
exit ([int]($fail.Count -gt 0))
