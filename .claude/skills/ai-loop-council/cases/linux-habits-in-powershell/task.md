Detect Linux shell habits in PowerShell scripts that fail or misbehave in PowerShell 7 on Windows.

In every `.ps1` file (any folder), exit 1 if a real command (not a comment, not text inside a string) is any of:
- `sudo`, `apt`, `apt-get`, `chmod`, `chown`, `touch`, `grep`, `which` or `export`.
- `ls` or `rm` with bundled short flags: a parameter made of 2 or 3 lowercase letters, such as `-la`, `-rf`, `-lah`.
- `mkdir -p` followed by two or more paths.
- Any output redirected to `/dev/null` (for example `> /dev/null` or `2>/dev/null`).

Do not flag:
- These words inside comments or strings.
- `mkdir -p` with a single path (PowerShell creates the parent folders).
- `curl` with its usual flags (it runs curl.exe).
- Variables or other names that merely contain these words, such as `$adapter` or `$touchCount`.
- Normal PowerShell parameters such as `-Force` or `-Recurse`.

Tip: PowerShell can parse a script into commands for you, so comments and strings are excluded automatically.
