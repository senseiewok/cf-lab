#!/usr/bin/env python3
"""Contract test for the lab setup scripts: setup.cmd (Windows) and setup.sh (macOS and Linux).

Each script is copied into a throwaway fixture whose root folder contains a space, with a stub `git`
(no network, no clone) and run through the contract: clones of cf-skills and cf-research beside the
checkout, the cf-lab-files folder, no flags, no workspace generation, and no dependence on VERSION.
It also checks the repo files setup relies on: the shipped cf-lab.code-workspace, the .gitignore rules
for private workspaces, and the format of VERSION.

Usage:
    python test-setup.py                    run every target available here (sh anywhere, cmd on Windows)
    python test-setup.py --target sh        only setup.sh
    python test-setup.py --target cmd       only setup.cmd (Windows)
    python test-setup.py --target sh --script PATH   test a candidate script instead of the repo's

Exit 0 only when every check passes. Failure lines start with FAIL.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FILES = "cf-lab-files"
CLONES = ["cf-research", "cf-skills"]
README = (HERE / "lab-files-readme.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
EXCLUDE = {"**/node_modules": True, "**/.git": True, "**/.svn": True, "**/.hg": True, "**/CVS": True, "**/.DS_Store": True, "**/Thumbs.db": True, "**/*.tmp": True}
WATCH = {"**/node_modules": True, "**/bower_components": True, "**/*.min.js": True, "**/*.min.css": True, "**/node_modules/**": True, "**/.git/**": True, "**/.svn/**": True, "**/.hg/**": True, "**/CVS/**": True, "**/.DS_Store": True, "**/Thumbs.db": True, "**/*.tmp": True}
SEARCH = {"**/" + FILES + "/scratch/**": True, **WATCH}
EXPECTED = {
    "folders": [
        {"path": ".", "name": "\U0001F916 Sensei Ewok's CF Lab"},
        {"path": "../cf-skills", "name": "\u26a1 CF Skills"},
        {"path": "../cf-research", "name": "\U0001F680 CF Research"},
        {"path": "../" + FILES, "name": "\U0001F4C1 Files"},
    ],
    "settings": {"files.exclude": EXCLUDE, "search.exclude": SEARCH, "files.watcherExclude": WATCH},
}
STUB_SH = '#!/bin/sh\necho "$*" >> "$GIT_LOG"\nif [ "$1" = clone ]; then\n  if [ -n "$STUB_GIT_FAIL" ]; then exit 23; fi\n  mkdir -p "$3/.git"\n  exit 0\nfi\necho "unexpected git call: $*" >&2\nexit 99\n'
STUB_CMD = '@echo off\r\n>>"%GIT_LOG%" echo %*\r\nif /i not "%~1"=="clone" exit /b 99\r\nif defined STUB_GIT_FAIL exit /b 23\r\nmd "%~3\\.git"\r\nexit /b 0\r\n'
BANNED = [
    (r"\[\[", "[[ ]] is a bashism"), (r"\breadlink\s+-f", "readlink -f is not on macOS"), (r"\bmapfile\b|\breadarray\b", "mapfile is bash 4"),
    (r"\$\{[A-Za-z_]+(,,|\^\^)", "case-conversion expansion is bash 4"), (r"\bdeclare\b|\btypeset\b", "declare/typeset"),
    (r"\bsed\s+-i", "sed -i differs on macOS"), (r"\becho\s+-[en]", "echo -e/-n is not portable; use printf"), (r"^\s*source\s", "source is a bashism; use ."),
    (r"^\s*function\s", "function keyword"), (r"<<<", "here-string"), (r"\$'[^'\n]*\\[nrtabfve0]", "$'...' ANSI-C quoting"), (r"\brealpath\b", "realpath is not on old macOS"),
    (r"\bgrep\s+-[A-Za-z]*P", "grep -P is GNU only"), (r"\[ [^]]*==", "== inside [ ] is a bashism"), (r"\bwhich\b", "use command -v, not which"),
]
SEMVER = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")


def find_posix_shells():
    """(strict sh, bash). On Windows these come from Git for Windows (usr/bin); elsewhere from PATH."""
    dash = shutil.which("dash")
    bash = shutil.which("bash")
    if os.name != "nt" and Path("/bin/bash").exists():
        bash = "/bin/bash"  # on macOS this is Apple's bash 3.2, older than a Homebrew bash found first on PATH
    if os.name == "nt":
        git = shutil.which("git")
        for parent in (Path(git).parents if git else []):
            usr = parent / "usr" / "bin"
            if (usr / "dash.exe").exists():
                dash, bash = str(usr / "dash.exe"), str(usr / "bash.exe")
                break
    return dash or shutil.which("sh"), bash


def check_repo_files(repo=REPO):
    """Checks on the tracked files setup relies on. They do not depend on which script is under test."""
    fails = []

    def fail(msg):
        fails.append(f"FAIL [repo] {msg}")

    ws_path = repo / "cf-lab.code-workspace"
    try:
        raw = ws_path.read_bytes()
        if not raw.isascii():
            fail("cf-lab.code-workspace must be ASCII (use \\u escapes for the emoji)")
        if json.loads(raw.decode("utf-8")) != EXPECTED:
            fail("cf-lab.code-workspace differs from the expected folders and settings")
    except Exception as e:  # noqa: BLE001
        fail(f"cf-lab.code-workspace is missing or not valid JSON ({type(e).__name__})")

    def ignored(name):
        p = subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", name], capture_output=True, text=True)
        return p.returncode
    for name, want, why in (("cf-lab-admin.code-workspace", 0, "the private workspace must be ignored"),
                            ("cf-lab-admin-home.code-workspace", 0, "any cf-lab-admin*.code-workspace must be ignored"),
                            ("workspace-admin.code-workspace", 0, "the earlier private workspace name must stay ignored"),
                            ("workspace.code-workspace", 0, "the legacy generated workspace must stay ignored"),
                            ("cf-lab.code-workspace", 1, "the shipped workspace must not be ignored")):
        rc = ignored(name)
        if rc not in (0, 1):
            fail(f"git check-ignore could not run on {name} (exit {rc})")
        elif rc != want:
            fail(f"{name}: {why}")

    try:
        raw = (repo / "VERSION").read_bytes().decode("utf-8")
        lines = raw.splitlines()
        if len(lines) != 1 or not SEMVER.fullmatch(lines[0]):
            fail(f"VERSION must be one line, MAJOR.MINOR.PATCH, digits only, no v prefix, no leading zeroes; got {raw!r}")
    except Exception as e:  # noqa: BLE001
        fail(f"VERSION is missing or unreadable ({type(e).__name__})")
    return fails


class Target:
    def __init__(self, name, script):
        self.name = name
        self.script = Path(script)
        self.dash, self.bash = find_posix_shells()
        self.windows_usr = None
        if os.name == "nt" and self.dash:
            self.windows_usr = str(Path(self.dash).parent)

    def bad_flag(self):
        return "/force" if self.name == "cmd" else "--force"

    def command(self, script_arg, args, shell=None):
        if self.name == "cmd":
            return ["cmd", "/c", script_arg, *args]
        return [shell or self.dash, script_arg, *args]


def run_target(t: Target):
    fails = []

    def fail(msg):
        fails.append(f"FAIL [{t.name}] {msg}")

    raw = t.script.read_bytes()
    text = raw.decode("utf-8")
    if t.name == "sh":
        first = text.splitlines()[0] if text else ""
        if first != "#!/bin/sh":
            fail(f"first line must be exactly '#!/bin/sh', got {first!r}")
        if not re.search(r"^\s*set\s+-[a-z]*e[a-z]*u|^\s*set\s+-[a-z]*u[a-z]*e", text, re.M):
            fail("the script must run with 'set -eu' near the top")
        for pat, why in BANNED:
            m = re.search(pat, text, re.M)
            if m:
                fail(f"banned construct ({why}): {m.group(0).strip()[:40]!r}")
        if "\r" in text:
            fail("the file has carriage returns (CRLF); use LF line endings")
    else:
        if b"\r\n" not in raw or re.search(rb"(?<!\r)\n", raw):
            fail("setup.cmd must use CRLF line endings throughout")
        if not raw.isascii():
            fail("setup.cmd must be ASCII")

    work = Path(tempfile.mkdtemp(prefix="lab setup test "))

    def fixture(name):
        root = work / name / "lab root"  # a space on purpose
        lab = root / "cf-lab"
        bin_ = work / name / "bin"
        lab.mkdir(parents=True)
        bin_.mkdir(parents=True)
        (lab / t.script.name).write_bytes(raw)  # no VERSION file: setup must not need one
        if t.name == "cmd":
            (bin_ / "git.cmd").write_bytes(STUB_CMD.encode())
            # Decoys that shadow the Windows tools, like GNU find from Git for Windows does: the script must use System32's.
            for tool in ("find", "findstr", "more", "where"):
                (bin_ / f"{tool}.cmd").write_bytes(b"@echo off\r\necho decoy %~n0 was run 1>&2\r\nexit /b 0\r\n")
        else:
            (bin_ / "git").write_text(STUB_SH, encoding="utf-8", newline="\n")
        return root, lab, bin_

    def run(lab, bin_, args=(), shell=None, fail_clone=False, cwd=None, no_stub_git=False, pause=False):
        env = dict(os.environ)
        env["GIT_LOG"] = str(bin_ / "git.log")
        if pause:
            env.pop("LAB_NO_PAUSE", None)
        else:
            env["LAB_NO_PAUSE"] = "1"
        env.pop("STUB_GIT_FAIL", None)
        env.pop("LAB_GIT", None)
        if fail_clone:
            env["STUB_GIT_FAIL"] = "1"
        if t.name == "cmd":
            if no_stub_git:  # no git anywhere on PATH, and no seam; the decoy tools still sit first on PATH
                (bin_ / "git.cmd").unlink()
                env["PATH"] = str(bin_) + os.pathsep + os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
            else:
                env["LAB_GIT"] = f'call "{bin_ / "git.cmd"}"'
                env["PATH"] = str(bin_) + os.pathsep + env.get("PATH", "")
            # ".\" because some environments set NoDefaultCurrentDirectoryInExePath, which stops cmd running ./name
            target = ".\\" + t.script.name if cwd is None else str(lab / t.script.name)
        else:
            extra = [str(bin_)] + ([t.windows_usr] if t.windows_usr else [])
            env["PATH"] = os.pathsep.join(extra + ([] if no_stub_git and not t.windows_usr else [env.get("PATH", "")]))
            if no_stub_git:
                (bin_ / "git").unlink()
                env["PATH"] = os.pathsep.join([str(bin_)] + ([t.windows_usr] if t.windows_usr else [os.pathsep.join(p for p in env["PATH"].split(os.pathsep) if p and not shutil.which("git", path=p))]))
            target = t.script.name if cwd is None else (lab / t.script.name).as_posix()
        p = subprocess.run(t.command(target, list(args), shell), cwd=str(cwd or lab), env=env, capture_output=True, text=True,
                           timeout=120, errors="replace", stdin=subprocess.DEVNULL)
        logf = bin_ / "git.log"
        log = logf.read_text(encoding="utf-8", errors="replace").splitlines() if logf.exists() else []
        return p.returncode, (p.stdout + p.stderr), [l.replace('"', "") for l in log]

    shells = [("default", None)] if t.name == "cmd" else [("dash", t.dash)] + ([("bash", t.bash)] if t.bash else [])
    try:
        for label, shell in shells:
            root, lab, bin_ = fixture(f"happy-{label}")
            rc, out, log = run(lab, bin_, (), shell)
            tag = f"happy path ({label})"
            if rc != 0:
                fail(f"{tag} exited {rc}: {out.strip()[-200:]}")
                continue
            if "decoy" in out:
                fail(f"{tag}: the script ran a find/findstr/more/where from PATH instead of the Windows one in System32")
            if "Setting up Sensei Ewok's CF Lab..." not in out:
                fail(f"{tag}: the opening line \"Setting up Sensei Ewok's CF Lab...\" is missing")
            if "Done. Open cf-lab.code-workspace in this checkout in VS Code." not in out:
                fail(f"{tag}: the closing line 'Done. Open cf-lab.code-workspace in this checkout in VS Code.' is missing")
            clones = [l for l in log if l.startswith("clone ")]
            urls = sorted(c.split()[1] for c in clones)
            if urls != ["https://github.com/senseiewok/" + n for n in CLONES]:
                fail(f"{tag}: wrong clones {clones}")
            order = [c.split()[1].rsplit("/", 1)[1] for c in clones]
            if order != ["cf-skills", "cf-research"]:
                fail(f"{tag}: clone order must be cf-skills then cf-research, got {order}")
            for n in CLONES:
                if not (root / n / ".git").exists():
                    fail(f"{tag}: {n} was not cloned beside cf-lab (a sibling, not inside it)")
            for sub in ("memory", "scratch"):
                if not (root / FILES / sub).is_dir():
                    fail(f"{tag}: {FILES}/{sub} was not created beside cf-lab")
            rd = root / FILES / "README.md"
            if not rd.exists() or rd.read_text(encoding="utf-8").replace("\r\n", "\n") != README:
                fail(f"{tag}: {FILES}/README.md is missing or its text differs from lab-files-readme.txt")
            elif len(README.splitlines()) != 8 or README.splitlines()[0] != FILES:
                fail(f"{tag}: lab-files-readme.txt must be 8 lines and start with '{FILES}'")
            if (root / FILES / "downloads").exists():
                fail(f"{tag}: do not create a downloads folder in {FILES}")
            if (lab / FILES).exists() or any((lab / n).exists() for n in CLONES):
                fail(f"{tag}: something was created inside cf-lab that belongs beside it")
            if list(lab.glob("*.code-workspace")):
                fail(f"{tag}: setup must not generate a workspace file; cf-lab.code-workspace is tracked")

        # an ordinary re-run preserves the README and every file in the Files folder, and clones nothing again
        root, lab, bin_ = fixture("preserve")
        run(lab, bin_)
        (root / FILES / "memory" / "keep.txt").write_text("mine", encoding="utf-8")
        (root / FILES / "README.md").write_text("my own readme", encoding="utf-8")
        rc, out, log = run(lab, bin_)
        if rc != 0:
            fail(f"an ordinary re-run must exit 0 (exit {rc}): {out.strip()[-160:]}")
        if len([l for l in log if l.startswith("clone ")]) != 2:
            fail("a re-run cloned again although both repos were present")
        if (root / FILES / "memory" / "keep.txt").read_text(encoding="utf-8") != "mine":
            fail("a re-run disturbed a file inside the Files folder")
        if (root / FILES / "README.md").read_text(encoding="utf-8") != "my own readme":
            fail("a re-run overwrote an existing README.md in the Files folder")

        # no flags: anything else is a usage error that stops before touching anything
        root, lab, bin_ = fixture("badflag")
        rc, out, log = run(lab, bin_, (t.bad_flag(),))
        if rc != 2 or "usage" not in out.lower():
            fail(f"an unknown argument ({t.bad_flag()}) must exit 2 with a usage line; exit {rc}")
        if log or (root / FILES).exists():
            fail(f"an unknown argument ({t.bad_flag()}) must stop before cloning or creating anything")

        root, lab, bin_ = fixture("notgit")
        (root / "cf-skills").mkdir()
        (root / "cf-skills" / "mine.txt").write_text("keep", encoding="utf-8")
        rc, out, log = run(lab, bin_)
        if rc == 0 or "not a git checkout" not in out or (root / "cf-skills" / "mine.txt").read_text(encoding="utf-8") != "keep":
            fail(f"a non-git 'cf-skills' folder must be refused with 'not a git checkout' and left alone; exit {rc}")

        root, lab, bin_ = fixture("clonefail")
        rc, out, log = run(lab, bin_, fail_clone=True)
        if rc == 0 or "Failed to clone" not in out:
            fail(f"a failed clone must exit non-zero with 'Failed to clone'; exit {rc}")
        if (root / FILES).exists():
            fail("a failed clone must stop before the Files folder is created")

        root, lab, bin_ = fixture("filesisfile")
        (root / FILES).write_text("not a folder", encoding="utf-8")
        rc, out, log = run(lab, bin_)
        if rc == 0 or "is a file" not in out or (root / FILES).read_text(encoding="utf-8") != "not a folder":
            fail(f"a regular file named '{FILES}' must be refused with 'is a file' and left alone; exit {rc}")

        root, lab, bin_ = fixture("elsewhere")
        rc, out, log = run(lab, bin_, cwd=work)
        if rc != 0 or not all((root / n / ".git").exists() for n in CLONES) or not (root / FILES / "memory").is_dir():
            fail(f"running from another folder by absolute path must work; exit {rc}: {out.strip()[-160:]}")

        root, lab, bin_ = fixture("nogit")
        rc, out, log = run(lab, bin_, no_stub_git=True)
        if rc == 0 or "Git is required" not in out:
            fail(f"with no git on PATH the script must exit non-zero with 'Git is required'; exit {rc}: {out.strip()[-120:]}")

        if t.name == "cmd":
            # Double-click behaviour: without LAB_NO_PAUSE or /nopause the window waits (stdin is NUL here, so it returns at once).
            root, lab, bin_ = fixture("pause")
            rc, out, log = run(lab, bin_, pause=True)
            if rc != 0 or "decoy" in out:
                fail(f"the pause check must use the Windows find in System32; exit {rc}: {out.strip()[-160:]}")
            if "Press any key" not in out:
                fail("started with /c and no /nopause the script must pause so a double-click window stays open")
            root, lab, bin_ = fixture("nopause")
            rc, out, log = run(lab, bin_, ("/nopause",), pause=True)
            if rc != 0 or "Press any key" in out or "decoy" in out:
                fail(f"/nopause must be accepted and must skip the pause; exit {rc}: {out.strip()[-160:]}")
    except Exception as e:  # noqa: BLE001  (a script that does nothing must fail, not crash the test)
        fail(f"the checks could not finish: {type(e).__name__}: {str(e)[-160:]}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["sh", "cmd", "all"], default="all")
    ap.add_argument("--script")
    a = ap.parse_args()
    targets = []
    if a.target in ("sh", "all"):
        if find_posix_shells()[0] is None:
            print("skip: no POSIX shell found for setup.sh")
        else:
            targets.append(Target("sh", a.script if (a.script and a.target == "sh") else REPO / "setup.sh"))
    if a.target in ("cmd", "all"):
        if os.name != "nt":
            print("skip: setup.cmd needs Windows")
        else:
            targets.append(Target("cmd", a.script if (a.script and a.target == "cmd") else REPO / "setup.cmd"))
    if not targets:
        print("FAIL no target could run here")
        return 1
    allf = []
    f = check_repo_files()
    allf += f
    print("repo files: " + ("all checks passed" if not f else f"{len(f)} failure(s)"))
    for t in targets:
        f = run_target(t)
        allf += f
        print(f"{t.name}: " + ("all checks passed" if not f else f"{len(f)} failure(s)"))
    for f in allf:
        print(f)
    print("VERIFIED" if not allf else f"{len(allf)} failure(s)")
    return 1 if allf else 0


if __name__ == "__main__":
    sys.exit(main())
