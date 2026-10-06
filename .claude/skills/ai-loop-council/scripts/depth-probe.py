#!/usr/bin/env python3
"""depth-probe: measure whether a local Ollama model can use a synthetic fact hidden at a chosen depth of a long filler prompt."""
import argparse
import json
import random
import sys
import time
import re
import urllib.request
import urllib.parse
from pathlib import Path

ADJ = ["quiet", "ancient", "bright", "gentle", "dusty", "silver", "amber", "crimson", "hollow", "winding", "silent", "gilded", "faded", "mossy", "pale"]
NOUN = ["river", "mill", "bridge", "valley", "forest", "harbor", "tower", "meadow", "coastline", "orchard", "cavern", "glacier", "island", "fjord", "prairie"]
VERB = ["carried", "wrapped", "drifted", "spun", "wove", "held", "shaped", "bent", "folded", "lifted", "pressed", "traced", "sketched", "brushed", "drew"]
NUM = ["seven", "three", "nine", "twelve", "five", "eleven", "four", "eight", "six", "ten"]
OBS = ["wooden", "stone", "iron", "glass", "silk", "brass", "clay", "leather", "steel", "copper"]
PREP = ["past", "along", "beneath", "across", "through", "beyond", "beside", "around", "over", "under"]


def check_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme != "http":
        return False
    h = (p.hostname or "").lower()
    return h in ("127.0.0.1", "localhost", "::1")


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description="depth probe for local Ollama models")
    ap.add_argument("--url", default="http://127.0.0.1:11434")
    ap.add_argument("--model")
    ap.add_argument("--profile")
    ap.add_argument("--lengths", default="8000,32000,56000")
    ap.add_argument("--depths", default="0.1,0.5,0.9")
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--out")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--chars-per-token", type=float, default=4.0,
                    help="sizing ratio: a prompt for --lengths N is about N * ratio characters. Default 4. "
                         "For this script's synthetic filler with the Qwen3.8 27B tokenizer the counted prompt tokens were about 77 percent of the chars/4 estimate, "
                         "so the calibrated ratio is 5.15 (32000 characters were counted as 6212 tokens), which makes the requested length match the counted tokens; the table and --out rows report the counted tokens")
    ap.add_argument("--think", choices=["on", "off"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args(argv)

    if args.chars_per_token <= 0:
        print("error: --chars-per-token must be positive", file=sys.stderr)
        sys.exit(2)
    if not check_url(args.url):
        print(f"error: --url must be http on a loopback host (127.0.0.1, localhost, ::1); got {args.url}", file=sys.stderr)
        sys.exit(2)

    profile = {}
    if args.profile:
        ppath = Path(args.profile)
        try:
            with open(ppath, encoding="utf-8") as f:
                profile = json.load(f)
        except Exception as e:
            print(f"error: cannot read --profile {ppath}: {e}", file=sys.stderr)
            sys.exit(2)

    model = args.model or profile.get("model")
    if not args.dry_run and not model:
        ap.error("--model is required (or provide a profile with a 'model' key)")

    think_default = False
    if "think" in profile:
        think_default = bool(profile["think"])
    if args.think == "on":
        think_bool = True
    elif args.think == "off":
        think_bool = False
    else:
        think_bool = think_default

    lengths = [int(x) for x in re.findall(r"\d+", args.lengths)]
    depths = [float(x) for x in args.depths.split(",") if x.strip()]
    return {
        "url": args.url, "model": model, "profile": profile,
        "lengths": lengths, "depths": depths, "samples": args.samples,
        "out": args.out, "seed": args.seed, "cpt": args.chars_per_token, "think": think_bool,
        "dry_run": args.dry_run, "show_prompt": args.show_prompt,
    }


def filler_sentences(seed, length, budget):
    rng = random.Random(seed * 1000003 + length)
    out = []
    total = 0
    while True:
        s = f"The {rng.choice(ADJ)} {rng.choice(NOUN)} {rng.choice(VERB)} {rng.choice(NUM)} {rng.choice(OBS)} {rng.choice(NOUN)}s {rng.choice(PREP)} the {rng.choice(ADJ)} {rng.choice(NOUN)}."
        out.append(s)
        total += len(s) + 1
        if total >= budget:
            break
    return out


def build_prompts(cfg):
    seed = cfg["seed"]
    code_rng = random.Random(seed)
    n_letters = code_rng.randint(6, 8)
    letters = "".join(code_rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(n_letters))
    digits = "".join(code_rng.choice("0123456789") for _ in range(4))
    code = f"{letters}-{digits}"
    fact_sentence = f"The access code for the blue door is {code}."
    question = "Using only the text above, what is the access code for the blue door? Reply with the code only, or not stated if the text does not say."

    results = []
    for L in cfg["lengths"]:
        budget = max(int(L * cfg["cpt"]) - len(fact_sentence) - len(question) - 4, 100)
        base_sent = filler_sentences(seed, L, budget)

        # Control prompt (no fact): the same filler as every fact prompt of this length
        ctrl_prompt = " ".join(base_sent) + "\n\n" + question
        results.append({"length": L, "depth": None, "control": True, "prompt": ctrl_prompt, "fact_sentence": None})

        # Fact prompts for each depth
        for d in cfg["depths"]:
            sent_list = list(base_sent)
            idx = round(d * len(sent_list))
            idx = max(0, min(idx, len(sent_list)))
            sent_list.insert(idx, fact_sentence)
            text = " ".join(sent_list)
            prompt = text + "\n\n" + question
            pos = prompt.index(fact_sentence)
            fact_at = pos / len(prompt)
            results.append({"length": L, "depth": d, "control": False, "prompt": prompt, "fact_sentence": fact_sentence, "fact_at": fact_at})
    return code, results


def ask(url, model, think, seed, profile, prompt):
    options = {"num_ctx": 65536, "seed": seed}
    prof_opts = {k: v for k, v in profile.items() if k not in ("model", "think", "num_ctx")}
    options.update(prof_opts)
    if "num_ctx" in profile and isinstance(profile["num_ctx"], int):
        options["num_ctx"] = profile["num_ctx"]
    if not prof_opts:
        options["temperature"] = 0

    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": think,
        "options": options,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url.rstrip("/") + "/api/chat", data=data, headers={"Content-Type": "application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=3600) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, str(e), time.time() - t0
    elapsed = time.time() - t0
    reply_text = raw.get("message", {}).get("content", "") or ""
    reply_text = re.sub(r"<think>.*?</think>", "", reply_text, flags=re.DOTALL).strip()
    return {
        "reply": reply_text,
        "prompt_eval_count": raw.get("prompt_eval_count"),
        "eval_count": raw.get("eval_count"),
    }, None, elapsed


def score_fact(reply, code):
    return code.lower() in reply.lower()


def score_control(reply):
    low = reply.lower()
    if "not stated" not in low:
        return False
    if re.search(r"[A-Za-z]+-\d+", reply):
        return False
    return True


def note_near_ctx(length, depth, prompt_tokens, num_ctx):
    """Say so when the counted prompt is within 512 tokens of the window: the server may have cut the front of the prompt."""
    if isinstance(prompt_tokens, int) and prompt_tokens >= num_ctx - 512:
        print(f"[{length}/{depth}] counted prompt tokens {prompt_tokens} are within 512 of num_ctx {num_ctx}: the front of the prompt may have been truncated", file=sys.stderr)


def median_tokens(vals):
    vals = sorted(v for v in vals if isinstance(v, int))
    return vals[len(vals) // 2] if vals else None


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    cfg = parse_args()
    code, prompts = build_prompts(cfg)

    if cfg["dry_run"]:
        by_len = {}
        for p in prompts:
            L = p["length"]
            by_len.setdefault(L, []).append(p)
        for L in cfg["lengths"]:
            entries = [p for p in by_len.get(L, []) if not p["control"]]
            ctrl = [p for p in by_len.get(L, []) if p["control"]]
            for p in entries:
                line = f"length={L} depth={p['depth']:g} approx_tokens={int(len(p['prompt']) / cfg['cpt'])} chars={len(p['prompt'])} fact_at={p['fact_at']:.3f}"
                print(line)
                if cfg["show_prompt"]:
                    print(p["prompt"])
                    print()
            for p in ctrl:
                line = f"control length={L} approx_tokens={int(len(p['prompt']) / cfg['cpt'])} chars={len(p['prompt'])}"
                print(line)
                if cfg["show_prompt"]:
                    print(p["prompt"])
                    print()
        return

    # Real run
    out_file = None
    if cfg["out"]:
        opath = Path(cfg["out"])
        opath.parent.mkdir(parents=True, exist_ok=True)
        out_file = open(opath, "w", encoding="utf-8")

    results = []  # (length, depth, correct, seconds, counted prompt tokens)
    control_results = []  # (length, correct, seconds, counted prompt tokens)
    num_ctx = cfg["profile"].get("num_ctx", 65536) if isinstance(cfg["profile"].get("num_ctx", 65536), int) else 65536

    for L in cfg["lengths"]:
        fact_entries = [p for p in prompts if p["length"] == L and not p["control"]]
        ctrl_entries = [p for p in prompts if p["length"] == L and p["control"]]

        for p in fact_entries:
            d = p["depth"]
            for s in range(cfg["samples"]):
                res, err, elapsed = ask(cfg["url"], cfg["model"], cfg["think"], cfg["seed"] + s, cfg["profile"], p["prompt"])
                if err is not None:
                    correct = False
                    reply_text = f"ERROR: {err}"
                    prompt_tokens = None
                    eval_tokens = None
                else:
                    correct = score_fact(res["reply"], code)
                    reply_text = res["reply"]
                    prompt_tokens = res.get("prompt_eval_count")
                    eval_tokens = res.get("eval_count")
                print(f"[{L}/{d:g}/s{s}] {'OK' if correct else 'MISS'} {elapsed:.2f}s", file=sys.stderr)
                results.append((L, d, correct, elapsed, prompt_tokens))
                note_near_ctx(L, d, prompt_tokens, num_ctx)
                row = {
                    "length": L, "depth": d, "control": False, "sample": s,
                    "correct": correct, "seconds": elapsed,
                    "reply": reply_text[:200], "expected": code,
                    "prompt_tokens": prompt_tokens, "eval_tokens": eval_tokens,
                    "chars_per_token": cfg["cpt"],
                    "model": cfg["model"], "think": cfg["think"], "seed": cfg["seed"],
                }
                if out_file:
                    out_file.write(json.dumps(row, ensure_ascii=False) + "\n")

        for p in ctrl_entries:
            for s in range(cfg["samples"]):
                res, err, elapsed = ask(cfg["url"], cfg["model"], cfg["think"], cfg["seed"] + s, cfg["profile"], p["prompt"])
                if err is not None:
                    correct = False
                    reply_text = f"ERROR: {err}"
                    prompt_tokens = None
                    eval_tokens = None
                else:
                    correct = score_control(res["reply"])
                    reply_text = res["reply"]
                    prompt_tokens = res.get("prompt_eval_count")
                    eval_tokens = res.get("eval_count")
                print(f"[{L}/control/s{s}] {'OK' if correct else 'FAIL'} {elapsed:.2f}s", file=sys.stderr)
                control_results.append((L, correct, elapsed, prompt_tokens))
                note_near_ctx(L, 'control', prompt_tokens, num_ctx)
                row = {
                    "length": L, "depth": None, "control": True, "sample": s,
                    "correct": correct, "seconds": elapsed,
                    "reply": reply_text[:200], "expected": None,
                    "prompt_tokens": prompt_tokens, "eval_tokens": eval_tokens,
                    "chars_per_token": cfg["cpt"],
                    "model": cfg["model"], "think": cfg["think"], "seed": cfg["seed"],
                }
                if out_file:
                    out_file.write(json.dumps(row, ensure_ascii=False) + "\n")

    if out_file:
        out_file.close()

    # Print table
    print("length  depth  correct/total  median_seconds  counted_prompt_tokens")
    for L in cfg["lengths"]:
        for d in cfg["depths"]:
            rows = [(c, s, t) for (ll, dd, c, s, t) in results if ll == L and dd == d]
            total = len(rows)
            ok = sum(1 for c, _, _ in rows if c)
            secs = sorted(s for _, s, _ in rows)
            med = secs[len(secs) // 2] if secs else 0.0
            print(f"{L}  {d:g}  {ok}/{total}  {med:.1f}  {median_tokens([t for _, _, t in rows])}")

    for L in cfg["lengths"]:
        rows = [(c, s, t) for (ll, c, s, t) in control_results if ll == L]
        total = len(rows)
        ok = sum(1 for c, _, _ in rows if c)
        secs = sorted(s for _, s, _ in rows)
        med = secs[len(secs) // 2] if secs else 0.0
        print(f"control  {L}  {ok}/{total}  {med:.1f}  {median_tokens([t for _, _, t in rows])}")


if __name__ == "__main__":
    main()
