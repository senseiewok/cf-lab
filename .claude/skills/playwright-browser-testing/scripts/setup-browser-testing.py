#!/usr/bin/env python3
"""Optional, opt-in setup for browser testing in Sensei Ewok's CF Lab.

Creates a Python virtual environment OUTSIDE every repository, installs one pinned version of
Playwright for Python from PyPI into it, and then either uses a Microsoft Edge or Google Chrome
that is already installed (no browser download) or downloads Playwright's Chromium build. It
finishes by running the observation script's self-test, which uses only a local page.

It is never run by setup.cmd or setup.sh. Before it changes anything it prints what it will
download and from where, and waits for you to type yes (or takes --yes). --dry-run prints the
same plan and touches nothing.

Usage:
    python setup-browser-testing.py --dry-run          show the plan; download, create or change nothing
    python setup-browser-testing.py                    show the plan, ask, then do it
    python setup-browser-testing.py --yes              do it without asking
    options: --venv PATH   --browser {auto,msedge,chrome,chromium}

Exit codes: 0 done (or dry run), 1 a check or a step failed, 2 usage error, 3 you did not type yes.
Standard library only; the installs go through pip and Playwright's own installer.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

PLAYWRIGHT_VERSION = "1.63.0"  # PyPI: released 2026-09-15, requires Python >=3.10; see the skill's SKILL.md
MIN_PYTHON = (3, 10)
PYPI = "https://pypi.org"
BROWSER_CDN = "https://cdn.playwright.dev"
HERE = Path(__file__).resolve().parent
OBSERVE = HERE / "observe-page.py"
CHANNEL_NAMES = {"msedge": "Microsoft Edge", "chrome": "Google Chrome"}
EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_DECLINED = 0, 1, 2, 3


def default_venv(env=None, platform=None) -> Path:
    """Windows: %LOCALAPPDATA%\\lab-playwright. Elsewhere: $XDG_DATA_HOME (or ~/.local/share)/lab-playwright."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32" and env.get("LOCALAPPDATA"):
        return Path(env["LOCALAPPDATA"]) / "lab-playwright"
    base = env.get("XDG_DATA_HOME") or str(Path(env.get("HOME") or Path.home()) / ".local" / "share")
    return Path(base) / "lab-playwright"


def browser_candidates(channel: str, env=None, platform=None) -> list:
    """The stable-channel install paths Playwright itself looks in, for this platform."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if platform == "win32":
        rel = {"msedge": ("Microsoft", "Edge", "Application", "msedge.exe"),
               "chrome": ("Google", "Chrome", "Application", "chrome.exe")}[channel]
        roots = [env.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        return [str(Path(r, *rel)) for r in roots if r]
    if platform == "darwin":
        return {"msedge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
                "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]}[channel]
    return {"msedge": ["/opt/microsoft/msedge/msedge"], "chrome": ["/opt/google/chrome/chrome"]}[channel]


def find_browser(channel: str, env=None, platform=None, exists=os.path.isfile):
    for path in browser_candidates(channel, env, platform):
        if exists(path):
            return path
    return None


def choose_browser(requested: str, env=None, platform=None, exists=os.path.isfile):
    """Return (channel or 'chromium', path or None, error or None)."""
    if requested == "chromium":
        return "chromium", None, None
    order = ["msedge", "chrome"] if requested == "auto" else [requested]
    for ch in order:
        path = find_browser(ch, env, platform, exists)
        if path:
            return ch, path, None
    if requested == "auto":
        return "chromium", None, None
    return requested, None, (f"{CHANNEL_NAMES[requested]} was not found in its usual install location. "
                             "Install it, or use --browser chromium to download Playwright's Chromium instead.")


def python_ok(version_info=None) -> bool:
    return tuple((version_info or sys.version_info)[:2]) >= MIN_PYTHON


def venv_python(venv: Path, platform=None) -> Path:
    platform = sys.platform if platform is None else platform
    return venv / ("Scripts/python.exe" if platform == "win32" else "bin/python")


def inside_repository(path: Path):
    """The nearest folder at or above path that holds a .git entry, or None."""
    p = path.resolve()
    for candidate in (p, *p.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def check_venv(venv: Path):
    """Return (state, error): state is 'create' or 'reuse'."""
    repo = inside_repository(venv)
    if repo is not None:
        return None, (f"{venv} is inside the git repository at {repo}. Put the virtual environment outside "
                      "every repository so it is never committed; pass --venv PATH or use the default.")
    if venv.exists():
        if not venv.is_dir():
            return None, f"{venv} exists and is a file; nothing was changed."
        if (venv / "pyvenv.cfg").is_file():
            return "reuse", None
        if any(venv.iterdir()):
            return None, f"{venv} exists, is not empty and is not a virtual environment; nothing was changed."
    return "create", None


def plan_steps(venv: Path, state: str, channel: str, browser_path, platform=None):
    """List of (description, command or None). The commands are exactly what a real run executes."""
    vpy = str(venv_python(venv, platform))
    steps = []
    if state == "create":
        steps.append((f"Create a virtual environment at {venv} (python -m venv; downloads nothing).",
                      [sys.executable, "-m", "venv", str(venv)]))
    else:
        steps.append((f"Reuse the existing virtual environment at {venv}.", None))
    steps.append((f"Install playwright=={PLAYWRIGHT_VERSION} and the packages it needs (pyee, greenlet, "
                  f"typing-extensions) from the Python Package Index, {PYPI}. The Playwright wheel is about "
                  "35 to 50 MB; pip downloads nothing that is already installed.",
                  [vpy, "-m", "pip", "install", "--disable-pip-version-check", f"playwright=={PLAYWRIGHT_VERSION}"]))
    if channel == "chromium":
        steps.append((f"Print Playwright's own list of browser downloads and their exact URLs ({BROWSER_CDN}), "
                      "without downloading.", [vpy, "-m", "playwright", "install", "--dry-run", "chromium"]))
        steps.append((f"Download Chromium and its headless shell from {BROWSER_CDN} into Playwright's own cache "
                      "folder (several hundred MB on disk).", [vpy, "-m", "playwright", "install", "chromium"]))
        selftest = [vpy, str(OBSERVE), "--self-test"]
    else:
        steps.append((f"Use {CHANNEL_NAMES[channel]} already installed at {browser_path} (channel {channel}); "
                      "no browser download.", None))
        selftest = [vpy, str(OBSERVE), "--self-test", "--channel", channel]
    steps.append(("Run the observation script's self-test (a page served on this machine; no external site).",
                  selftest))
    return steps


def format_command(cmd) -> str:
    return " ".join(f'"{c}"' if " " in c else c for c in cmd)


def run_step(cmd) -> int:
    """Run one command, its output going straight to the terminal. Replaced in the tests."""
    return subprocess.run(cmd).returncode


def ask(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="setup-browser-testing.py",
        description="Optional: install a pinned Playwright for Python into its own virtual environment.")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; download, create or change nothing")
    ap.add_argument("--yes", action="store_true", help="do not ask; proceed after printing the plan")
    ap.add_argument("--venv", type=Path, help="virtual environment folder (default: %(default)s)",
                    default=default_venv())
    ap.add_argument("--browser", choices=["auto", "msedge", "chrome", "chromium"], default="auto",
                    help="auto (default): an installed Edge, else an installed Chrome, else download Chromium")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    venv = a.venv.expanduser()
    print("Optional browser testing for Sensei Ewok's CF Lab")
    print("This is not part of setup.cmd or setup.sh. It installs Playwright for Python into its own")
    print("virtual environment, outside every repository.")
    print()

    if not python_ok():
        print(f"error: Playwright {PLAYWRIGHT_VERSION} needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer; "
              f"this is {sys.version_info[0]}.{sys.version_info[1]}. Nothing was changed.")
        return EXIT_FAIL
    state, err = check_venv(venv)
    if err:
        print("error: " + err)
        return EXIT_FAIL
    channel, path, err = choose_browser(a.browser)
    if err:
        print("error: " + err)
        return EXIT_FAIL

    steps = plan_steps(venv, state, channel, path)
    print("Plan:")
    for i, (text, cmd) in enumerate(steps, 1):
        print(f"  {i}. {text}")
        if cmd:
            print(f"     {format_command(cmd)}")
    print()

    if a.dry_run:
        print("Dry run: nothing was downloaded, created or changed.")
        return EXIT_OK
    if not a.yes:
        answer = ask("Type yes to download and install as shown above: ")
        if answer.strip().lower() != "yes":
            print("Stopped. Nothing was downloaded, created or changed.")
            return EXIT_DECLINED

    for i, (text, cmd) in enumerate(steps, 1):
        if not cmd:
            continue
        print(f"-- step {i}: {format_command(cmd)}", flush=True)
        rc = run_step(cmd)
        if rc != 0:
            print(f"error: step {i} failed with exit code {rc}. Steps before it were kept; run this script again "
                  "after fixing the cause, and it reuses the virtual environment.")
            return EXIT_FAIL

    print()
    print(f"Done. Playwright {PLAYWRIGHT_VERSION} is installed in {venv}.")
    observe = [str(venv_python(venv)), str(OBSERVE), "https://example.com"] + (
        [] if channel == "chromium" else ["--channel", channel])
    print("Observe a page with: " + format_command(observe))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
