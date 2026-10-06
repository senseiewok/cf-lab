Detect real-looking secret values in environment template files, which are meant to be committed with placeholders only.

Scan every file named `.env.example`, `.env.sample` or `.env.template`, in any folder. For each `KEY=VALUE` line:
- The line may start with `export `, may have spaces around `=`, and the value may be wrapped in single or double quotes.
- Ignore blank lines and comment lines starting with `#`.
- A key is a secret key if, after splitting its name on `_` (case-insensitive), any part is PASSWORD, PASSWD, PASS, PWD, SECRET, TOKEN, KEY or APIKEY. So `API_KEY` and `db_password` are secret keys; `KEYBOARD_LAYOUT`, `DONKEY_NAME` and `COMPASS_HEADING` are not.
- A secret key's value must be a placeholder: empty, or (case-insensitive, after removing quotes) starting with `your_` or `your-`, wrapped in `<...>`, `changeme` / `change_me`, three or more `x`, starting with `placeholder` or `example`, `replace_me` / `replace-me`, or a `${...}` reference.

Exit 1 if any secret key has a non-placeholder value. Non-secret keys (hosts, ports, user names) are never flagged.
