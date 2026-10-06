#!/usr/bin/env python3
"""verify-in-copy.py — judge a candidate file inside a temporary copy of a repository."""
import argparse
import os
import py_compile
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def ignore_func(directory, names):
    skip = {".git", "__pycache__", "node_modules", ".loop-logs"}
    ignored = set()
    for n in names:
        if n in skip or n.endswith(".pyc"):
            ignored.add(n)
    return ignored


def make_link(name, path, base):
    target = Path(path).resolve()
    link_path = base / name
    try:
        os.symlink(str(target), str(link_path))
        return
    except OSError:
        pass
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target)],
                check=True, capture_output=True, timeout=60
            )
            return
        except Exception:
            pass
    shutil.copytree(str(target), str(link_path))


def run_generator(cmd_text, workdir, python_exe):
    parts = shlex.split(cmd_text)
    if not parts:
        return None
    if parts[0] == "python":
        parts[0] = python_exe
    proc = subprocess.run(parts, cwd=str(workdir), capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        output = (proc.stderr or proc.stdout or "").strip()
        lines = [l for l in output.splitlines() if l.strip()]
        last = lines[-1] if lines else ""
        return f'FAIL generator "{cmd_text}" exited {proc.returncode}: {last[:240]}'
    return None


def extract_test_failures(output, module):
    fails = []
    m = re.search(r"Ran (\d+) test", output)
    if not m:
        lines = [l for l in output.splitlines() if l.strip()]
        last = lines[-1] if lines else ""
        return 0, [f"FAIL {module}: the tests did not run: {last[:200]}"]

    total = int(m.group(1))
    lines = output.splitlines()
    blocks = []
    current = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^=+$", stripped) and len(stripped) >= 20:
            if current:
                blocks.append(current)
                current = []
        else:
            current.append(line)
    if current:
        blocks.append(current)

    for block in blocks:
        name = None
        for line in block:
            hm = re.match(r"^(FAIL|ERROR):\s*(.+?)\s*\(", line)
            if hm:
                nm = re.match(r"^(?:FAIL|ERROR):\s*([^(\n]+)", line)
                if nm:
                    name = nm.group(1).strip()
                break
        if name is None:
            continue
        detail = ""
        for line in reversed(block):
            ls = line.strip()
            if re.match(r"^(AssertionError|.*Error|.*Exception)", ls):
                detail = ls[:240]
                break
        name_short = name[:90]
        fails.append(f"FAIL {name_short}: {detail}")

    return total, fails


def main():
    parser = argparse.ArgumentParser(description="Judge a candidate file inside a temporary copy of a repository.")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--generator", action="append", default=[])
    parser.add_argument("--tests", action="append", default=[])
    parser.add_argument("--link", action="append", default=[])
    parser.add_argument("--python", default=None)
    parser.add_argument("--max-lines", type=int, default=12)
    args = parser.parse_args()

    repo = Path(args.repo)
    candidate = Path(args.candidate)
    target = args.target
    python_exe = args.python or sys.executable
    max_lines = args.max_lines

    if not repo.is_dir():
        print(f"ERROR: repository not found: {repo}")
        sys.exit(2)
    if not candidate.is_file():
        print(f"ERROR: candidate file not found: {candidate}")
        sys.exit(2)

    try:
        cand_text = candidate.read_text(encoding="utf-8")
    except Exception as e:
        print(f"ERROR: cannot read candidate: {e}")
        sys.exit(2)

    tmp_dir = tempfile.mkdtemp(prefix="verify-in-copy-")
    repo_basename = repo.name
    copy_path = Path(tmp_dir) / repo_basename

    try:
        shutil.copytree(str(repo), str(copy_path), ignore=ignore_func, symlinks=False)

        for link_spec in args.link:
            if "=" not in link_spec:
                continue
            name, path = link_spec.split("=", 1)
            make_link(name.strip(), path.strip(), copy_path)

        target_path = copy_path / target
        target_path.parent.mkdir(parents=True, exist_ok=True)
        normalized = cand_text.replace("\r\n", "\n").replace("\r", "\n")
        target_path.write_text(normalized, encoding="utf-8", newline="\n")

        failure_lines = []

        if normalized.strip() == "":
            failure_lines.append("FAIL the candidate is empty")
            print("\n".join(failure_lines))
            print("0 / 1 passed")
            sys.exit(1)

        if target.endswith(".py"):
            try:
                py_compile.compile(str(target_path), doraise=True)
            except py_compile.PyCompileError as e:
                err_lines = [l for l in str(e).splitlines() if l.strip()]
                last_err = err_lines[-1] if err_lines else str(e)
                failure_lines.append(f"FAIL does not compile: {last_err}")
                print("\n".join(failure_lines))
                print("0 / 1 passed")
                sys.exit(1)

        for gen_cmd in args.generator:
            fail = run_generator(gen_cmd, copy_path, python_exe)
            if fail:
                failure_lines.append(fail)

        total_tests_run = 0
        for module in args.tests:
            cmd = [python_exe, "-W", "ignore", "-m", "unittest", module]
            proc = subprocess.run(
                cmd, cwd=str(copy_path), capture_output=True, text=True, timeout=300
            )
            output = (proc.stdout or "") + "\n" + (proc.stderr or "")
            total, fails = extract_test_failures(output, module)
            if total > 0:
                total_tests_run += total
            failure_lines.extend(fails)

        seen = {}
        order = []
        for fl in failure_lines:
            if fl not in seen:
                seen[fl] = 1
                order.append(fl)
            else:
                seen[fl] += 1

        distinct_count = len(order)
        print_count = min(distinct_count, max_lines)
        for i in range(print_count):
            line = order[i]
            count = seen[line]
            if count > 1:
                line = f"{line}  (x{count})"
            print(line)

        if distinct_count > max_lines:
            omitted = distinct_count - max_lines
            print(f"({omitted} more distinct failures omitted)")

        T = max(total_tests_run, 1)
        P = max(T - len(failure_lines), 0)
        print(f"{P} / {T} passed")

        if failure_lines:
            sys.exit(1)
        else:
            sys.exit(0)

    finally:
        # Never let the cleanup follow a link into a real sibling folder: remove the links themselves first.
        for link_spec in args.link:
            if "=" in link_spec:
                lp = copy_path / link_spec.split("=", 1)[0].strip()
                try:
                    if lp.is_symlink() or getattr(os.path, "isjunction", lambda x: False)(str(lp)):
                        os.rmdir(lp) if os.name == "nt" else os.unlink(lp)
                except OSError:
                    pass
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
