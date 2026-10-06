Rules for writing the PowerShell 7 check. Each one fixes a mistake models have really made here, and each example was run to confirm it.

1. Layout. Use real line breaks and one statement per line. Never write the two characters backslash and n to mean a line break. Prefer a plain `foreach ($file in Get-ChildItem ...) { ... }` loop with simple statements over one long pipeline nested several levels deep: a single missing brace in a one-line pipeline breaks the whole script.

2. PowerShell strings have no backslash escapes. A backslash is an ordinary character in both quote styles.
   - Single quotes: everything is literal. To include one single quote, double it: `'it''s'` is it's.
   - Double quotes: `$` expands. To include a double quote, use a backtick or double it: ``"say `"hi`""``.
   - So `\"` and `\'` do not escape anything. `'[\'"]'` does not parse: the `\'` ends the string.

3. Put every regex in single quotes, so `$` and backslashes stay literal. To match a quote character inside a regex, do not type the quote. Use its hex code: `\x22` is `"` and `\x27` is `'`.
   - Either quote: `'=\s*[\x22\x27]?(.*?)[\x22\x27]?\s*$'`
   - This matches `KEY="v"`, `KEY='v'` and `KEY=v`, and captures `v`.

4. Compare text with `-ceq`, `-cne`, `-cmatch` and `-cin` when the case matters, and use the `-replace` operator instead of `.Replace()`.

5. If the same parsing is needed twice, write a small `function` once and call it, instead of repeating a long expression.

6. Before you answer, check that every `{`, `(` and quote you opened is closed, and that each statement is on its own line.
