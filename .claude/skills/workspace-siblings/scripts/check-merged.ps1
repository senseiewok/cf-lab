#Requires -Version 7
<#
.SYNOPSIS
  After a pull request is merged, check that nothing pushed to its branch was left behind.

.DESCRIPTION
  A squash merge takes the branch as it was at the moment of the merge. A commit pushed to the branch after that
  (or a pull request stacked on a branch that had already been merged) never reaches main, and GitHub says nothing.
  This script asks GitHub, read-only, and prints one PASS, FAIL or INFO line per check:

    merged         the pull request is merged (FAIL when it is open or closed without merging)
    on-default     the merge commit is on the default branch. A stacked pull request merged into another feature
                   branch FAILS when that merge commit never reached the default branch
    branch-head    the branch's current head on GitHub is still the head the pull request merged. FAIL when commits
                   were pushed after the merge (or the branch was force-pushed); the extra commits are listed.
                   INFO when the branch was deleted (nothing left to compare)
    files          every file the pull request's commits touched (and every file a later commit on the branch touched)
                   has the same content at the branch head as in the merge commit. FAIL lists the files that differ
    main-drift     INFO only: the same files compared with the default branch's head today
    local          with -RepoPath: the local branch of that name, and any worktree on it, hold nothing that is not
                   in the merged head (unpushed commits FAIL, uncommitted changes FAIL)

  Why the merge commit and not origin/main: the merge commit is exactly what the merge put on the base branch and it
  never changes, so the answer is the same tomorrow as today. Comparing with origin/main would flag every file a later
  pull request legitimately changed, and a person would have to judge each one. The comparison with origin/main is
  still printed, as INFO, so a person can look. One case the merge commit can also flag: if the base branch changed
  the same file before a squash merge, the merged file legitimately differs from the branch's version. The FAIL line
  says so; read the diff before acting.

  Only GET requests through `gh api` (no -X, no -f), and only read-only git commands with -RepoPath (no fetch).

  Exit codes: 0 every check passed, 1 a check failed, 2 usage error or an API call failed.

.EXAMPLE
  pwsh -NoProfile -File check-merged.ps1 -Repo senseiewok/cf-research -Pr 22
  pwsh -NoProfile -File check-merged.ps1 -Repo senseiewok/cf-lab -Pr 31 -RepoPath C:\path\to\cf-lab
  pwsh -NoProfile -File check-merged.ps1 -SelfTest
#>
[CmdletBinding()]
param(
    [string] $Repo,
    [int] $Pr,
    [string] $RepoPath,
    [switch] $SelfTest
)
$ErrorActionPreference = 'Stop'

class ApiError : System.Exception { ApiError([string] $m) : base($m) { } }

function Get-Short([string] $sha) { if ($sha -match '^[0-9a-f]{8,}$') { return $sha.Substring(0, 7) } if ($sha) { return $sha } return '(none)' }

function Get-Escaped([string] $path) { return (($path -split '/') | ForEach-Object { [uri]::EscapeDataString($_) }) -join '/' }

# The live API: GET only. Returns the parsed JSON, or $null on HTTP 404. Any other failure throws ApiError.
function Invoke-GhGet([string] $path) {
    $out = & gh api -H 'Accept: application/vnd.github+json' $path 2>&1
    $code = $LASTEXITCODE
    $text = ($out | ForEach-Object { "$_" }) -join "`n"
    if ($code -ne 0) {
        if ($text -match 'HTTP 404|Not Found') { return $null }
        throw [ApiError]::new("gh api $path failed: $($text.Trim())")
    }
    return ($text | ConvertFrom-Json -Depth 50)
}

# Map path -> blob sha for the given files at one commit. A file absent at that commit maps to '(absent)'.
function Get-Blobs($Api, [string] $Repo, [string] $sha, [string[]] $files) {
    $map = @{}
    $tree = & $Api "repos/$Repo/git/trees/${sha}?recursive=1"
    if ($tree -and -not $tree.truncated) {
        $all = @{}
        foreach ($e in @($tree.tree)) { if ($e.type -eq 'blob') { $all[$e.path] = $e.sha } }
        foreach ($f in $files) { $map[$f] = $(if ($all.ContainsKey($f)) { $all[$f] } else { '(absent)' }) }
        return $map
    }
    foreach ($f in $files) {   # a very large tree: ask per file
        $c = & $Api "repos/$Repo/contents/$(Get-Escaped $f)?ref=$sha"
        $map[$f] = $(if ($c -and $c.sha) { $c.sha } else { '(absent)' })
    }
    return $map
}

function Get-PrFiles($Api, [string] $Repo, [int] $Pr) {
    $files = [System.Collections.Generic.List[string]]::new()
    for ($page = 1; $page -le 30; $page++) {
        $batch = @(& $Api "repos/$Repo/pulls/$Pr/files?per_page=100&page=$page")
        foreach ($f in $batch) {
            if ($f.filename) { $files.Add($f.filename) }
            if ($f.previous_filename) { $files.Add($f.previous_filename) }
        }
        if ($batch.Count -lt 100) { break }
    }
    return @($files | Sort-Object -Unique)
}

# Read-only local checks: the local branch and any worktree on it.
function Test-Local([string] $RepoPath, [string] $branch, [string] $prHead, [ref] $fails) {
    $lines = @()
    if (-not (Test-Path -LiteralPath $RepoPath)) { $fails.Value++; return @("FAIL local: -RepoPath '$RepoPath' does not exist") }
    $local = (& git -C $RepoPath rev-parse --verify --quiet "refs/heads/$branch" 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $local) {
        $lines += "INFO local: no local branch '$branch' in $RepoPath"
    } else {
        $local = "$local".Trim()
        & git -C $RepoPath cat-file -e "$prHead^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $lines += "INFO local: the merged head $(Get-Short $prHead) is not in this clone (no fetch is done); cannot compare local branch $(Get-Short $local)"
        } else {
            $extra = @(& git -C $RepoPath rev-list "$prHead..$local" 2>$null | Where-Object { $_ })
            if ($extra.Count -gt 0) {
                $fails.Value++
                $lines += "FAIL local: local branch '$branch' has $($extra.Count) commit(s) not in the merged head $(Get-Short $prHead):"
                foreach ($c in $extra) { $lines += "       $(& git -C $RepoPath log -1 --format='%h %s' $c)" }
            } else {
                $lines += "PASS local: local branch '$branch' ($(Get-Short $local)) holds nothing beyond the merged head"
            }
        }
    }
    $wt = $null
    foreach ($l in @(& git -C $RepoPath worktree list --porcelain)) {
        if ($l -like 'worktree *') { $wt = $l.Substring(9) }
        elseif ($l -eq "branch refs/heads/$branch" -and $wt) {
            $dirty = @(& git -C $wt status --porcelain 2>$null | Where-Object { $_ })
            if ($dirty.Count -gt 0) {
                $fails.Value++
                $lines += "FAIL local: worktree $wt on '$branch' has $($dirty.Count) uncommitted change(s); commit them to a new branch before removing it"
            } else {
                $lines += "PASS local: worktree $wt on '$branch' is clean"
            }
        }
    }
    return $lines
}

# The checks. $Api is a scriptblock: path -> parsed JSON or $null (404). Returns @{ Lines; Fails }.
function Test-MergedPr($Api, [string] $Repo, [int] $Pr, [string] $RepoPath) {
    $lines = [System.Collections.Generic.List[string]]::new()
    $fails = 0
    $p = & $Api "repos/$Repo/pulls/$Pr"
    if (-not $p) { throw [ApiError]::new("pull request $Repo#$Pr not found") }
    if (-not $p.merged) {
        $state = $(if ($p.state -eq 'open') { 'open' } else { 'closed without merging' })
        $lines.Add("FAIL merged: $Repo#$Pr is $state")
        return @{ Lines = $lines; Fails = 1 }
    }
    $mergeSha = $p.merge_commit_sha; $prHead = $p.head.sha; $branch = $p.head.ref; $base = $p.base.ref
    $headRepo = $(if ($p.head.repo) { $p.head.repo.full_name } else { $null })
    $at = $(if ($p.merged_at -is [datetime]) { $p.merged_at.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') } else { "$($p.merged_at)" })
    $lines.Add("PASS merged: $Repo#$Pr merged $at into '$base' as $(Get-Short $mergeSha); merged head $(Get-Short $prHead) of '$branch'")

    $repoInfo = & $Api "repos/$Repo"
    $default = $(if ($repoInfo -and $repoInfo.default_branch) { $repoInfo.default_branch } else { 'main' })
    if ($base -eq $default) {
        $lines.Add("PASS on-default: merged straight into '$default'")
    } else {
        $cmp = & $Api "repos/$Repo/compare/$(Get-Escaped $default)...$mergeSha"
        if ($cmp -and $cmp.status -in 'behind', 'identical') {
            $lines.Add("PASS on-default: stacked on '$base', and the merge commit $(Get-Short $mergeSha) has reached '$default'")
        } else {
            $fails++
            $why = $(if ($cmp) { "'$default' is $($cmp.status) relative to it" } else { 'compare unavailable' })
            $lines.Add("FAIL on-default: stacked pull request: merged into '$base', and its merge commit $(Get-Short $mergeSha) is not on '$default' ($why). Its changes may never have reached '$default'")
        }
    }

    # The branch now. Only meaningful when the head lives in this repository.
    $now = $null; $moved = @(); $movedFiles = @()
    if ($headRepo -and $headRepo -ne $Repo) {
        $br = & $Api "repos/$headRepo/branches/$(Get-Escaped $branch)"
    } else {
        $br = & $Api "repos/$Repo/branches/$(Get-Escaped $branch)"
    }
    if (-not $br) {
        $lines.Add("INFO branch-head: branch '$branch' no longer exists on GitHub; no later pushes to see there (check local clones with -RepoPath)")
    } else {
        $now = $br.commit.sha
        if ($now -eq $prHead) {
            $lines.Add("PASS branch-head: '$branch' is still at the merged head $(Get-Short $prHead); nothing pushed after the merge")
        } else {
            $fails++
            $cmpRepo = $(if ($headRepo) { $headRepo } else { $Repo })
            $cmp = & $Api "repos/$cmpRepo/compare/$prHead...$now"
            $status = $(if ($cmp) { $cmp.status } else { 'unknown' })
            $moved = @(if ($cmp) { @($cmp.commits) })
            $movedFiles = @(if ($cmp) { @($cmp.files | ForEach-Object { $_.filename }) })
            $lines.Add("FAIL branch-head: '$branch' moved after the merge: now $(Get-Short $now), merged $(Get-Short $prHead) (status $status, $($moved.Count) commit(s) not in the merge):")
            foreach ($c in $moved) { $lines.Add("       $(Get-Short $c.sha) $((("$($c.commit.message)") -split "`n")[0])") }
            if ($status -in 'behind', 'diverged') { $lines.Add('       the branch was reset or force-pushed; some merged commits are no longer on it') }
        }
    }

    # File contents: the branch's latest version (or the merged head if the branch is gone) against the merge commit.
    $prFiles = Get-PrFiles $Api $Repo $Pr
    if (@($prFiles).Count -ge 3000) { $lines.Add('INFO files: GitHub lists at most 3000 files per pull request; files beyond that are not checked') }
    $files = @(@($prFiles) + @($movedFiles) | Where-Object { $_ } | Sort-Object -Unique)
    $tip = $(if ($now) { $now } else { $prHead })
    $tipRepo = $(if ($headRepo -and $headRepo -ne $Repo) { $headRepo } else { $Repo })
    if ($files.Count -eq 0) {
        $lines.Add('INFO files: the pull request lists no files')
    } else {
        $atTip = Get-Blobs $Api $tipRepo $tip $files
        $atMerge = Get-Blobs $Api $Repo $mergeSha $files
        $diff = @($files | Where-Object { $atTip[$_] -ne $atMerge[$_] })
        if ($diff.Count -eq 0) {
            $lines.Add("PASS files: all $($files.Count) file(s) the branch touched match the merge commit $(Get-Short $mergeSha)")
        } else {
            $fails++
            $lines.Add("FAIL files: $($diff.Count) of $($files.Count) file(s) differ between the branch ($(Get-Short $tip)) and the merge commit $(Get-Short $mergeSha):")
            foreach ($f in $diff) { $lines.Add("       $f  (branch $(Get-Short $atTip[$f]), merge $(Get-Short $atMerge[$f]))") }
            $lines.Add('       a commit after the merge, or a change the base branch made to the same file before a squash merge; read the diff before acting')
        }
        $defaultBr = & $Api "repos/$Repo/branches/$(Get-Escaped $default)"
        if ($defaultBr) {
            $atDefault = Get-Blobs $Api $Repo $defaultBr.commit.sha $files
            $drift = @($files | Where-Object { $atTip[$_] -ne $atDefault[$_] })
            if ($drift.Count -eq 0 -and $diff.Count -gt 0) {
                $lines.Add("INFO main-drift: all $($files.Count) file(s) at the branch head match '$default' today ($(Get-Short $defaultBr.commit.sha)): the late changes may have landed through a later pull request; confirm before closing this out")
            } elseif ($drift.Count -eq 0) {
                $lines.Add("INFO main-drift: all $($files.Count) file(s) match '$default' today ($(Get-Short $defaultBr.commit.sha))")
            } else {
                $lines.Add("INFO main-drift: $($drift.Count) file(s) differ from '$default' today ($(Get-Short $defaultBr.commit.sha)); later merges may have changed them legitimately, a person judges:")
                foreach ($f in $drift) { $lines.Add("       $f") }
            }
        }
    }

    if ($RepoPath) {
        $ref = [ref]$fails
        foreach ($l in (Test-Local $RepoPath $branch $prHead $ref)) { $lines.Add($l) }
        $fails = $ref.Value
    }
    return @{ Lines = $lines; Fails = $fails }
}

function Write-Result($r) {
    foreach ($l in $r.Lines) { Write-Output $l }
    if ($r.Fails -gt 0) { Write-Output "RESULT FAIL ($($r.Fails) check(s) failed)" } else { Write-Output 'RESULT PASS' }
}

if ($SelfTest) {
    $R = 'o/r'
    function New-Canned([bool] $merged, [string] $branchNow, [string] $base = 'main', [string] $defaultNow = 'm2', [hashtable] $extra = @{}) {
        $c = @{
            "repos/$R/pulls/1"                               = @{ merged = $merged; state = $(if ($merged) { 'closed' } else { 'open' }); merged_at = '2026-10-08T12:00:00Z'
                                                                  merge_commit_sha = $(if ($merged) { 'm1' } else { $null })
                                                                  head = @{ ref = 'feat/x'; sha = 'h1'; repo = @{ full_name = $R } }; base = @{ ref = $base } }
            "repos/$R"                                       = @{ default_branch = 'main' }
            "repos/$R/branches/feat/x"                       = $(if ($branchNow) { @{ commit = @{ sha = $branchNow } } } else { $null })
            "repos/$R/branches/main"                         = @{ commit = @{ sha = $defaultNow } }
            "repos/$R/pulls/1/files?per_page=100&page=1"     = @(@{ filename = 'a.txt' }, @{ filename = 'b.txt' })
            "repos/$R/git/trees/h1?recursive=1"              = @{ truncated = $false; tree = @(@{ type = 'blob'; path = 'a.txt'; sha = 'A1' }, @{ type = 'blob'; path = 'b.txt'; sha = 'B1' }) }
            "repos/$R/git/trees/h2?recursive=1"              = @{ truncated = $false; tree = @(@{ type = 'blob'; path = 'a.txt'; sha = 'A2' }, @{ type = 'blob'; path = 'b.txt'; sha = 'B1' }, @{ type = 'blob'; path = 'c.txt'; sha = 'C1' }) }
            "repos/$R/git/trees/m1?recursive=1"              = @{ truncated = $false; tree = @(@{ type = 'blob'; path = 'a.txt'; sha = 'A1' }, @{ type = 'blob'; path = 'b.txt'; sha = 'B1' }) }
            "repos/$R/git/trees/m2?recursive=1"              = @{ truncated = $false; tree = @(@{ type = 'blob'; path = 'a.txt'; sha = 'A1' }, @{ type = 'blob'; path = 'b.txt'; sha = 'B9' }) }
            "repos/$R/compare/h1...h2"                       = @{ status = 'ahead'; commits = @(@{ sha = 'h2'; commit = @{ message = "security fix pushed late`nbody" } }); files = @(@{ filename = 'a.txt' }, @{ filename = 'c.txt' }) }
            "repos/$R/compare/main...m1"                     = @{ status = 'ahead' }
        }
        foreach ($k in $extra.Keys) { $c[$k] = $extra[$k] }
        # Round-trip through JSON so the script sees the same shapes as from gh api.
        $json = @{}
        foreach ($k in $c.Keys) { $json[$k] = $(if ($null -eq $c[$k]) { $null } else { ConvertTo-Json -InputObject $c[$k] -Depth 20 }) }
        return $json
    }
    function New-Api([hashtable] $json) {
        return { param([string] $path)
            if (-not $json.ContainsKey($path)) { throw [ApiError]::new("self-test: no canned response for $path") }
            if ($null -eq $json[$path]) { return $null }
            return ($json[$path] | ConvertFrom-Json -Depth 50)
        }.GetNewClosure()
    }
    $cases = @(
        @{ name = 'clean merge passes';            canned = (New-Canned $true 'h1');          fails = 0; want = @('PASS merged', 'PASS on-default', 'PASS branch-head', 'PASS files', 'INFO main-drift: 1 file') }
        @{ name = 'commit after merge fails';      canned = (New-Canned $true 'h2');          fails = 2; want = @('FAIL branch-head', 'security fix pushed late', 'FAIL files: 2 of 3', 'a.txt', 'c.txt') }
        @{ name = 'not merged fails';              canned = (New-Canned $false 'h1');         fails = 1; want = @('FAIL merged: o/r#1 is open') }
        @{ name = 'deleted branch, clean merge';   canned = (New-Canned $true $null);         fails = 0; want = @('INFO branch-head', 'PASS files') }
        @{ name = 'stacked PR not on main fails';  canned = (New-Canned $true 'h1' 'feat/base'); fails = 1; want = @('FAIL on-default: stacked') }
    )
    $bad = 0
    foreach ($c in $cases) {
        try {
            $res = Test-MergedPr (New-Api $c.canned) $R 1 $null
            $text = $res.Lines -join "`n"
            $missing = @($c.want | Where-Object { -not $text.Contains($_) })
            if ($res.Fails -ne $c.fails -or $missing) {
                $bad++
                Write-Output "FAIL self-test: $($c.name) (fails $($res.Fails), wanted $($c.fails); missing: $($missing -join ' | '))"
                $res.Lines | ForEach-Object { Write-Output "       | $_" }
            } else { Write-Output "PASS self-test: $($c.name)" }
        } catch { $bad++; Write-Output "FAIL self-test: $($c.name) threw: $($_.Exception.Message)" }
    }
    Write-Output $(if ($bad) { "RESULT FAIL ($bad self-test case(s) failed)" } else { "RESULT PASS ($($cases.Count) self-test cases)" })
    exit $(if ($bad) { 1 } else { 0 })
}

if (-not $Repo -or $Repo -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' -or $Pr -le 0) {
    Write-Output 'usage: check-merged.ps1 -Repo <owner/name> -Pr <number> [-RepoPath <local clone>] | -SelfTest'
    exit 2
}
if (-not (Get-Command gh -CommandType Application -ErrorAction SilentlyContinue)) { Write-Output 'ERROR gh (GitHub CLI) is not installed or not on PATH'; exit 2 }
try {
    $result = Test-MergedPr ${function:Invoke-GhGet} $Repo $Pr $RepoPath
} catch [ApiError] {
    Write-Output "ERROR $($_.Exception.Message)"; exit 2
}
Write-Result $result
exit $(if ($result.Fails -gt 0) { 1 } else { 0 })
