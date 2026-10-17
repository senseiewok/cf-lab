"""Check a file of claims against the evidence each one cites, before any of them is published.

A model that writes a note from reports can type a number from memory, write a sentence stronger than its quote, say something is absent
after reading part of a document, or attach a figure to the wrong thing, and the result reads well. This guard removes the cheap classes of
those mistakes and forces a written record of what was searched. Each claim names its evidence, an exact quote from it, and its kind
(observed, computed or inferred); the rules are:

  R1  the claims file parses, holds at least one claim, every claim has the required fields, ids are unique, and its source has evidence
  R2  each quote is an exact piece of that evidence (only whitespace, curly quotes and dashes are normalised), 4 to --max-quote-words words
  R3  every number in the claim is in the quote, or is the result of a `computed` entry whose operands are in the quote; a spelled-out
      one..ten counts as a number and passes only if the quote has its digit form or the same word, or it is a computed result
  R4  a widening word (only, all, never, first, now, agrees, because, ...) or an absence phrase ("not stated") needs a `scope` of 8+ words,
      and an `observed` claim may use a widening word only when its quote uses the same word
  R5  an `inferred` claim needs a `basis` of 8+ words and says "our inference" or "we infer"; a `computed` claim needs `computed` entries

What it does NOT prove: that the quote entails the sentence. A claim can pass every rule and still be wrong. A person or a different model
still reads each quote against its sentence, and then the page.

Usage: python check_claims.py CLAIMS.json --evidence ID=PATH [--evidence ID=PATH ...] [--evidence-map MAP.json] [--max-quote-words N]
       [--widening FILE] [--absence FILE] [--json]
Exit 0: every claim passes every rule. 1: at least one FAIL (including an empty claims file or missing evidence: it fails closed).
2: usage error (a bad flag, an --evidence without ID=PATH, an evidence id given twice, an unreadable map or term list)."""
import argparse
import ast
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path

KINDS = ("observed", "computed", "inferred")
REQUIRED = ("id", "claim", "source", "quote", "kind")
OPTIONAL = ("computed", "scope", "basis")
MIN_QUOTE_WORDS = 4
DEFAULT_MAX_QUOTE_WORDS = 25
MIN_SCOPE_WORDS = 8
MIN_BASIS_WORDS = 8
MAX_EXPR_CHARS = 200

# Words that widen a claim beyond what one quote shows. Whole words, case-insensitive. Replace with --widening FILE.
DEFAULT_WIDENING = (
    "only", "all", "every", "each", "never", "always", "none", "no one", "same", "identical", "first", "last", "no longer", "new in",
    "now", "agrees", "consistent", "stronger", "strongest", "most", "majority", "any", "entire", "whole", "completely", "both", "neither",
    "unique", "cause", "causes", "caused", "because",
)
# Phrases that claim something is missing; they need a record of what was searched. Replace with --absence FILE.
DEFAULT_ABSENCE = ("does not say", "not stated", "no evidence", "absent", "never reported", "there is no")
INFERENCE_MARKERS = ("our inference", "we infer")
SPELLED = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

_CHAR_MAP = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
})
# A number in a claim: not glued to a word or a version string, not the tail of an identifier such as T-0067. A range 2019-2024 gives both ends.
_CLAIM_NUMBER = re.compile(r"(?<![\w.])(?<![A-Za-z]-)\d+(?:,\d{3})*(?:\.\d+)?(?!\w)")
# A number in a quote: any run of digits, so the quote side is generous.
_ANY_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3}(?!\d))")
_ELLIPSIS = re.compile(r"\.\.\.|…")


class UsageError(Exception):
    pass


def normalise_text(s):
    """The only normalisations a quote match allows: curly quotes and dashes to straight ones, then whitespace collapsed. No case folding."""
    return re.sub(r"\s+", " ", s.translate(_CHAR_MAP)).strip()


def count_words(s):
    return len(s.split())


def norm_number(token):
    """'33,782' -> '33782', '99.40' -> '99.4', '05' -> '5'."""
    try:
        d = Decimal(str(token).replace(",", ""))
    except InvalidOperation:
        return None
    return format(d.normalize(), "f")


def claim_numbers(text):
    """Every number written in a claim sentence (normalised), plus the digit form of spelled-out one..ten ("no one" is not a number)."""
    text = normalise_text(text)
    found = [(m.group(0), norm_number(m.group(0))) for m in _CLAIM_NUMBER.finditer(text)]
    for m in re.finditer(r"\b(" + "|".join(SPELLED) + r")\b", text, re.I):
        word = m.group(1).lower()
        if word == "one" and re.search(r"\bno\s+$", text[:m.start()], re.I):
            continue
        found.append((m.group(1), str(SPELLED[word])))
    return found


def quote_numbers(quotes):
    return {norm_number(m.group(0)) for q in quotes for m in _ANY_NUMBER.finditer(normalise_text(q))}


def has_term(text, term):
    words = [re.escape(w) for w in term.split()]
    return re.search(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", text, re.I) is not None


# ---------- safe arithmetic: numbers, + - * / and parentheses; parsed with ast, never evaluated by Python ----------

def safe_arith(expr):
    """(value as Fraction, [operand literals as written]). Raises ValueError for anything but numbers, + - * / and parentheses."""
    if not isinstance(expr, str) or not expr.strip():
        raise ValueError("expr must be a non-empty string")
    if len(expr) > MAX_EXPR_CHARS:
        raise ValueError(f"expr is longer than {MAX_EXPR_CHARS} characters")
    src = _THOUSANDS.sub("", expr.strip())
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"expr does not parse: {e.msg}") from None
    operands = []

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            literal = ast.get_source_segment(src, node) or repr(node.value)
            operands.append(literal)
            return Fraction(Decimal(literal))
        if isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div):
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if right == 0:
                raise ValueError("division by zero")
            return left / right
        if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd):
            v = walk(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        raise ValueError(f"only numbers, + - * / and parentheses are allowed, not {type(node).__name__}")

    return walk(tree), operands


def matches_result(value, result):
    """True when `value` rounded (half up) to the decimals written in `result` equals it: 564 / 127 matches 4.4 and 4.44."""
    d = Decimal(norm_number(result))
    places = max(0, -d.as_tuple().exponent)
    v = Decimal(value.numerator) / Decimal(value.denominator)
    return v.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP) == d


# ---------- the rules; each takes (claim, ctx) and returns (ok, detail). main() looks them up in RULES at call time ----------

def _quotes(claim):
    q = claim["quote"]
    return [q] if isinstance(q, str) else list(q)


def rule_r1(claim, ctx):
    if not isinstance(claim, dict):
        return False, "a claim must be a JSON object"
    problems = []
    for f in REQUIRED:
        if f not in claim:
            problems.append(f"missing field '{f}'")
    for f in ("id", "claim", "source", "kind"):
        if f in claim and (not isinstance(claim[f], str) or not claim[f].strip()):
            problems.append(f"'{f}' must be a non-empty string")
    if "quote" in claim:
        q = claim["quote"]
        if not (isinstance(q, str) and q.strip()) and not (isinstance(q, list) and q and all(isinstance(x, str) and x.strip() for x in q)):
            problems.append("'quote' must be a non-empty string or a non-empty list of them")
    if isinstance(claim.get("kind"), str) and claim["kind"].strip() and claim["kind"] not in KINDS:
        problems.append(f"'kind' must be one of {', '.join(KINDS)}")
    for f in ("scope", "basis"):
        if f in claim and not isinstance(claim[f], str):
            problems.append(f"'{f}' must be a string")
    if "computed" in claim:
        c = claim["computed"]
        if not isinstance(c, list) or not all(isinstance(e, dict) and set(e) == {"expr", "result"} for e in c):
            problems.append("'computed' must be a list of {expr, result} objects")
        elif any(isinstance(e["result"], bool) or not isinstance(e["result"], (int, float, str)) or norm_number(e["result"]) is None
                 for e in c):
            problems.append("each computed 'result' must be a number")
    unknown = sorted(set(claim) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        problems.append(f"unknown field(s) {', '.join(unknown)} (a misspelt 'scope' or 'basis' would otherwise be ignored)")
    if problems:
        return False, "; ".join(problems)
    if ctx["id_counts"].get(claim["id"], 0) > 1:
        return False, f"id '{claim['id']}' is used {ctx['id_counts'][claim['id']]} times"
    src = claim["source"]
    if src not in ctx["evidence"]:
        if src in ctx["evidence_errors"]:
            return False, f"the evidence for source '{src}' could not be read: {ctx['evidence_errors'][src]}"
        return False, f"source '{src}' has no evidence (give --evidence {src}=PATH)"
    return True, "fields, id and evidence present"


def rule_r2(claim, ctx):
    evidence = ctx["evidence"][claim["source"]]
    problems = []
    for i, q in enumerate(_quotes(claim), 1):
        nq = normalise_text(q)
        tag = f"quote {i}" if isinstance(claim["quote"], list) else "quote"
        n = count_words(nq)
        if n < MIN_QUOTE_WORDS:
            problems.append(f"{tag} has {n} word(s); at least {MIN_QUOTE_WORDS} are needed")
        elif n > ctx["max_quote_words"]:
            problems.append(f"{tag} has {n} words; the limit is {ctx['max_quote_words']}")
        if nq in evidence:
            continue
        if _ELLIPSIS.search(nq):
            problems.append(f"{tag} contains an ellipsis and is not in the evidence; split it into separate quotes")
        elif nq.lower() in evidence.lower():
            problems.append(f"{tag} matches the evidence only if case is ignored; copy it exactly")
        else:
            problems.append(f"{tag} is not an exact piece of evidence '{claim['source']}'")
    if problems:
        return False, "; ".join(problems)
    return True, f"{len(_quotes(claim))} quote(s) found exactly in '{claim['source']}'"


def rule_r3(claim, ctx):
    known = quote_numbers(_quotes(claim))
    problems, results = [], set()
    for i, entry in enumerate(claim.get("computed", []), 1):
        try:
            value, operands = safe_arith(entry["expr"])
        except ValueError as e:
            problems.append(f"computed {i}: {e}")
            continue
        missing = [o for o in operands if norm_number(o) not in known | results]
        if missing:
            problems.append(f"computed {i}: operand(s) {', '.join(missing)} not in the quote")
            continue
        if not matches_result(value, entry["result"]):
            problems.append(f"computed {i}: {entry['expr']} is {float(value):.6g}, not {entry['result']}")
            continue
        results.add(norm_number(entry["result"]))
    quotes = " | ".join(normalise_text(q) for q in _quotes(claim))
    for written, n in claim_numbers(claim["claim"]):
        if written.lower() in SPELLED and has_term(quotes, written):
            continue  # the quote uses the same spelled-out word
        if n not in known and n not in results:
            problems.append(f"number {written} is not in the quote and is not a computed result")
    if problems:
        return False, "; ".join(dict.fromkeys(problems))
    return True, "every number is in the quote or computed"


def rule_r4(claim, ctx):
    text = normalise_text(claim["claim"])
    quotes = " | ".join(normalise_text(q) for q in _quotes(claim))
    widening = [t for t in ctx["widening"] if has_term(text, t)]
    absence = [t for t in ctx["absence"] if has_term(text, t)]
    if not widening and not absence:
        return True, "no widening word or absence phrase"
    problems = []
    terms = ", ".join(f"'{t}'" for t in widening + absence)
    scope = claim.get("scope", "")
    if not scope.strip():
        problems.append(f"{terms} need(s) a 'scope' saying what was searched and where")
    elif count_words(scope) < MIN_SCOPE_WORDS:
        problems.append(f"{terms} need(s) a scope of at least {MIN_SCOPE_WORDS} words; it has {count_words(scope)}")
    if claim["kind"] == "observed":
        unquoted = [t for t in widening if not has_term(quotes, t)]
        if unquoted:
            problems.append(f"an observed claim uses {', '.join(repr(t) for t in unquoted)} but its quote does not; "
                            "narrow the sentence or mark it inferred")
    if problems:
        return False, "; ".join(problems)
    return True, f"{terms} with a scope of {count_words(scope)} words"


def rule_r5(claim, ctx):
    kind = claim["kind"]
    if kind == "inferred":
        problems = []
        basis = claim.get("basis", "")
        if count_words(basis) < MIN_BASIS_WORDS:
            problems.append(f"an inferred claim needs a 'basis' of at least {MIN_BASIS_WORDS} words; it has {count_words(basis)}")
        if not any(has_term(claim["claim"], m) for m in INFERENCE_MARKERS):
            problems.append("an inferred claim must say 'our inference' or 'we infer'")
        if problems:
            return False, "; ".join(problems)
    elif kind == "computed" and not claim.get("computed"):
        return False, "a computed claim needs 'computed' entries"
    elif kind == "observed" and claim.get("computed"):
        return False, "an observed claim has 'computed' entries; mark it computed"
    return True, f"kind {kind} has what it needs"


RULES = {"R1": rule_r1, "R2": rule_r2, "R3": rule_r3, "R4": rule_r4, "R5": rule_r5}
RULE_NAMES = {"R1": "fields", "R2": "quote", "R3": "numbers", "R4": "scope", "R5": "kind"}


# ---------- inputs ----------

def parse_evidence_args(pairs, map_path):
    """{id: path}. Raises UsageError for a malformed pair, an unreadable map or an id given twice."""
    out = {}

    def add(eid, path):
        if not eid or not str(path).strip():
            raise UsageError(f"evidence needs ID=PATH, got '{eid}={path}'")
        if eid in out:
            raise UsageError(f"evidence id '{eid}' is given twice")
        out[eid] = Path(path)

    for pair in pairs or []:
        eid, sep, path = pair.partition("=")
        if not sep:
            raise UsageError(f"--evidence needs ID=PATH, got '{pair}'")
        add(eid.strip(), path.strip())
    if map_path:
        try:
            m = json.loads(Path(map_path).read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as e:
            raise UsageError(f"cannot read the evidence map {map_path}: {e}") from None
        if not isinstance(m, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in m.items()):
            raise UsageError("the evidence map must be a JSON object of id -> path")
        base = Path(map_path).parent
        for eid, path in m.items():
            add(eid.strip(), base / path)
    return out


def read_evidence(paths):
    """({id: normalised text}, {id: error}). A missing, unreadable, non-UTF-8 or empty file is an error, never empty evidence."""
    texts, errors = {}, {}
    for eid, p in paths.items():
        try:
            raw = p.read_bytes().decode("utf-8-sig")
        except FileNotFoundError:
            errors[eid] = f"no such file: {p}"
            continue
        except (OSError, UnicodeDecodeError) as e:
            errors[eid] = f"cannot read {p} as UTF-8 text: {type(e).__name__}"
            continue
        if not raw.strip():
            errors[eid] = f"{p} is empty"
            continue
        texts[eid] = normalise_text(raw)
    return texts, errors


def read_terms(path):
    try:
        lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    except OSError as e:
        raise UsageError(f"cannot read the term list {path}: {e}") from None
    terms = [ln.split("#", 1)[0].strip() for ln in lines]
    terms = [t for t in terms if t]
    if not terms:
        raise UsageError(f"the term list {path} has no terms; an empty list would switch the rule off")
    return tuple(terms)


def load_claims(path):
    """(claims, problem). A problem means the file fails R1 as a whole."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return None, f"no such claims file: {path}"
    except (OSError, UnicodeDecodeError) as e:
        return None, f"cannot read {path}: {type(e).__name__}"
    except ValueError as e:
        return None, f"{path} is not valid JSON: {e}"
    if not isinstance(data, list):
        return None, f"{path} must hold a JSON list of claims"
    if not data:
        return None, f"{path} holds no claims; an empty file fails, it is never 'nothing to check'"
    return data, None


def check(claims, evidence, evidence_errors, max_quote_words=DEFAULT_MAX_QUOTE_WORDS, widening=DEFAULT_WIDENING, absence=DEFAULT_ABSENCE):
    """[{"id", "rule", "name", "ok", "detail"}] for every claim and rule. A claim that fails R1 is not checked further."""
    ids = [c.get("id") for c in claims if isinstance(c, dict) and isinstance(c.get("id"), str)]
    ctx = {"evidence": evidence, "evidence_errors": evidence_errors, "max_quote_words": max_quote_words,
           "widening": widening, "absence": absence, "id_counts": {i: ids.count(i) for i in ids}}
    out = []
    for n, claim in enumerate(claims, 1):
        cid = claim.get("id") if isinstance(claim, dict) and isinstance(claim.get("id"), str) and claim["id"].strip() else f"#{n}"
        for rule in RULES:
            ok, detail = RULES[rule](claim, ctx)
            out.append({"id": cid, "rule": rule, "name": RULE_NAMES[rule], "ok": ok, "detail": detail})
            if rule == "R1" and not ok:
                break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check each claim against an exact quote from the evidence it cites (rules R1 to R5; see the README).",
        epilog="What it does NOT prove: that the quote entails the sentence. It removes the cheap classes of invented claims and forces a "
               "written scope; a person or a different model still reads each quote against its sentence, then the page.")
    ap.add_argument("claims", help="a JSON file holding a list of claims")
    ap.add_argument("--evidence", action="append", metavar="ID=PATH", help="a UTF-8 text file a claim's 'source' names; repeat for more")
    ap.add_argument("--evidence-map", metavar="FILE", help="a JSON object of id -> path (relative to the map's folder)")
    ap.add_argument("--max-quote-words", type=int, default=DEFAULT_MAX_QUOTE_WORDS, metavar="N")
    ap.add_argument("--widening", metavar="FILE", help="one widening word or phrase per line, replacing the default list")
    ap.add_argument("--absence", metavar="FILE", help="one absence phrase per line, replacing the default list")
    ap.add_argument("--json", action="store_true", help="print the results as JSON")
    a = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # a Windows console may not show every character; never crash a report over it
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")
    target_path = Path(a.claims)
    companion_map = None
    claims: list | None = None
    problem: str | None = None
    original_md_path: Path | None = None
    if target_path.suffix.lower() == ".md":
        original_md_path = target_path
        companion_claims = target_path.parent / f"{target_path.stem}-claims.json"
        if companion_claims.exists():
            target_path = companion_claims
            cand_map = target_path.parent / f"{target_path.stem.removesuffix('-claims')}-evidence-map.json"
            if cand_map.exists():
                companion_map = cand_map
        else:
            problem = f"no companion claims file found for {a.claims}: expected {companion_claims}"
    elif target_path.name.endswith("-claims.json"):
        cand_map = target_path.parent / f"{target_path.stem.removesuffix('-claims')}-evidence-map.json"
        if cand_map.exists():
            companion_map = cand_map

    try:
        if a.max_quote_words < MIN_QUOTE_WORDS:
            raise UsageError(f"--max-quote-words must be at least {MIN_QUOTE_WORDS}")
        map_to_use = a.evidence_map or (str(companion_map) if companion_map and not a.evidence else None)
        paths = parse_evidence_args(a.evidence, map_to_use)
        widening = read_terms(a.widening) if a.widening else DEFAULT_WIDENING
        absence = read_terms(a.absence) if a.absence else DEFAULT_ABSENCE
    except UsageError as e:
        print(f"ERROR: {e}")
        return 2
    evidence, evidence_errors = read_evidence(paths)
    if problem is None:
        claims, problem = load_claims(target_path)
    results = []
    if not paths:
        results.append({"id": "-", "rule": "R1", "name": "fields", "ok": False, "detail": "no evidence was given (--evidence ID=PATH)"})
    for eid, err in evidence_errors.items():
        results.append({"id": "-", "rule": "R1", "name": "fields", "ok": False, "detail": f"evidence '{eid}': {err}"})
    if problem:
        results.append({"id": "-", "rule": "R1", "name": "fields", "ok": False, "detail": problem})
    else:
        results.extend(check(claims, evidence, evidence_errors, a.max_quote_words, widening, absence))
        if original_md_path and claims:
            try:
                md_text = original_md_path.read_text(encoding="utf-8")
                md_norm = normalise_text(md_text)
                for c in claims:
                    cid = c.get("id", "?")
                    c_text = c.get("claim", "")
                    c_norm = normalise_text(c_text)
                    if c_norm not in md_norm:
                        c_nums = [n for _, n in claim_numbers(c_text)]
                        if not (c_nums and all(n in md_norm for n in c_nums)):
                            results.append(
                                {
                                    "id": cid,
                                    "rule": "R2",
                                    "name": "companion_markdown",
                                    "ok": False,
                                    "detail": f"claim sentence or numbers not found in companion markdown {original_md_path.name}",
                                }
                            )
            except Exception as e:
                results.append(
                    {
                        "id": "-",
                        "rule": "R2",
                        "name": "companion_markdown",
                        "ok": False,
                        "detail": f"could not read companion markdown {original_md_path}: {e}",
                    }
                )
    failures = sum(1 for r in results if not r["ok"])
    n_claims = len(claims) if claims else 0
    if a.json:
        print(json.dumps({"claims": n_claims, "failures": failures, "ok": failures == 0, "results": results}, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print(f"{'PASS' if r['ok'] else 'FAIL'} {r['id']} {r['rule']} {r['name']}: {r['detail']}")
        print(f"{n_claims} claims, {failures} failures")
        print("A pass does not prove that a quote supports its sentence; a person or a different model still reads them.")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
