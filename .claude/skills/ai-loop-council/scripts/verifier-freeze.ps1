<#
.SYNOPSIS
  Functions for delegate.ps1 (V2-02): freeze the verifier and run it only inside a copy. Dot-sourced; it runs nothing on its own.

.DESCRIPTION
  The manifest is the verifier file, every file under the verifier's own folder, and any files or folders named with -VerifierFiles. It leaves out
  .git, __pycache__, .pytest_cache, .loop-logs and *.pyc, and it refuses symlinks and junctions. The copy keeps the layout relative to the nearest
  folder that holds every manifest path. A manifest is hashed twice: over the raw bytes (what blocks a run) and over the bytes with CRLF turned
  into LF (only for comparing the same tree across checkouts, where git may have changed the line endings).

  What this does and does not claim. It detects a change to a declared verifier file between the proof and acceptance, and it refuses, before the
  first model call, a verifier whose run on an empty stub reaches a relative path outside its manifest. It is not a sandbox: an absolute path, an
  environment variable, an installed package, a tool on PATH, the network, and any code path the empty stub does not reach are all outside it, and
  a verifier that loops over a missing folder passes with nothing to check. Verifier authors should assert that their fixture count is above zero.
#>

# Folders and files that the loop or the interpreter itself changes: never part of the manifest.
$script:VfSkipDirs = @('.git', '__pycache__', '.pytest_cache', '.loop-logs')
$script:VfComparison = if ($IsWindows) { [StringComparison]::OrdinalIgnoreCase } else { [StringComparison]::Ordinal }
# Paths are compared the way the file system does: ignoring case on Windows, exactly elsewhere (so A.txt and a.txt are two files on Linux).
$script:VfComparer = if ($IsWindows) { [StringComparer]::OrdinalIgnoreCase } else { [StringComparer]::Ordinal }

function Get-VfSha256([byte[]] $Bytes) { return ([BitConverter]::ToString([Security.Cryptography.SHA256]::HashData($Bytes)) -replace '-', '').ToLowerInvariant() }

# True when $Path is $Dir or lies inside it.
function Test-VfUnder([string] $Path, [string] $Dir) {
    $p = [IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    $d = [IO.Path]::GetFullPath($Dir).TrimEnd('\', '/')
    return ($p.Equals($d, $script:VfComparison) -or $p.StartsWith($d + [IO.Path]::DirectorySeparatorChar, $script:VfComparison) -or $p.StartsWith($d + [IO.Path]::AltDirectorySeparatorChar, $script:VfComparison))
}

# The deepest folder that holds every folder in $Dirs, or $null when they share no root (different drives).
function Get-VfCommonRoot([string[]] $Dirs) {
    $sep = [IO.Path]::DirectorySeparatorChar
    $split = @($Dirs | ForEach-Object { , @([IO.Path]::GetFullPath($_).TrimEnd('\', '/') -split '[\\/]') })
    $common = @()
    for ($i = 0; ; $i++) {
        $seg = $null; $same = $true
        foreach ($s in $split) {
            if ($i -ge $s.Count) { $same = $false; break }
            if ($null -eq $seg) { $seg = $s[$i] } elseif (-not $seg.Equals($s[$i], $script:VfComparison)) { $same = $false; break }
        }
        if (-not $same) { break }
        $common += $seg
    }
    if (-not $common.Count) { return $null }
    $root = $common -join $sep
    if ($root -eq '') { return [string]$sep }
    if ($root -match '^[A-Za-z]:$') { return $root + $sep }
    return $root
}

# Collect the files under $Dir into $Acc.Files; symlinks and junctions go to $Acc.Reparse and are not followed. Stops once a cap is passed.
function Find-VfFiles([string] $Dir, $Acc) {
    foreach ($e in Get-ChildItem -LiteralPath $Dir -Force) {
        if ($Acc.Stop) { return }
        if ($e.Attributes -band [IO.FileAttributes]::ReparsePoint) { $Acc.Reparse.Add($e.FullName); continue }
        if ($e.PSIsContainer) {
            if ($script:VfSkipDirs -contains $e.Name) { continue }
            Find-VfFiles $e.FullName $Acc
        } else {
            if ($e.Name -like '*.pyc') { continue }
            if (-not $Acc.Seen.Add($e.FullName)) { continue }   # named twice (a -VerifierFiles folder that holds the verifier's own folder): counted once
            $Acc.Files.Add($e)
            $Acc.Bytes += $e.Length
            if ($Acc.Files.Count -gt $Acc.MaxFiles -or $Acc.Bytes -gt $Acc.MaxBytes) { $Acc.Stop = $true; return }
        }
    }
}

# Work out the manifest. Returns an object with Error set (a sentence for the person) or with Root, Verify, VerifyRel and Files (Rel, Full, Length).
function Get-VerifierPlan([string] $Verify, [string[]] $Extra, [string] $OutFull, [string] $WorkFull, [int] $MaxFiles, [long] $MaxBytes) {
    $hint = ' Put the verifier in a folder of its own, and name anything else it needs with -VerifierFiles.'
    $vfull = [IO.Path]::GetFullPath($Verify)
    $vdir = Split-Path -Parent $vfull
    $trees = [Collections.Generic.List[string]]::new(); $singles = [Collections.Generic.List[string]]::new()
    $trees.Add($vdir)
    if ((Get-Item -LiteralPath $vdir -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return [pscustomobject]@{ Error = "refusing a symlink or junction in the verifier manifest: the verifier's own folder $vdir" } }
    foreach ($x in @($Extra | Where-Object { $_ })) {
        $xf = [IO.Path]::GetFullPath($x)
        if (Test-Path -LiteralPath $xf -PathType Container) { $trees.Add($xf) }
        elseif (Test-Path -LiteralPath $xf -PathType Leaf) { $singles.Add($xf) }
        else { return [pscustomobject]@{ Error = "a -VerifierFiles path does not exist: $x" } }
        if ((Get-Item -LiteralPath $xf -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { return [pscustomobject]@{ Error = "refusing a symlink or junction in the verifier manifest: $x" } }
    }
    foreach ($t in $trees) {
        if (Test-VfUnder $OutFull $t) { return [pscustomobject]@{ Error = "the output file is inside the verifier's folder ($t): a candidate written there would change the manifest on every attempt.$hint" } }
        if (Test-VfUnder $WorkFull $t) { return [pscustomobject]@{ Error = "the work folder is inside the verifier's folder ($t): the loop's own files would change the manifest.$hint" } }
    }
    foreach ($s in $singles) { if ($s.Equals([IO.Path]::GetFullPath($OutFull), $script:VfComparison)) { return [pscustomobject]@{ Error = "the output file is named in -VerifierFiles: $s" } } }

    $acc = [pscustomobject]@{ Files = [Collections.Generic.List[IO.FileInfo]]::new(); Reparse = [Collections.Generic.List[string]]::new(); Seen = [Collections.Generic.HashSet[string]]::new($script:VfComparer); Bytes = [long]0; MaxFiles = $MaxFiles; MaxBytes = $MaxBytes; Stop = $false }
    foreach ($t in $trees) { Find-VfFiles $t $acc }
    foreach ($s in $singles) { if ($acc.Seen.Add($s)) { $fi = Get-Item -LiteralPath $s -Force; $acc.Files.Add($fi); $acc.Bytes += $fi.Length } }
    if ($acc.Reparse.Count) { return [pscustomobject]@{ Error = "refusing a symlink or junction in the verifier manifest: $($acc.Reparse[0])" } }
    if ($acc.Files.Count -gt $MaxFiles) { return [pscustomobject]@{ Error = "the verifier manifest has more than $MaxFiles files (the -MaxManifestFiles cap).$hint" } }
    if ($acc.Bytes -gt $MaxBytes) { return [pscustomobject]@{ Error = "the verifier manifest is larger than $MaxBytes bytes (the -MaxManifestBytes cap).$hint" } }

    $dirs = @($trees) + @($singles | ForEach-Object { Split-Path -Parent $_ })
    $root = Get-VfCommonRoot $dirs
    if (-not $root) { return [pscustomobject]@{ Error = 'the verifier and its -VerifierFiles share no common folder (different drives?)' } }
    $files = [Collections.Generic.List[object]]::new()
    foreach ($f in $acc.Files) {
        $rel = ([IO.Path]::GetRelativePath($root, $f.FullName)) -replace '\\', '/'
        $files.Add([pscustomobject]@{ Rel = $rel; Full = $f.FullName; Length = $f.Length })
    }
    $sorted = @($files | Sort-Object -Property @{ Expression = { $_.Rel }; Ascending = $true })
    return [pscustomobject]@{ Error = $null; Root = $root; Verify = $vfull; VerifyRel = (([IO.Path]::GetRelativePath($root, $vfull)) -replace '\\', '/'); Files = $sorted; Bytes = $acc.Bytes }
}

# Copy the manifest into $Dest, keeping the layout. An existing $Dest is replaced.
function Copy-VfFiles($Plan, [string] $Dest) {
    if (Test-Path -LiteralPath $Dest) { Remove-Item -LiteralPath $Dest -Recurse -Force }
    foreach ($f in $Plan.Files) {
        $t = Join-Path $Dest ($f.Rel -replace '/', [IO.Path]::DirectorySeparatorChar)
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $t) | Out-Null
        Copy-Item -LiteralPath $f.Full -Destination $t -Force
    }
}

# Raw and line-ending-normalised SHA-256 of one file. A file with a NUL byte is binary and is not normalised.
function Get-VfFileHash([string] $Path) {
    $b = [IO.File]::ReadAllBytes($Path)
    $raw = Get-VfSha256 $b
    $norm = $raw
    if ($b.Length -gt 0 -and [Array]::IndexOf([byte[]]$b, [byte]0) -lt 0) {
        $s = [Text.Encoding]::Latin1.GetString($b)
        if ($s.Contains("`r`n")) { $norm = Get-VfSha256 ([Text.Encoding]::Latin1.GetBytes($s.Replace("`r`n", "`n"))) }
    }
    return [pscustomobject]@{ Raw = $raw; Norm = $norm }
}

# rel -> {Raw, Norm} for each file of the plan, read from the live path or, when $CopyRoot is given, from the same layout under it.
function Get-VfHashes($Plan, [string] $CopyRoot) {
    $h = [Collections.Specialized.OrderedDictionary]::new($script:VfComparer)
    foreach ($f in $Plan.Files) {
        $path = if ($CopyRoot) { Join-Path $CopyRoot ($f.Rel -replace '/', [IO.Path]::DirectorySeparatorChar) } else { $f.Full }
        $h[$f.Rel] = Get-VfFileHash $path
    }
    return $h
}

# One hash for the whole manifest: the SHA-256 of the sorted lines "<path>TAB<hash>". $Kind is Raw or Norm.
function Get-VfManifestHash($Hashes, [string] $Kind) {
    [string[]]$keys = @($Hashes.Keys)
    [Array]::Sort($keys, [StringComparer]::Ordinal)
    $text = ($keys | ForEach-Object { "$_`t$($Hashes[$_].$Kind)`n" }) -join ''
    return Get-VfSha256 ([Text.Encoding]::UTF8.GetBytes($text))
}

# What differs between two hash sets, as short sentences. A change that is only line endings is said so. Empty when they are equal on raw bytes.
function Compare-VfHashes($Old, $New) {
    $out = @()
    foreach ($k in $Old.Keys) {
        if (-not $New.Contains($k)) { $out += "removed: $k"; continue }
        if ($Old[$k].Raw -ne $New[$k].Raw) { $out += $(if ($Old[$k].Norm -eq $New[$k].Norm) { "changed (line endings only): $k" } else { "changed: $k" }) }
    }
    foreach ($k in $New.Keys) { if (-not $Old.Contains($k)) { $out += "added: $k" } }
    return $out
}

# PowerShell prints an error with its message wrapped after a few words and each continuation line starting with "     | ": join those lines so a message can be matched.
function ConvertTo-VfFlatText([string] $Text) { return [regex]::Replace($Text, '\s*\r?\n[ \t]*\|?[ \t]*', ' ') }

# Paths and modules the verifier's output says it could not find, as Kind path or module with the Name as written. Nothing else is read from the text: a
# missing function or an "is not recognized" error is an ordinary failure on an empty stub, not a hole in the manifest.
function Get-VfMissing([string] $Text) {
    $Text = ConvertTo-VfFlatText $Text
    $found = @()
    foreach ($pattern in "Cannot find path '([^']+)'", "No such file or directory: '([^']+)'", "Could not find (?:a part of the path|file|a part of the file path) '([^']+)'", "FileNotFoundError[^\r\n]*?'([^']+)'") {
        foreach ($m in [regex]::Matches($Text, $pattern)) { $found += [pscustomobject]@{ Kind = 'path'; Name = $m.Groups[1].Value } }
    }
    foreach ($m in [regex]::Matches($Text, "ModuleNotFoundError: No module named '([^']+)'")) { $found += [pscustomobject]@{ Kind = 'module'; Name = $m.Groups[1].Value } }
    # A script or module reached by a path (a dot-sourced ../lib/x.ps1, Import-Module ../lib/x.psm1) names that path in its error; a plain function name has no separator.
    foreach ($pattern in "The term '([^']+)' is not recognized", "The specified module '([^']+)' was not loaded") {
        foreach ($m in [regex]::Matches($Text, $pattern)) { if ($m.Groups[1].Value -match '[\\/]') { $found += [pscustomobject]@{ Kind = 'path'; Name = $m.Groups[1].Value } } }
    }
    return $found
}

# The first path the verifier could not find that EXISTS at the same place beside the live verifier: a file it needs that the manifest does not hold. A
# path that is missing live as well is the verifier's or the worker's own bug, and a path outside the copy's neighbourhood is not our business: both
# stay ordinary failures. $Skip are paths never counted (the candidate or the stub). Returns the path as it lies under the copy, or $null.
function Get-VfHole([string] $Text, [string] $CopyRoot, [string] $LiveRoot, [string] $Cwd, [string[]] $Skip) {
    foreach ($f in @(Get-VfMissing $Text | Where-Object { $_.Kind -eq 'path' -and $_.Name })) {
        try { $full = if ([IO.Path]::IsPathRooted($f.Name)) { [IO.Path]::GetFullPath($f.Name) } else { [IO.Path]::GetFullPath((Join-Path $Cwd $f.Name)) } } catch { continue }
        # the candidate, the stub, or anything in their folder is not the manifest's business
        if (@($Skip | Where-Object { $_ -and ($full.Equals([IO.Path]::GetFullPath($_), $script:VfComparison) -or [IO.Path]::GetDirectoryName($full).Equals([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($_)), $script:VfComparison)) }).Count) { continue }
        $rel = [IO.Path]::GetRelativePath($CopyRoot, $full)
        if ([IO.Path]::IsPathRooted($rel)) { continue }   # another drive
        $live = [IO.Path]::GetFullPath((Join-Path $LiveRoot $rel))
        if (Test-Path -LiteralPath $live) { return $full }
    }
    return $null
}

# A Python module the verifier could not import, unless it is the candidate or the stub being imported by its own name (that is an ordinary failure).
function Get-VfMissingModule([string] $Text, [string[]] $CandidatePaths) {
    $own = @($CandidatePaths | Where-Object { $_ } | ForEach-Object { [IO.Path]::GetFileNameWithoutExtension($_) -replace '[-.]', '_' })
    foreach ($f in @(Get-VfMissing $Text | Where-Object { $_.Kind -eq 'module' })) {
        $top = ($f.Name -split '\.')[0]
        if ($own -notcontains ($top -replace '[-.]', '_')) { return $f.Name }
    }
    return $null
}

# Run the verifier from its copy, with the copy's folder as the working folder. Returns Code and Text (stdout and stderr together), and NoInterpreter when
# python or pwsh itself could not be started.
function Invoke-VfVerifier([string] $VerifierCopy, [string] $Candidate) {
    $oldBytecode = $env:PYTHONDONTWRITEBYTECODE
    $env:PYTHONDONTWRITEBYTECODE = '1'
    Push-Location (Split-Path -Parent $VerifierCopy)
    $code = $null; $v = ''; $none = $false
    try {
        $v = if ($VerifierCopy -match '\.py$') { & python $VerifierCopy $Candidate 2>&1 | Out-String } else { & pwsh -NoProfile -File $VerifierCopy -Script $Candidate 2>&1 | Out-String }
        $code = $LASTEXITCODE
    } catch [System.Management.Automation.CommandNotFoundException] {
        $none = $true; $code = 127; $v = "the interpreter for the verifier could not be started: $($_.Exception.Message)"
    } finally {
        Pop-Location
        if ($null -eq $oldBytecode) { Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue } else { $env:PYTHONDONTWRITEBYTECODE = $oldBytecode }
    }
    return [pscustomobject]@{ Code = $code; Text = $v; NoInterpreter = $none }
}

# Remove from the copy every file that is not in the frozen set. A verifier may leave a cache or a marker in its working folder; if it stayed, a later
# attempt (or the next run of the same verifier) could read state an earlier one wrote, and the copy would no longer be what was hashed.
function Clear-VfCopyExtras($Frozen, [string] $CopyRoot) {
    if (-not (Test-Path -LiteralPath $CopyRoot)) { return }
    $keep = [Collections.Generic.HashSet[string]]::new($script:VfComparer)
    foreach ($k in $Frozen.Keys) { [void]$keep.Add([IO.Path]::GetFullPath((Join-Path $CopyRoot ($k -replace '/', [IO.Path]::DirectorySeparatorChar)))) }
    foreach ($f in @(Get-ChildItem -LiteralPath $CopyRoot -Recurse -Force -File)) { if (-not $keep.Contains($f.FullName)) { Remove-Item -LiteralPath $f.FullName -Force -ErrorAction SilentlyContinue } }
    foreach ($d in @(Get-ChildItem -LiteralPath $CopyRoot -Recurse -Force -Directory | Sort-Object { $_.FullName.Length } -Descending)) {
        if (-not (Get-ChildItem -LiteralPath $d.FullName -Force)) { Remove-Item -LiteralPath $d.FullName -Force -ErrorAction SilentlyContinue }
    }
}
