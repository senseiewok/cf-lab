#!/usr/bin/env python3
"""loop-report.py - read v2 delegation-loop log rows and print a plain-text report."""
import argparse
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, ROUND_HALF_UP


def code_of(label):
    if not label or not isinstance(label, str):
        return None
    colon = label.find(':')
    code = label[:colon] if colon >= 0 else label
    return code.upper()


def has_reply(row):
    # A reply is a candidate hash, or a NOFENCE label (a reply that held no fenced block).
    return row.get('candidate_sha256') is not None or code_of(row.get('label')) == 'NOFENCE'


def round1(value):
    q = Decimal(1) / Decimal(10)
    return Decimal(value).quantize(q, rounding=ROUND_HALF_UP)


def percent(numerator, denominator):
    if denominator == 0:
        return None
    val = (Decimal(numerator) * Decimal(100)) / Decimal(denominator)
    return round1(val)


class Run:
    __slots__ = ('id', 'attempts', 'run_row')

    def __init__(self, run_id):
        self.id = run_id
        self.attempts = []
        self.run_row = None


def tag_of(run):
    if run.run_row is not None:
        return run.run_row.get('tag')
    for a in run.attempts:
        return a.get('tag')
    return None


def state_of(run):
    if run.run_row is not None:
        s = run.run_row.get('state')
        if s in ('accepted', 'budget exhausted', 'failed', 'cancelled'):
            return s
        return 'unknown'
    return 'interrupted'


def read_v2(paths, skipped_counter):
    runs = {}
    order = []
    for path in paths:
        with open(path, 'r', encoding='utf-8-sig', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    skipped_counter['n'] += 1
                    continue
                if not isinstance(obj, dict):
                    skipped_counter['n'] += 1
                    continue
                kind = obj.get('kind')
                if kind == 'attempt':
                    rid = obj.get('run')
                    if rid is None:
                        skipped_counter['n'] += 1
                        continue
                    r = runs.get(rid)
                    if r is None:
                        r = Run(rid)
                        runs[rid] = r
                        order.append(r)
                    r.attempts.append(obj)
                elif kind == 'run':
                    rid = obj.get('run')
                    if rid is None:
                        skipped_counter['n'] += 1
                        continue
                    r = runs.get(rid)
                    if r is None:
                        r = Run(rid)
                        runs[rid] = r
                        order.append(r)
                    r.run_row = obj
                else:
                    pass
    return order


def extract_candidate(text):
    lines = re.split(r'\r?\n', text)
    open_re = re.compile(r'^\s*```[A-Za-z0-9_+-]*\s*$')
    close_re = re.compile(r'^\s*```\s*$')
    opening = None
    for i, ln in enumerate(lines):
        if open_re.match(ln):
            opening = i
            break
    if opening is None:
        return None
    closing = None
    for j in range(len(lines) - 1, opening, -1):
        if close_re.match(lines[j]):
            closing = j
            break
    if closing is None:
        return None
    body = lines[opening + 1:closing]
    return '\n'.join(body)


def backfill(v1log, root, write_rows):
    skipped_folder = 0
    built = []
    with open(v1log, 'r', encoding='utf-8-sig', errors='replace') as f:
        lines = [ln for ln in f if ln.strip()]

    counter = 0
    run_objs = []
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            run_objs.append(obj)

    for v1 in run_objs:
        wd = v1.get('work_dir')
        if wd is None or not os.path.isabs(wd):
            wd = os.path.join(root, wd) if wd else root
        usage_path = os.path.join(wd, 'usage.jsonl')
        if not os.path.isdir(wd) or not os.path.isfile(usage_path):
            skipped_folder += 1
            continue

        counter += 1
        rid = 'bf%d' % counter
        tag = v1.get('tag')
        prev_sha = None
        state = 'failed'
        outcome = v1.get('outcome')
        if outcome in ('accepted', 'salvaged'):
            state = 'accepted'
        elif outcome == 'not accepted':
            state = 'budget exhausted'

        attempts = []
        n = 0
        with open(usage_path, 'r', encoding='utf-8-sig', errors='replace') as uf:
            for ln in uf:
                ln = ln.strip()
                if not ln:
                    continue
                n += 1
                try:
                    uo = json.loads(ln)
                except Exception:
                    uo = {}
                if not isinstance(uo, dict):
                    uo = {}
                think = uo.get('think')
                mode = 'thinking' if think is True else 'default'
                prompt_tokens = uo.get('prompt_tokens')
                output_tokens = uo.get('output_tokens')
                done_reason = uo.get('done_reason')
                ped = uo.get('prompt_eval_duration')

                sha = None
                reply_path = os.path.join(wd, 'reply-%d.txt' % n)
                nofence = False
                if os.path.isfile(reply_path):
                    with open(reply_path, 'r', encoding='utf-8-sig', errors='replace') as rf:
                        text = rf.read()
                    cand = extract_candidate(text)
                    if cand is None:
                        nofence = True
                    else:
                        sha = hashlib.sha256(cand.encode('utf-8')).hexdigest()

                # label rules in order
                label = None
                if nofence:
                    label = 'NOFENCE'
                elif done_reason == 'length':
                    label = 'CAP'
                elif n >= 2 and sha is not None and prev_sha is not None and sha == prev_sha:
                    label = 'IDENT'
                elif state == 'accepted' and v1.get('attempts') == n:
                    label = None
                else:
                    label = 'UNKNOWN'

                row = {
                    'kind': 'attempt',
                    'run': rid,
                    'tag': tag,
                    'n': n,
                    'mode': mode,
                    'label': label,
                    'prompt_tokens': prompt_tokens,
                    'output_tokens': output_tokens,
                    'prompt_eval_duration': ped,
                    'done_reason': done_reason,
                    'candidate_sha256': sha,
                }
                attempts.append(row)
                if sha is not None:
                    prev_sha = sha

        run_row = {
            'kind': 'run',
            'run': rid,
            'tag': tag,
            'task': v1.get('task'),
            'outcome': outcome,
            'state': state,
            'attempts': v1.get('attempts'),
            'max_attempts': v1.get('max_attempts'),
            'seconds': v1.get('seconds'),
            'output_tokens': v1.get('output_tokens'),
        }
        built.extend(attempts)
        built.append(run_row)

    if write_rows:
        with open(write_rows, 'w', encoding='utf-8') as wf:
            for r in built:
                wf.write(json.dumps(r, separators=(',', ':')) + '\n')

    return built, skipped_folder


def group_runs(order):
    groups = {}
    for r in order:
        t = tag_of(r)
        if t is None or t == '':
            key = '(no tag)'
        else:
            key = str(t)
        groups.setdefault(key, []).append(r)
    return groups


def compute_block(runs):
    R = len(runs)
    states = {'accepted': 0, 'budget exhausted': 0, 'failed': 0, 'cancelled': 0, 'interrupted': 0}
    for r in runs:
        s = state_of(r)
        if s in states:
            states[s] += 1
    # The two states the verifier freeze (V2-02) writes are counted on their own, so the states line stays as it was when there are none.
    verifier_stops = {'blocked': 0, 'accepted-after-verifier-edit': 0}
    for r in runs:
        raw = r.run_row.get('state') if r.run_row is not None else None
        if raw in verifier_stops:
            verifier_stops[raw] += 1

    K = None
    for r in runs:
        if r.run_row is not None:
            ma = r.run_row.get('max_attempts')
            if isinstance(ma, int):
                if K is None or ma > K:
                    K = ma
    if K is None:
        K = 3

    accepted_on_attempt = [0] * (K + 1)
    for r in runs:
        if state_of(r) == 'accepted' and r.run_row is not None:
            att = r.run_row.get('attempts')
            if isinstance(att, int) and 1 <= att <= K:
                accepted_on_attempt[att] += 1

    pass_at = [0] * (K + 1)
    for k in range(1, K + 1):
        for r in runs:
            if state_of(r) == 'accepted' and r.run_row is not None:
                att = r.run_row.get('attempts')
                if isinstance(att, int) and att <= k:
                    pass_at[k] += 1

    out_tokens = 0
    prompt_tokens = 0
    ident_attempts = 0
    suspect_attempts = 0
    comparable_retries = 0
    identical_retries = 0
    thinking_out = 0
    cap_hits = 0
    ped_ns = 0

    for r in runs:
        attempts = r.attempts
        by_n = {}
        for a in attempts:
            n = a.get('n')
            if isinstance(n, int):
                by_n[n] = a

        for a in attempts:
            ot = a.get('output_tokens')
            if isinstance(ot, (int, float)):
                out_tokens += ot
                if a.get('mode') == 'thinking':
                    thinking_out += ot
            pt = a.get('prompt_tokens')
            if isinstance(pt, (int, float)):
                prompt_tokens += pt
            ped = a.get('prompt_eval_duration')
            if isinstance(ped, (int, float)):
                ped_ns += ped

            code = code_of(a.get('label'))
            if code == 'IDENT':
                ident_attempts += 1
            elif code == 'SUSPECT':
                suspect_attempts += 1

            n = a.get('n')
            if isinstance(n, int) and n >= 2:
                prev_a = by_n.get(n - 1)
                if prev_a is not None:
                    if has_reply(a) and has_reply(prev_a):
                        comparable_retries += 1
                        sha_cur = a.get('candidate_sha256')
                        sha_prev = prev_a.get('candidate_sha256')
                        if sha_cur is not None and sha_prev is not None and sha_cur == sha_prev:
                            identical_retries += 1

            if code == 'CAP' or a.get('done_reason') == 'length':
                cap_hits += 1

    accepted_count = states['accepted']
    out_per_artifact = None
    if accepted_count > 0:
        val = Decimal(out_tokens) / Decimal(accepted_count)
        out_per_artifact = round1(val)

    thinking_share = percent(thinking_out, out_tokens)

    prompt_eval_s = round1(Decimal(ped_ns) / Decimal(1000000000))

    reached_runs = []
    for r in runs:
        for a in r.attempts:
            n = a.get('n')
            if isinstance(n, int) and n >= 3:
                reached_runs.append(r)
                break
    reached_R = len(reached_runs)
    reached_O = 0
    for r in reached_runs:
        for a in r.attempts:
            ot = a.get('output_tokens')
            if isinstance(ot, (int, float)):
                reached_O += ot

    return {
        'R': R,
        'states': states,
        'verifier_stops': verifier_stops,
        'K': K,
        'accepted_on_attempt': accepted_on_attempt,
        'pass_at': pass_at,
        'out_tokens': out_tokens,
        'prompt_tokens': prompt_tokens,
        'out_per_artifact': out_per_artifact,
        'ident_attempts': ident_attempts,
        'suspect_attempts': suspect_attempts,
        'comparable_retries': comparable_retries,
        'identical_retries': identical_retries,
        'thinking_share': thinking_share,
        'cap_hits': cap_hits,
        'prompt_eval_s': prompt_eval_s,
        'reached_R': reached_R,
        'reached_O': reached_O,
    }


def pass_k(runs, k):
    tasks = {}
    for r in runs:
        if r.run_row is None:
            continue
        s = state_of(r)
        if s not in ('accepted', 'budget exhausted', 'failed'):
            continue
        task = r.run_row.get('task')
        if not task:
            continue
        tasks.setdefault(task, []).append(s)

    eligible = 0
    all_accepted = 0
    for task, ss in tasks.items():
        if len(ss) >= k:
            eligible += 1
            if all(x == 'accepted' for x in ss):
                all_accepted += 1

    if eligible == 0:
        return 'pass^%d: n/a (no task has %d or more runs)' % (k, k)
    return 'pass^%d: %d of %d tasks with %d+ runs had every run accepted' % (k, all_accepted, eligible, k)


def fmt_block(name, stats, pass_k_line):
    lines = []
    if name is None:
        lines.append('== all ==')
    else:
        lines.append('== tag: %s ==' % name)
    lines.append('runs: %d' % stats['R'])
    st = stats['states']
    lines.append('states: accepted %d, budget exhausted %d, failed %d, cancelled %d, interrupted %d' % (
        st['accepted'], st['budget exhausted'], st['failed'], st['cancelled'], st['interrupted']))
    vs = stats['verifier_stops']
    if vs['blocked'] or vs['accepted-after-verifier-edit']:
        lines.append('verifier freeze: blocked %d, accepted-after-verifier-edit %d (neither is counted in the states above)' % (vs['blocked'], vs['accepted-after-verifier-edit']))

    K = stats['K']
    aoa = stats['accepted_on_attempt']
    parts = []
    for j in range(1, K + 1):
        parts.append('%d:%d' % (j, aoa[j]))
    lines.append('accepted on attempt: ' + ' '.join(parts))

    pa = stats['pass_at']
    R = stats['R']
    for k in range(1, K + 1):
        lines.append('pass@%d: %d of %d' % (k, pa[k], R))

    lines.append(pass_k_line)

    lines.append('output tokens: %d' % stats['out_tokens'])
    lines.append('prompt tokens: %d' % stats['prompt_tokens'])

    if stats['out_per_artifact'] is None:
        lines.append('output tokens per accepted artifact: n/a (nothing accepted)')
    else:
        lines.append('output tokens per accepted artifact: %s' % str(stats['out_per_artifact']))

    lines.append('IDENT attempts: %d' % stats['ident_attempts'])
    lines.append('SUSPECT attempts: %d' % stats['suspect_attempts'])
    lines.append('comparable retries: %d, identical: %d' % (stats['comparable_retries'], stats['identical_retries']))

    if stats['thinking_share'] is None:
        lines.append('thinking share of output tokens: n/a (no output tokens)')
    else:
        lines.append('thinking share of output tokens: %s percent' % str(stats['thinking_share']))

    lines.append('cap hits: %d' % stats['cap_hits'])
    lines.append('prompt-eval seconds: %s' % str(stats['prompt_eval_s']))

    if stats['out_tokens'] == 0:
        lines.append('reached attempt 3: runs %d, output tokens %d of %d (n/a)' % (
            stats['reached_R'], stats['reached_O'], stats['out_tokens']))
    else:
        p = percent(stats['reached_O'], stats['out_tokens'])
        lines.append('reached attempt 3: runs %d, output tokens %d of %d (%s percent)' % (
            stats['reached_R'], stats['reached_O'], stats['out_tokens'], str(p)))

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(prog='loop-report.py', add_help=False)
    parser.add_argument('LOGS', nargs='*')
    parser.add_argument('--backfill', dest='backfill', default=None)
    parser.add_argument('--root', dest='root', default=None)
    parser.add_argument('--k', dest='k', type=int, default=2)
    parser.add_argument('--write-rows', dest='write_rows', default=None)

    try:
        args = parser.parse_args()
    except SystemExit as e:
        if e.code != 0:
            sys.exit(2)
        raise

    if args.k < 1:
        sys.stderr.write('error: --k must be at least 1\n')
        sys.exit(2)

    if args.write_rows is not None and args.backfill is None:
        sys.stderr.write('error: --write-rows requires --backfill\n')
        sys.exit(2)

    if not args.LOGS and args.backfill is None:
        sys.stderr.write('error: no arguments (provide LOG file(s) or --backfill)\n')
        sys.exit(2)

    skipped = {'n': 0}
    order = []
    if args.LOGS:
        try:
            order = read_v2(args.LOGS, skipped)
        except OSError as e:
            sys.stderr.write('error: cannot read log: %s\n' % (e.strerror or 'read error'))
            sys.exit(2)

    built_rows = []
    if args.backfill is not None:
        root = args.root
        if root is None:
            root = os.path.dirname(os.path.abspath(args.backfill))
        try:
            with open(args.backfill, 'r', encoding='utf-8-sig', errors='replace') as f:
                pass
        except OSError:
            sys.stderr.write('error: cannot read backfill log\n')
            sys.exit(2)

        built_rows, skipped_folder = backfill(args.backfill, root, args.write_rows)
        if skipped_folder > 0:
            sys.stderr.write('note: skipped %d run(s) whose work folder was not found\n' % skipped_folder)

        runs_map = {}
        order2 = []
        for row in built_rows:
            kind = row.get('kind')
            rid = row.get('run')
            if rid is None:
                continue
            r = runs_map.get(rid)
            if r is None:
                r = Run(rid)
                runs_map[rid] = r
                order2.append(r)
            if kind == 'attempt':
                r.attempts.append(row)
            elif kind == 'run':
                r.run_row = row
        order.extend(order2)

    if not order:
        sys.stderr.write('error: no v2 rows found (try --backfill for old outcome logs)\n')
        sys.exit(2)

    groups = group_runs(order)
    keys = [k for k in groups.keys() if k != '(no tag)']
    keys.sort()
    blocks = []
    for key in keys:
        stats = compute_block(groups[key])
        pk_line = pass_k(groups[key], args.k)
        blocks.append(fmt_block(key, stats, pk_line))

    if '(no tag)' in groups:
        stats = compute_block(groups['(no tag)'])
        pk_line = pass_k(groups['(no tag)'], args.k)
        blocks.append(fmt_block('(no tag)', stats, pk_line))

    all_stats = compute_block(order)
    all_pk = pass_k(order, args.k)
    blocks.append(fmt_block(None, all_stats, all_pk))

    report = '\n\n'.join(blocks) + '\n'
    sys.stdout.write(report)

    if skipped['n'] > 0:
        sys.stderr.write('note: skipped %d unreadable line(s)\n' % skipped['n'])

    sys.exit(0)


if __name__ == '__main__':
    main()
