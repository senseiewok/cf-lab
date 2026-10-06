#!/usr/bin/env python3
"""filter-review-findings.py -- filter review findings by reproducing their failing inputs.

Purpose
-------
This tool takes review findings (produced by a small local model) and a candidate
Python script, runs each finding's failing input against the candidate in a fresh
temporary copy of the candidate folder, and labels every finding by what happened.

What it decides
---------------
For each finding it answers ONE narrow question: "does this specific input produce
the described behaviour (exit code / output regex / hang) when run against the
candidate?"  That is all.

What it does NOT decide
-----------------------
It does NOT decide whether the quoted spec sentence actually requires something
different from what the script did, whether a finding is correct, wrong, important,
or worth acting on.  Judging the spec is the controller's job.  This tool is a
filter, never a judge: it must not accept, rank, score or confirm any finding.

Why: in the 2026-10-06 local-reviewer evaluation (board T-0089), 14 wrong claims came from 8 runs. Running the given
input removed 5 (the failure did not occur); 8 reproduced exactly and were still wrong about the spec; 1 had no input.
So reproduction narrows the list and the controller still reads each quoted spec sentence. A finding with no input
is a lead to read, not a finding.

How to use: ask the worker for findings in the format below (JSON, inputs as data, never a command line), run this
tool, read the `needs spec check` rows against their quoted sentences, and treat the other labels as leads at most.
Tests: scripts/test_filter_review_findings.py (fixtures in cases/review-findings-filter/).

Finding format (one short example)
----------------------------------
    {"id": "A3-2", "claim": "text", "spec_quote": "the spec sentence the finding relies on",
     "failing_input": {"stdin": "optional text",
                       "files": {"site/index.html": "<html>...</html>"},
                       "args": ["{input_dir}/site", "--json"],
                       "expect": {"exit_code": 0, "output_regex": "SEO026",
                                  "output_not_regex": "SEO030"}}}

The four labels
---------------
    needs spec check   the input produced exactly the described behaviour; the
                       controller must read the quoted spec sentence to decide.
    did not reproduce  the input did NOT produce the described behaviour, or the
                       sandbox itself failed, or the output cap was exceeded.
    timed out          the run exceeded --timeout and a hang was not expected.
    invalid finding    the finding could not be validated (bad shape / unsafe input).

Safety limits and their honest limits
-------------------------------------
- Finding inputs are DATA only: text written to files, text sent to stdin, argument
  strings.  This tool never runs, imports, evals or execs anything a finding supplies.
- The candidate is run in a fresh temporary copy; symlinks, .git, __pycache__,
  node_modules, *.pyc and the like are skipped when copying.
- A boot wrapper monkey-patches Python's socket module so that network calls raise
  OSError.  This covers PYTHON candidates only; it is best-effort, not an operating
  system sandbox.  Files outside the copy are NOT blocked by this tool.

Exit codes
----------
    0   the run completed (whatever the labels)
    2   usage error (bad CLI args, unreadable/invalid findings file, bad candidate)

Usage
-----
    python filter-review-findings.py FINDINGS CANDIDATE [--out RESULT.json] \\
        [--timeout SECONDS] [--output-cap BYTES]
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BOOT_SOURCE = '''\
import os
import runpy
import socket
import sys


def _no_network(*args, **kwargs):
    raise OSError("network access is disabled by filter-review-findings")


for _name in ("connect", "connect_ex", "sendto"):
    setattr(socket.socket, _name, _no_network)
for _name in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr"):
    setattr(socket, _name, _no_network)
_target = os.path.abspath(sys.argv[1])
sys.argv = sys.argv[1:]
sys.path[0] = os.path.dirname(_target)
runpy.run_path(_target, run_name="__main__")
'''

LABEL_NEEDS_SPEC = "needs spec check"
LABEL_DID_NOT_REPRODUCE = "did not reproduce"
LABEL_TIMED_OUT = "timed out"
LABEL_INVALID = "invalid finding"

CODE_BLOCKING_KEYS = {
    "command", "cmd", "code", "script", "shell", "exec", "run", "python",
    "eval", "bash", "powershell", "sh", "argv", "executable", "program",
}

EXECUTABLE_EXTENSIONS = {
    ".py", ".pyw", ".pyc", ".pyo", ".pyd", ".pth", ".so", ".dll", ".exe",
    ".bat", ".cmd", ".com", ".ps1", ".sh", ".vbs", ".msi", ".scr", ".lnk",
}

SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".loop-logs"}

MAX_FINDINGS = 200
MAX_FILES = 50
MAX_TOTAL_CONTENT = 1_000_000
MAX_STDIN = 1_000_000
MAX_ARGS = 20
MAX_ARG_LEN = 2000
MAX_REGEX_LEN = 1000
MAX_CANDIDATE_FILES = 2000
MAX_CANDIDATE_BYTES = 50 * 1024 * 1024


# ---------------------------------------------------------------------------
# Hidden match worker mode (checked before argparse)
# ---------------------------------------------------------------------------

def _match_worker():
    """Read {"pattern": ..., "text": ...} from stdin, print 1 or 0, exit 0."""
    try:
        raw = sys.stdin.buffer.read()
        obj = json.loads(raw.decode("utf-8", errors="replace"))
        pattern = obj["pattern"]
        text = obj["text"]
        if re.search(pattern, text, re.MULTILINE):
            sys.stdout.write("1")
        else:
            sys.stdout.write("0")
    except Exception:
        sys.stdout.write("0")
        sys.exit(1)
    sys.exit(0)


def _run_regex_match(pattern, text, timeout):
    """Run the match in a child process. Return True/False or raise RuntimeError."""
    payload = json.dumps({"pattern": pattern, "text": text}).encode("utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, "-E", "-s", os.path.abspath(__file__), "--match-worker"],
            input=payload,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("regex took too long or failed (possible catastrophic backtracking)")
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        raise RuntimeError("regex took too long or failed (possible catastrophic backtracking)")
    return out == "1"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _is_blank(s):
    return s is None or (isinstance(s, str) and s.strip() == "")


def _has_code_key(obj):
    if not isinstance(obj, dict):
        return False
    for k in obj:
        if isinstance(k, str) and k.lower() in CODE_BLOCKING_KEYS:
            return True
    return False


def _file_name_valid(name):
    """Return None if valid, else a reason string."""
    if not isinstance(name, str) or name == "":
        return "invalid file name"
    n = name.replace("\\", "/")
    if "\x00" in n:
        return "file name contains NUL"
    if ":" in n:
        return "file name contains ':'"
    if n.startswith("/"):
        return "file name starts with '/'"
    parts = n.split("/")
    for p in parts:
        if p == "" or p == "." or p == "..":
            return "invalid file name part: %r" % (p,)
    ext = os.path.splitext(n)[1].lower()
    if ext in EXECUTABLE_EXTENSIONS:
        return "asks to run code: executable file name"
    return None


def _arg_reaches_outside(arg):
    a = arg.replace("\\", "/")
    if a.startswith("/") or a.startswith("\\\\"):
        return True
    if re.match(r"^[A-Za-z]:", a):
        return True
    for p in a.split("/"):
        if p == "..":
            return True
    return False


def _validate_finding(f, position, seen_ids):
    """Return (result_entry_dict, finding_or_None)."""
    entry = {
        "id": "#%d" % position,
        "label": LABEL_INVALID,
        "reason": "",
        "claim": "",
        "spec_quote": "",
        "observed": None,
        "next_step": None,
    }

    def fail(reason):
        entry["reason"] = reason
        return entry, None

    # 1. must be an object
    if not isinstance(f, dict):
        return fail("finding is not an object")

    # 2. id
    fid = f.get("id")
    if isinstance(fid, bool) or not (isinstance(fid, str) and fid.strip() != "") and not (isinstance(fid, int) and not isinstance(fid, bool)):
        return fail("missing id")
    if isinstance(fid, int):
        fid = str(fid)
    else:
        fid = fid.strip()
    entry["id"] = fid
    if fid in seen_ids:
        return fail("duplicate id")
    seen_ids.add(fid)

    # 3. claim and spec_quote
    claim = f.get("claim")
    if not (isinstance(claim, str) and claim.strip() != ""):
        entry["claim"] = ""
        return fail("missing claim")
    entry["claim"] = claim

    sq = f.get("spec_quote")
    if not (isinstance(sq, str) and sq.strip() != ""):
        entry["spec_quote"] = ""
        return fail("missing spec_quote")
    entry["spec_quote"] = sq

    # 4. code-blocking keys at top level or in failing_input
    if _has_code_key(f):
        return fail("asks to run code: inputs are data only")
    fi = f.get("failing_input")
    if isinstance(fi, dict) and _has_code_key(fi):
        return fail("asks to run code: inputs are data only")

    # 5. failing_input present
    if fi is None or (isinstance(fi, dict) and len(fi) == 0):
        return fail("no failing input: this is a lead to read, not a finding")
    if not isinstance(fi, dict):
        return fail("failing_input is not an object")

    # 6. allowed keys
    allowed = {"stdin", "files", "args", "expect"}
    for k in fi:
        if k not in allowed:
            return fail("unknown key in failing_input: %s" % (k,))

    # 7. stdin
    total_content = 0
    stdin_val = fi.get("stdin")
    if stdin_val is not None:
        if not isinstance(stdin_val, str):
            return fail("stdin must be a string")
        if len(stdin_val) > MAX_STDIN:
            return fail("stdin too long (max %d chars)" % MAX_STDIN)
        total_content += len(stdin_val)

    # 8. files
    files_val = fi.get("files")
    file_map = {}
    if files_val is not None:
        if not isinstance(files_val, dict):
            return fail("files must be an object")
        if len(files_val) > MAX_FILES:
            return fail("too many files (max %d)" % MAX_FILES)
        for fname, fcontent in files_val.items():
            r = _file_name_valid(fname)
            if r is not None:
                return fail(r)
            if not isinstance(fcontent, str):
                return fail("file content must be a string: %s" % (fname,))
            total_content += len(fcontent)
            file_map[fname.replace("\\", "/")] = fcontent
        if total_content > MAX_TOTAL_CONTENT:
            return fail("total content too large (max %d chars)" % MAX_TOTAL_CONTENT)

    # 9. args
    args_val = fi.get("args")
    args_list = []
    if args_val is not None:
        if not isinstance(args_val, list):
            return fail("args must be a list")
        if len(args_val) > MAX_ARGS:
            return fail("too many args (max %d)" % MAX_ARGS)
        for a in args_val:
            if not isinstance(a, str):
                return fail("each arg must be a string")
            if len(a) > MAX_ARG_LEN:
                return fail("arg too long (max %d chars)" % MAX_ARG_LEN)
            if "\x00" in a:
                return fail("arg contains NUL")
            for s in [a]:
                if "=" in a:
                    s2 = a.split("=", 1)[1]
                    if _arg_reaches_outside(s2):
                        return fail("argument reaches outside the input folder")
            if _arg_reaches_outside(a):
                return fail("argument reaches outside the input folder")
            args_list.append(a)

    # 10. expect
    exp = fi.get("expect")
    if exp is None:
        return fail("missing expect")
    if not isinstance(exp, dict):
        return fail("expect must be an object")
    if len(exp) == 0:
        return fail("empty expect")

    allowed_exp = {"exit_code", "output_regex", "output_not_regex", "hangs"}
    for k in exp:
        if k not in allowed_exp:
            return fail("unknown key in expect: %s" % (k,))

    if "hangs" in exp:
        if exp["hangs"] is not True:
            return fail("hangs must be true")
        if len(exp) != 1:
            return fail("when hangs is set it must be the only key")

    exit_code = None
    output_regex = None
    output_not_regex = None
    if "exit_code" in exp:
        ec = exp["exit_code"]
        if isinstance(ec, bool) or not isinstance(ec, int):
            return fail("bad exit_code: must be an int (not bool)")
        exit_code = ec
    if "output_regex" in exp:
        pr = exp["output_regex"]
        if not (isinstance(pr, str) and pr.strip() != "") or len(pr) > MAX_REGEX_LEN:
            return fail("bad regex")
        try:
            re.compile(pr)
        except re.error:
            return fail("bad regex")
        output_regex = pr
    if "output_not_regex" in exp:
        pn = exp["output_not_regex"]
        if not (isinstance(pn, str) and pn.strip() != "") or len(pn) > MAX_REGEX_LEN:
            return fail("bad regex")
        try:
            re.compile(pn)
        except re.error:
            return fail("bad regex")
        output_not_regex = pn

    finding_norm = {
        "id": fid,
        "claim": claim,
        "spec_quote": sq,
        "failing_input": {
            "stdin": stdin_val if isinstance(stdin_val, str) else None,
            "files": file_map,
            "args": args_list,
            "expect": exp,
        },
    }
    return entry, finding_norm


# ---------------------------------------------------------------------------
# Candidate folder helpers
# ---------------------------------------------------------------------------

def _count_candidate(candidate_folder):
    file_count = 0
    byte_count = 0
    for dirpath, dirnames, filenames in os.walk(candidate_folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            if fn.endswith(".pyc"):
                continue
            file_count += 1
            try:
                byte_count += os.path.getsize(full)
            except OSError:
                pass
    return file_count, byte_count


def _copy_candidate(src_folder, dst_folder):
    for dirpath, dirnames, filenames in os.walk(src_folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        rel_dir = os.path.relpath(dirpath, src_folder)
        dst_dir = os.path.join(dst_folder, rel_dir) if rel_dir != "." else dst_folder
        os.makedirs(dst_dir, exist_ok=True)
        for fn in filenames:
            full_src = os.path.join(dirpath, fn)
            if os.path.islink(full_src):
                continue
            if fn.endswith(".pyc"):
                continue
            dst_file = os.path.join(dst_dir, fn)
            shutil.copy2(full_src, dst_file)


# ---------------------------------------------------------------------------
# Running one finding
# ---------------------------------------------------------------------------

def _kill_process_tree(proc, pid):
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
            )
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _run_finding(finding, candidate_path, timeout, output_cap):
    """Run one valid finding. Returns (observed_dict, error_reason_or_None)."""
    fi = finding["failing_input"]
    stdin_text = fi.get("stdin") or ""
    file_map = fi.get("files") or {}
    args_list = fi.get("args") or []

    root = tempfile.mkdtemp(prefix="review-filter-")
    proc = None
    reader_threads = []
    try:
        copy_dir = os.path.join(root, "copy")
        input_dir = os.path.join(root, "input")
        home_dir = os.path.join(root, "home")
        os.makedirs(copy_dir, exist_ok=True)
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(home_dir, exist_ok=True)

        candidate_folder = os.path.dirname(os.path.abspath(candidate_path))
        try:
            _copy_candidate(candidate_folder, copy_dir)
        except Exception as e:
            return None, "sandbox error: cannot copy candidate: %s" % (e,)

        rel_candidate = os.path.relpath(os.path.abspath(candidate_path), candidate_folder)
        candidate_in_copy = os.path.join(copy_dir, rel_candidate)
        if not os.path.isfile(candidate_in_copy):
            return None, "sandbox error: candidate not found in copy"

        for fname, fcontent in file_map.items():
            dest = os.path.join(input_dir, fname)
            d = os.path.dirname(dest)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(dest, "w", encoding="utf-8", newline="") as fh:
                fh.write(fcontent)

        input_dir_str = input_dir.replace("\\", "/") if sys.platform == "win32" else input_dir
        resolved_args = []
        for a in args_list:
            resolved_args.append(a.replace("{input_dir}", input_dir_str))

        boot_path = os.path.join(root, "boot.py")
        with open(boot_path, "w", encoding="utf-8") as fh:
            fh.write(BOOT_SOURCE)

        env = {}
        for var in ("HOME", "USERPROFILE", "TMP", "TEMP", "TMPDIR"):
            env[var] = home_dir
        exe_folder = os.path.dirname(os.path.abspath(sys.executable))
        env["PATH"] = exe_folder
        if "SYSTEMROOT" in os.environ:
            env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        env["LANG"] = "C.UTF-8"
        env["NO_COLOR"] = "1"

        argv = [sys.executable, "-E", "-s", "-X", "utf8", boot_path, candidate_in_copy] + resolved_args

        byte_counter = {"n": 0}
        capped_flag = {"v": False}
        stdout_chunks = []
        stderr_chunks = []
        lock = threading.Lock()

        def _reader(stream, chunks_list):
            try:
                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    with lock:
                        byte_counter["n"] += len(chunk)
                        if capped_flag["v"]:
                            continue
                        if byte_counter["n"] > output_cap:
                            capped_flag["v"] = True
                            total = b"".join(chunks_list)
                            remaining = output_cap - len(total)
                            if remaining > 0:
                                chunks_list.append(chunk[:remaining])
                            break
                        chunks_list.append(chunk)
            except OSError:
                pass

        kwargs = dict(
            cwd=input_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        if sys.platform != "win32":
            kwargs["start_new_session"] = True

        try:
            proc = subprocess.Popen(argv, **kwargs)
        except Exception as e:
            return None, "sandbox error: cannot start candidate: %s" % (e,)

        def _writer():
            try:
                if proc.stdin:
                    data = stdin_text.encode("utf-8")
                    if data:
                        proc.stdin.write(data)
                    proc.stdin.close()
            except OSError:
                pass

        writer_t = threading.Thread(target=_writer, daemon=True)
        writer_t.start()

        out_t = threading.Thread(target=_reader, args=(proc.stdout, stdout_chunks), daemon=True)
        err_t = threading.Thread(target=_reader, args=(proc.stderr, stderr_chunks), daemon=True)
        out_t.start()
        err_t.start()
        reader_threads = [out_t, err_t]

        start = time.monotonic()
        timed_out = False
        while True:
            if capped_flag["v"]:
                break
            elapsed = time.monotonic() - start
            if elapsed > timeout:
                timed_out = True
                break
            try:
                ret = proc.poll()
                if ret is not None:
                    out_t.join(timeout=1.0)
                    err_t.join(timeout=1.0)
                    break
            except Exception:
                pass
            time.sleep(0.02)

        if timed_out or capped_flag["v"]:
            _kill_process_tree(proc, proc.pid)
            for t in reader_threads:
                t.join(timeout=2.0)

        for t in reader_threads:
            t.join(timeout=2.0)

        exit_code = None
        if not timed_out and not capped_flag["v"]:
            try:
                exit_code = proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                _kill_process_tree(proc, proc.pid)
                for t in reader_threads:
                    t.join(timeout=2.0)
        else:
            try:
                proc.wait(timeout=1.0)  # reap it; the code of a killed run says nothing, so exit_code stays None
            except Exception:
                pass

        seconds = round(time.monotonic() - start, 3)

        stdout_bytes = b"".join(stdout_chunks)[:output_cap]
        stderr_bytes = b"".join(stderr_chunks)[:output_cap]
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        observed = {
            "exit_code": exit_code,
            "timed_out": timed_out,
            "output_capped": capped_flag["v"],
            "stdout": stdout_text[:2000],
            "stderr": stderr_text[:2000],
            "seconds": seconds,
            # The complete captured text (up to the cap) is what the regexes see; main() removes this key before the result is written.
            "_full": (stdout_text, stderr_text),
        }
        return observed, None

    finally:
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Label decision
# ---------------------------------------------------------------------------

def _decide_label(finding, observed, full, timeout, output_cap):
    """Return (label, reason, next_step)."""
    exp = finding["failing_input"]["expect"]
    exit_code = observed["exit_code"]
    timed_out = observed["timed_out"]
    capped = observed["output_capped"]
    stdout_text, stderr_text = full
    text = stdout_text + "\n" + stderr_text

    crashed = (exit_code is not None and exit_code != 0 and
               "Traceback (most recent call last)" in stderr_text)

    # Rule 1: timed out
    if timed_out:
        if exp.get("hangs") is True:
            return (LABEL_NEEDS_SPEC,
                    "reproduced: the candidate did not finish within %s s" % timeout,
                    _next_step())
        return (LABEL_TIMED_OUT,
                "the candidate did not finish within %s s" % timeout,
                None)

    # Rule 2: hangs expected but finished
    if exp.get("hangs") is True:
        return (LABEL_DID_NOT_REPRODUCE,
                "the candidate exited; it did not hang",
                None)

    # Rule 3: capped
    if capped:
        return (LABEL_DID_NOT_REPRODUCE,
                "output cap exceeded (%d bytes): the run was stopped; raise --output-cap to test again" % output_cap,
                None)

    # Rule 4/5: evaluate conditions
    held = []
    failed = []

    if "exit_code" in exp:
        expected_ec = exp["exit_code"]
        if exit_code == expected_ec:
            held.append("exit code %d" % expected_ec)
        else:
            failed.append("exit code %s, expected %d" % (exit_code, expected_ec))

    if "output_regex" in exp:
        pr = exp["output_regex"]
        try:
            matched = _run_regex_match(pr, text, timeout)
        except RuntimeError as e:
            return (LABEL_INVALID, str(e), None)
        if matched:
            held.append("output matches /%s/" % pr)
        else:
            failed.append("output does not match /%s/" % pr)

    if "output_not_regex" in exp:
        pn = exp["output_not_regex"]
        if crashed:
            # Per spec: if crashed and output_not_regex is given, that condition
            # counts as failed: "the candidate crashed, so an absence proves nothing"
            failed.append("the candidate crashed, so an absence proves nothing")
        else:
            try:
                matched = _run_regex_match(pn, text, timeout)
            except RuntimeError as e:
                return (LABEL_INVALID, str(e), None)
            if not matched:
                held.append("output does not match /%s/" % pn)
            else:
                failed.append("output matches /%s/ (should not)" % pn)

    crash_note = "; the candidate crashed with an uncaught exception" if crashed else ""

    if failed:
        reason = "; ".join(failed) + crash_note
        return (LABEL_DID_NOT_REPRODUCE, reason, None)
    else:
        reason = "reproduced: " + "; ".join(held) + crash_note
        return (LABEL_NEEDS_SPEC, reason, _next_step())


def _next_step():
    return ("Controller: read the quoted spec sentence and confirm it requires "
            "something other than what the script did; this tool has not decided that.")


# ---------------------------------------------------------------------------
# CLI parsing and main
# ---------------------------------------------------------------------------

def _reconfigure_stdout():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _print_error(msg):
    sys.stderr.write("error: %s\n" % msg)
    sys.exit(2)


def main():
    _reconfigure_stdout()

    # Hidden match-worker mode (before argparse)
    if len(sys.argv) > 1 and sys.argv[1] == "--match-worker":
        _match_worker()

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("FINDINGS")
    parser.add_argument("CANDIDATE")
    parser.add_argument("--out", default=None)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--output-cap", type=int, default=65536)
    args = parser.parse_args()  # argparse exits 2 on a usage error and 0 for --help

    if args.timeout <= 0:
        _print_error("--timeout must be > 0")
    if args.output_cap <= 0:
        _print_error("--output-cap must be > 0")

    findings_path = args.FINDINGS
    candidate_path = args.CANDIDATE

    # Validate findings file
    try:
        with open(findings_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        _print_error("cannot read findings file: %s" % (e,))

    if isinstance(data, dict) and "findings" in data:
        findings_list = data["findings"]
        if not isinstance(findings_list, list):
            _print_error("findings key must be a list")
    elif isinstance(data, list):
        findings_list = data
    else:
        _print_error("invalid top-level shape in findings file")

    if len(findings_list) > MAX_FINDINGS:
        _print_error("more than %d findings" % MAX_FINDINGS)

    # Validate candidate
    if not os.path.isfile(candidate_path):
        _print_error("candidate file does not exist: %s" % candidate_path)
    if not candidate_path.endswith(".py"):
        _print_error("candidate must end in .py")

    candidate_folder = os.path.dirname(os.path.abspath(candidate_path))

    # Count candidate folder
    try:
        fc, bc = _count_candidate(candidate_folder)
    except Exception as e:
        _print_error("cannot scan candidate folder: %s" % (e,))
    if fc > MAX_CANDIDATE_FILES:
        _print_error("candidate folder has more than %d files" % MAX_CANDIDATE_FILES)
    if bc > MAX_CANDIDATE_BYTES:
        _print_error("candidate folder exceeds 50 MiB")

    # Compute candidate sha256
    try:
        h = hashlib.sha256()
        with open(candidate_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        candidate_sha = h.hexdigest()
    except Exception as e:
        _print_error("cannot read candidate file: %s" % (e,))

    # Default out path
    if args.out is None:
        stem = os.path.splitext(findings_path)[0]
        out_path = stem + ".result.json"
    else:
        out_path = args.out

    # Validate findings
    seen_ids = set()
    results = []
    valid_findings = []
    for i, f in enumerate(findings_list):
        position = i + 1
        entry, norm = _validate_finding(f, position, seen_ids)
        results.append(entry)
        if norm is not None:
            valid_findings.append((i, norm))

    # Run valid findings
    for idx, finding in valid_findings:
        observed, err = _run_finding(finding, candidate_path, args.timeout, args.output_cap)
        if err is not None:
            results[idx]["label"] = LABEL_DID_NOT_REPRODUCE
            results[idx]["reason"] = err
            results[idx]["observed"] = None
            continue

        full = observed.pop("_full")
        label, reason, next_step = _decide_label(finding, observed, full, args.timeout, args.output_cap)
        results[idx]["label"] = label
        results[idx]["reason"] = reason
        results[idx]["observed"] = observed
        results[idx]["next_step"] = next_step

    # Build result JSON
    counts = {LABEL_NEEDS_SPEC: 0, LABEL_DID_NOT_REPRODUCE: 0,
              LABEL_TIMED_OUT: 0, LABEL_INVALID: 0}
    for r in results:
        counts[r["label"]] += 1

    result_obj = {
        "tool": "filter-review-findings",
        "candidate": os.path.basename(candidate_path),
        "candidate_sha256": candidate_sha,
        "timeout_seconds": args.timeout,
        "output_cap_bytes": args.output_cap,
        "counts": counts,
        "note": "Reproduction is not acceptance; the controller reads each quoted spec sentence.",
        "results": results,
    }

    # Write result JSON
    try:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result_obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    except Exception as e:
        _print_error("cannot write result file: %s" % (e,))

    # Print report
    ids = [r["id"] for r in results]
    labels = [r["label"] for r in results]
    details = [r["reason"][:100].replace("\n", " ") for r in results]
    id_w = max([len("id")] + [len(x) for x in ids]) if ids else 2
    label_w = max([len("label")] + [len(x) for x in labels]) if labels else 5
    detail_w = max([len("detail")] + [len(x) for x in details]) if details else 6

    header = "%-*s | %-*s | %-*s" % (id_w, "id", label_w, "label", detail_w, "detail")
    print(header)
    print("-" * len(header))
    for r in results:
        d = r["reason"][:100].replace("\n", " ")
        print("%-*s | %-*s | %-*s" % (id_w, r["id"], label_w, r["label"], detail_w, d))

    # CHECK SPEC lines
    for r in results:
        if r["label"] == LABEL_NEEDS_SPEC:
            sq = r["spec_quote"].replace("\n", " ")
            cl = r["claim"].replace("\n", " ")
            print('CHECK SPEC [%s]: "%s" (claim: %s)' % (r["id"], sq, cl))

    print("result written to %s" % out_path)

    n = len(results)
    a = counts[LABEL_NEEDS_SPEC]
    b = counts[LABEL_DID_NOT_REPRODUCE]
    c = counts[LABEL_TIMED_OUT]
    d = counts[LABEL_INVALID]
    print("%d findings: %d need a spec check, %d did not reproduce, %d timed out, %d invalid. "
          "This tool decides none of them: the controller reads each quoted spec sentence."
          % (n, a, b, c, d))

    sys.exit(0)


if __name__ == "__main__":
    main()
