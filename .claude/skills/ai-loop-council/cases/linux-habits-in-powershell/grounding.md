# Grounding: Linux habits in PowerShell

Two kinds of evidence, collected 2026-09-30.

## Microsoft docs: about_Redirection
https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_redirection

- The redirection operators `>` and `>>` "are effectively aliases for `Out-File`", so `> /dev/null` tries to write a real file.
- To discard output, redirect to `$null` (the docs' example: `6> $null`).

## Experiment: commands run in PowerShell 7.6 on Windows, in a throwaway folder
| Command | Result |
| --- | --- |
| `mkdir -p one/nested/path` | Works; creates the nested folders |
| `mkdir -p two three` | Fails: "A positional parameter cannot be found that accepts argument 'three'." Neither folder is created. |
| `ls -la` | Fails: "A parameter cannot be found that matches parameter name 'la'." |
| `touch x.txt`, `grep` | Fail: "The term ... is not recognized as a name of a cmdlet..." |
| `curl` | Resolves to `C:\windows\system32\curl.exe`, so curl flags work |
| `'x' > /dev/null` | Fails: "Could not find a part of the path 'C:\dev\null'." |

## PowerShell language parser
`[System.Management.Automation.Language.Parser]::ParseInput(...)` returns an AST. `CommandAst` nodes are real commands; `GetCommandName()` gives the name, `CommandElements` the parameters and arguments (`CommandParameterAst` for `-la`), and `Redirections` the redirection targets. Comments and string contents are never `CommandAst` nodes.
