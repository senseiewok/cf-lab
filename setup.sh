#!/bin/sh
set -eu

usage() {
    printf 'usage: setup.sh\n'
}

# --- 1. Arguments (none) ---
if [ "$#" -gt 0 ]; then
    usage
    exit 2
fi

# --- 2. Paths ---
HERE=$(cd "$(dirname "$0")" && pwd -P)
ROOT=$(dirname "$HERE")

# --- 4. git present ---
if ! command -v git >/dev/null 2>&1; then
    printf 'error: Git is required and was not found. On macOS run: xcode-select --install\n'
    exit 1
fi

# --- 5. Clone / verify cf-skills and cf-research ---
printf "Setting up Sensei Ewok's CF Lab...\n"

clone_or_check() {
    NAME=$1
    TARGET="$ROOT/$NAME"
    if [ ! -e "$TARGET" ]; then
        printf -- '- Cloning senseiewok/%s ...\n' "$NAME"
        if ! git clone "https://github.com/senseiewok/$NAME" "$TARGET"; then
            printf 'error: Failed to clone senseiewok/%s.\n' "$NAME"
            exit 1
        fi
    else
        if [ -d "$TARGET/.git" ]; then
            printf -- '- %s already present\n' "$NAME"
        else
            printf 'error: %s exists but is not a git checkout; no files were overwritten.\n' "$NAME"
            exit 1
        fi
    fi
}

clone_or_check cf-skills
clone_or_check cf-research

# --- 6. cf-lab-files folder ---
FILES_DIR="$ROOT/cf-lab-files"
if [ -e "$FILES_DIR" ]; then
    if [ ! -d "$FILES_DIR" ]; then
        printf 'error: "%s" exists but is a file.\n' "$FILES_DIR"
        exit 1
    fi
    printf -- '- cf-lab-files already present\n'
else
    mkdir "$FILES_DIR"
    printf -- '- Created cf-lab-files\n'
fi

if [ ! -d "$FILES_DIR/memory" ]; then
    mkdir "$FILES_DIR/memory"
fi
if [ ! -d "$FILES_DIR/scratch" ]; then
    mkdir "$FILES_DIR/scratch"
fi

README_FILE="$FILES_DIR/README.md"
if [ ! -e "$README_FILE" ]; then
    cat > "$README_FILE" <<'README_EOF'
cf-lab-files
This folder is local to this machine. It is not a git repository and is never published.
memory/   handoff.md (session notes), machine.md (paths, local model), observations.md (dated candidates)
scratch/  disposable; search skips it
Never put here: API keys or .env files, patient data or any patient-level rows, private site or deploy details,
transcripts or raw model output, third-party instructions, personal email addresses.
Nothing here is the only copy of anything you cannot lose: there is no history and no backup.
Rules and lessons live in the repos (AGENTS.md, skills, tasks/board.json), not here. If this disagrees with the board, the board wins.
README_EOF
fi

# --- 8. Done ---
printf '\nDone. Open cf-lab.code-workspace in this checkout in VS Code.\n'
printf 'Optional, not run by setup: browser testing with Playwright. See "Optional pieces" in README.md.\n'
exit 0
