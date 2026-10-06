---
name: windows-powershell-commands
description: Correct PowerShell equivalents for common Linux shell commands, plus how to check for and install missing tools on Windows. Use whenever running terminal commands on Windows or in PowerShell (pwsh), when a command fails with "not recognized as a name of a cmdlet", or before using rg, gh, python, node, curl, sudo, or apt.
license: CC0-1.0
compatibility: Windows 10/11 with PowerShell 7+. Also applies to Windows PowerShell 5.1 unless noted.
---

# Windows PowerShell commands

PowerShell isn't bash. Agents often type Linux commands out of habit, and they fail. Before running a command, check which shell you are in.

## Linux habit → PowerShell

| Linux habit | Problem in PowerShell | Use instead |
| --- | --- | --- |
| `mkdir -p a/b c/d` | Several paths in one call get glued into one invalid path | `New-Item -ItemType Directory -Force -Path a/b, c/d` |
| `ls -la` | `-la` isn't a parameter | `Get-ChildItem -Force` |
| `touch file` | No `touch` | `if (-not (Test-Path file)) { New-Item -ItemType File file }` |
| `chmod +x script.sh` | No `chmod`, and not needed on Windows | Nothing; run `.ps1` with `pwsh -File` |
| `sudo apt install x` | No apt; sudo is usually disabled | `winget install --id <Id> -e` |
| `cmd > /dev/null` | Writes to a file literally named `dev\null` on the current drive | `cmd > $null` or `| Out-Null` |
| `cat f | grep x` | Works but slow on big files | `Select-String -Path f -Pattern x` |
| `export X=1` | Not PowerShell syntax | `$env:X = '1'` for this session only |
| `which x` | Not available | `(Get-Command x -ErrorAction SilentlyContinue).Source` |
| `cmd1 && cmd2` | Only works in PowerShell 7+ | Fine in pwsh 7; in 5.1 use `cmd1; if ($?) { cmd2 }` |
| `curl -fsSL url` | In 5.1, `curl` is an alias for `Invoke-WebRequest` | `curl.exe` explicitly, or `Invoke-RestMethod` |

## Pre-run check for Linux habits

Before running a command a model wrote, check it against this pattern. It was tested against both bad and fixed examples:

```powershell
$linuxHabits = '\b(sudo|apt|apt-get|chmod|touch)\b|\bls\s+-\w*a|mkdir\s+-p\s+\S+\s+\S+|mkdir\s+-p\s+\w:.*\w:|/dev/null'
if ($command -match $linuxHabits) { Write-Error "Linux-style command; rewrite for PowerShell: $command" }
```

Keep the `\b` word boundaries. Without them, words like "adapt" match `apt`.

## Check before you use a tool

Don't assume `rg`, `gh`, `python`, `node` or `jq` are installed. Check first:

```powershell
foreach ($t in 'git','gh','python','node','rg') {
  "{0,-8} {1}" -f $t, ((Get-Command $t -ErrorAction SilentlyContinue).Source ?? 'MISSING')
}
```

`python` may resolve to a Microsoft Store stub that prints "Python was not found". Treat that as missing.

If a tool is missing, **tell the user and ask before installing**. Use winget with the exact package ID:

| Tool | winget ID |
| --- | --- |
| GitHub CLI | `GitHub.cli` |
| Python | `Python.Python.3.13` (check `winget search Python.Python` for the current one) |
| Node.js LTS | `OpenJS.NodeJS.LTS` |
| ripgrep | `BurntSushi.ripgrep.MSVC` |

After installing, open a new terminal so the updated `PATH` is picked up.

## Regex and text gotchas

- `-match` on multi-line text: `.` doesn't cross newlines by default. Prefix the pattern with `(?s)` when matching across lines (for example YAML frontmatter).
- `Get-Content -Raw` returns one string; without `-Raw` you get an array of lines.
- In double-quoted strings, `"$name:"` is a parse error (PowerShell reads `name:` as a scope prefix), and `"${file.Name}"` silently prints nothing (it means a variable literally named `file.Name`). Use `"$($name):"` and `"$($file.Name)"`.
- Don't assign to `$matches`; PowerShell overwrites it after every `-match`. Use another name such as `$found`.
- `-match`, `-eq`, `-in` and `-contains` ignore case. When checking a status line, use `-cmatch` and anchor it: `'No check accepted' -match 'Accepted'` is `$true`, which once made a benchmark report failures as successes. `-cmatch '^Accepted'` is safe.
- JSON: `ConvertFrom-Json -AsHashtable` (pwsh 7) when you need to modify and re-serialize; use `ConvertTo-Json -Depth 32` or nested objects get flattened.
- To validate JSON, use `Test-Json`, not `ConvertFrom-Json`: on PowerShell 7.6 `'{"a": 1,}' | ConvertFrom-Json` succeeds (a trailing comma passes) while `Test-Json` returns `$false` (checked 2026-10-04; `ai-loop-council/scripts/test-check-changed.ps1` reproduces it).
- In a function that returns a status code, print with `Write-Host`. `Write-Output` joins the return value, so `exit (Invoke-Check)` receives an array, the report is swallowed, and the exit code is wrong.
- Python printing non-ASCII (emoji, arrows) to the Windows console can raise `UnicodeEncodeError` (cp1252). Set `PYTHONIOENCODING=utf-8` for the command.
- Quote dotted hashtable keys (`'files.exclude'`), and verify the consuming application's exact key names. JSON that parses can still contain unsupported settings.
- Parse edited scripts with `[System.Management.Automation.Language.Parser]::ParseFile` before execution. After `& pwsh -File ...` or a native tool, inspect `$LASTEXITCODE` immediately; a later successful command does not clear the earlier failure.
- Do not hide `2>&1` in `Out-Null` during validation. On failure, inspect diagnostics before reading an output file; that file may be left over from the previous run.
- `Start-Process` takes executable arguments via `-ArgumentList`; `-NoProfile` belongs to `pwsh`, not to `Start-Process`. Track the process returned by `-PassThru` and stop only a server this task started, not any process that happens to use the port.

## Paths

- Forward slashes work in PowerShell and in VS Code workspace files; prefer them in anything shared.
- Never write a user's absolute path (`C:\Users\<name>\...`, drive letters) into files that will be committed. Use repo-relative paths.
