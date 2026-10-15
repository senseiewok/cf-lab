#!/usr/bin/env python3
"""Deterministic scanner for queries concerning one real person.

Enforces the privacy rule from security-browsing and cf-research-context (Task T-0109):
"before any search or cloud call, rewrite the question in general terms, say so,
 and keep nothing about the person; a session-close scan lists web-tool inputs
 that combine a health term with age, origin, status, place or a date."

Usage:
    python tasks/scan_person_generalization.py --self-test
    python tasks/scan_person_generalization.py [--transcript <path>] [--hours 24] [--strict]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Health terms: condition, genetics, modulators, clinical endpoints
HEALTH_PATTERNS = [
    # Conditions
    r"\bcystic[- ]fibrosis\b",
    r"\bcf\s+(?:patient|carrier|disease|care|cohort|registry|community)\b",
    r"\bcftr\b",
    r"\bbronchiectasis\b",
    r"\bpseudomonas\b",
    r"\bburkholderia\b",
    r"\bpancreatic insufficiency\b",
    r"\bmeconium ileus\b",
    # Genetics & mutations
    r"\bf508del\b",
    r"\bdeltaf508\b",
    r"\bw1282x\b",
    r"\bg542x\b",
    r"\bn1303k\b",
    r"\bg551d\b",
    r"\br117h\b",
    r"\bmutat(?:ion|ions|ed)\b",
    r"\bgenotype\b",
    r"\bhomozyg(?:ous|ote)\b",
    r"\bheterozyg(?:ous|ote)\b",
    r"\bnonsense mutat(?:ion|ions)\b",
    # Modulators & therapies
    r"\btrikafta\b",
    r"\bkalydeco\b",
    r"\borkambi\b",
    r"\bsymdeko\b",
    r"\balyftrek\b",
    r"\bivacaftor\b",
    r"\btezacaftor\b",
    r"\belexacaftor\b",
    r"\bvanzacaftor\b",
    r"\bdeutivacaftor\b",
    r"\bpulmozyme\b",
    r"\bdornase alfa\b",
    r"\btobramycin\b",
    r"\bcayston\b",
    r"\baztreonam\b",
    # Clinical endpoints & measures
    r"\bfev1\b",
    r"\bppfev1\b",
    r"\bfvc\b",
    r"\bsweat[- ]chloride\b",
    r"\bsweat[- ]test\b",
    r"\bsputum culture\b",
    r"\blung transplant\b",
]

# Personal attribute categories
ATTRIBUTE_PATTERNS: Dict[str, List[str]] = {
    "age": [
        r"\b\d{1,2}[- ]year[- ]olds?\b",
        r"\bage[ds]?\s*\d{1,2}\b",
        r"\b\d{1,2}[- ]*(?:yo|y/o|yr[- ]old)\b",
        r"\b(?:child|children|pediatric|paediatric|infant|toddler|teenager|adolescent|newborn|baby|preschooler|elderly)\b",
    ],
    "origin": [
        r"\b(?:caucasian|hispanic|latino|latina|latinx|ashkenazi|african[- ]american|black|white|asian|native american|indigenous|pacific islander|jewish|middle eastern)\b",
        r"\b(?:mexican|canadian|american|british|irish|french|german|italian|spanish|australian)\b",
    ],
    "status": [
        r"\b(?:pregnant|pregnancy|post[- ]transplant|transplant recipient|transplanted|inpatient|outpatient|admitted|admission|discharged|post[- ]op|postoperative|hospitalized|hospitalised|deceased|icu|nicu|palliative|hospice|wheelchair|ventilator|tracheostomy|(?:newly\s+|recently\s+)?diagnosed)\b",
    ],
    "place": [
        r"\b(?:hospital|clinic|center|centre|infirmary|sanatorium|ward)\b",
        r"\b(?:seattle|boston|toronto|vancouver|montreal|chicago|london|paris|denver|philadelphia|houston|atlanta|los angeles|san francisco|cleveland|baltimore|cincinnati|miami|san diego|dallas)\b",
        r"\b(?:alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)\b",
    ],
    "date": [
        r"\b(?:19\d\d|20\d\d)[-/]\d{1,2}[-/]\d{1,2}\b",
        r"\b\d{1,2}[-/]\d{1,2}[-/](?:19\d\d|20\d\d)\b",
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+(?:19\d\d|20\d\d)\b",
        r"\b\d{1,2}(?:st|nd|rd|th)?\s+of\s+(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?),?\s+(?:19\d\d|20\d\d)\b",
        r"\bborn\s+(?:in|on)\s+(?:19\d\d|20\d\d)\b",
    ],
}

COMPILED_HEALTH = [re.compile(p, re.I) for p in HEALTH_PATTERNS]
COMPILED_ATTRIBUTES = {
    cat: [re.compile(p, re.I) for p in pats]
    for cat, pats in ATTRIBUTE_PATTERNS.items()
}

WEB_TOOL_NAMES = {
    "search_web",
    "read_url_content",
    "fetch_web_page",
    "web_search",
    "google_search",
    "read_browser_page",
    "WebFetch",
    "fetch",
}


def analyze_text(text: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """Analyze text for health terms and personal attributes.

    Returns (matched_health_terms, matched_attributes_by_category).
    """
    matched_health = []
    for pat in COMPILED_HEALTH:
        m = pat.search(text)
        if m:
            matched_health.append(m.group(0).lower())

    matched_attrs: Dict[str, List[str]] = {}
    for cat, pats in COMPILED_ATTRIBUTES.items():
        cat_matches = []
        for pat in pats:
            m = pat.search(text)
            if m:
                cat_matches.append(m.group(0).lower())
        if cat_matches:
            matched_attrs[cat] = sorted(list(set(cat_matches)))

    return sorted(list(set(matched_health))), matched_attrs


def check_violation(text: str) -> Optional[Dict[str, Any]]:
    """Return violation details if text combines a health term with personal attributes."""
    health_terms, attributes = analyze_text(text)
    if health_terms and attributes:
        return {
            "health_terms": health_terms,
            "attributes": attributes,
            "categories": sorted(list(attributes.keys())),
            "violation": "Combines health term with personal attribute(s): " + ", ".join(sorted(attributes.keys())),
        }
    return None


def extract_web_tool_inputs(step: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract tool input strings from a transcript step."""
    inputs = []
    step_index = step.get("step_index", 0)

    tool_calls = step.get("tool_calls", [])
    if isinstance(tool_calls, list):
        for tc in tool_calls:
            if not isinstance(tc, dict):
                continue
            name = tc.get("name", "")
            args = tc.get("args", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            elif not isinstance(args, dict):
                args = {}

            if name in WEB_TOOL_NAMES or any(w in name.lower() for w in ["search", "web", "fetch", "url", "browser"]):
                for key in ["query", "Url", "url", "text", "q", "search_term", "domain"]:
                    val = args.get(key)
                    if isinstance(val, str) and val.strip():
                        inputs.append({
                            "step_index": step_index,
                            "tool_name": name,
                            "parameter": key,
                            "content": val.strip(),
                        })
            elif name == "run_command":
                cmd = args.get("CommandLine", "")
                if isinstance(cmd, str) and any(k in cmd.lower() for k in ["curl", "Invoke-WebRequest", "Invoke-RestMethod"]):
                    inputs.append({
                        "step_index": step_index,
                        "tool_name": "run_command",
                        "parameter": "CommandLine",
                        "content": cmd,
                    })

    return inputs


def scan_transcript_for_person_queries(transcript_path: Path) -> List[Dict[str, Any]]:
    """Scan a transcript.jsonl file for web-tool inputs violating person generalization."""
    findings = []
    if not transcript_path.is_file():
        return findings

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    step = json.loads(line)
                except Exception:
                    continue

                tool_inputs = extract_web_tool_inputs(step)
                for inp in tool_inputs:
                    violation = check_violation(inp["content"])
                    if violation:
                        findings.append({
                            "transcript": str(transcript_path),
                            "step_index": inp["step_index"],
                            "tool_name": inp["tool_name"],
                            "parameter": inp["parameter"],
                            "content_snippet": inp["content"][:200],
                            "health_terms": violation["health_terms"],
                            "attributes": violation["attributes"],
                            "categories": violation["categories"],
                            "rule": "T-0109 person-generalization",
                        })
    except Exception as e:
        findings.append({"transcript": str(transcript_path), "error": str(e)})

    return findings


def scan_recent_sessions(brain_dir: Path, max_age_hours: float = 24.0) -> List[Dict[str, Any]]:
    """Scan recent transcripts under brain_dir."""
    findings = []
    if not brain_dir.is_dir():
        return findings

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=max_age_hours)
    real_brain = brain_dir.resolve()

    for session_dir in brain_dir.iterdir():
        if not session_dir.is_dir() or session_dir.is_symlink():
            continue
        transcript_path = session_dir / ".system_generated" / "logs" / "transcript.jsonl"
        if not transcript_path.is_file() or transcript_path.is_symlink():
            continue

        try:
            if not transcript_path.resolve().is_relative_to(real_brain):
                continue
            mtime = datetime.datetime.fromtimestamp(transcript_path.stat().st_mtime, tz=datetime.timezone.utc)
            if mtime < cutoff:
                continue
        except Exception:
            continue

        session_findings = scan_transcript_for_person_queries(transcript_path)
        findings.extend(session_findings)

    return findings


def run_self_test() -> bool:
    """Deterministic self-test validating positive and negative controls."""
    print("Running scan_person_generalization self-test...")

    # Negative controls (clean generalized queries must NOT trigger violation)
    clean_queries = [
        "CFTR gating mutations potentiator response",
        "Trikafta liver enzyme monitoring guidelines",
        "Ivacaftor pharmacokinetics and sweat chloride reduction in clinical trials",
        "Nonsense mutation readthrough compounds in cystic fibrosis",
        "Pulmonary exacerbation rates with elexacaftor tezacaftor ivacaftor",
        "Pseudomonas aeruginosa bacteriophage therapy co-evolution dynamics",
        "Weather forecast Seattle Washington",
        "Python datetime formatting examples",
    ]
    for q in clean_queries:
        res = check_violation(q)
        if res is not None:
            print(f"FAIL: Clean query falsely flagged as violation: '{q}' -> {res}")
            return False

    # Positive controls (violating queries combining health + attribute MUST trigger)
    violating_cases = [
        ("14-year-old cystic fibrosis FEV1 decline", ["age"]),
        ("Seattle children's hospital Trikafta protocol", ["place"]),
        ("pregnant CF patient Kalydeco safety data", ["status"]),
        ("Ashkenazi Jewish W1282X mutation carrier screening", ["origin"]),
        ("diagnosed with cystic fibrosis on 2024-03-15", ["date"]),
        ("infant newborn diagnosed with CFTR F508del in Boston clinic", ["age", "place", "status"]),
    ]
    for q, expected_cats in violating_cases:
        res = check_violation(q)
        if res is None:
            print(f"FAIL: Violating query was NOT flagged: '{q}'")
            return False
        for exp in expected_cats:
            if exp not in res["categories"]:
                print(f"FAIL: Expected category '{exp}' not detected in '{q}'. Detected: {res['categories']}")
                return False

    # Positive control: Synthetic transcript
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_transcript = Path(tmpdir) / "transcript.jsonl"
        lines = [
            json.dumps({
                "step_index": 1,
                "type": "PLANNER_RESPONSE",
                "tool_calls": [
                    {"name": "search_web", "args": {"query": "CFTR potentiator mechanisms"}}
                ]
            }),
            json.dumps({
                "step_index": 2,
                "type": "PLANNER_RESPONSE",
                "tool_calls": [
                    {"name": "search_web", "args": {"query": "12-year-old child cystic fibrosis Trikafta dose in Toronto"}}
                ]
            }),
        ]
        tmp_transcript.write_text("\n".join(lines), encoding="utf-8")

        transcript_findings = scan_transcript_for_person_queries(tmp_transcript)
        if len(transcript_findings) != 1:
            print(f"FAIL: Expected 1 violation from synthetic transcript, got {len(transcript_findings)}")
            return False
        if transcript_findings[0]["step_index"] != 2:
            print(f"FAIL: Expected violation at step 2, got {transcript_findings[0]['step_index']}")
            return False
        if "age" not in transcript_findings[0]["categories"] or "place" not in transcript_findings[0]["categories"]:
            print(f"FAIL: Expected age and place categories, got {transcript_findings[0]['categories']}")
            return False

    print("ALL SELF-TESTS PASSED (clean queries clean, composite queries caught, synthetic transcript verified).")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan sessions for queries combining health terms with personal attributes.")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic positive/negative control self-tests.")
    parser.add_argument("--transcript", type=Path, help="Specific transcript.jsonl file to scan.")
    parser.add_argument("--brain-dir", type=Path, default=Path(os.environ.get("ANTIGRAVITY_BRAIN_DIR", str(Path.home() / ".gemini" / "antigravity" / "brain"))), help="Brain directory containing session transcripts.")
    parser.add_argument("--hours", type=float, default=24.0, help="Hours of history to scan under brain-dir.")
    parser.add_argument("--query", type=str, help="Single query text to inspect.")
    parser.add_argument("--strict", action="store_true", help="Exit 1 if any violating queries are found.")
    parser.add_argument("--json", action="store_true", help="Output JSON results.")

    args = parser.parse_args()

    if args.self_test:
        success = run_self_test()
        return 0 if success else 1

    if args.query:
        res = check_violation(args.query)
        if res:
            print(f"VIOLATION: Query combines health terms {res['health_terms']} with attributes {res['attributes']}")
            return 1 if args.strict else 0
        else:
            print("OK: Query does not combine health terms with personal attributes.")
            return 0

    findings = []
    if args.transcript:
        findings = scan_transcript_for_person_queries(args.transcript)
    else:
        findings = scan_recent_sessions(args.brain_dir, max_age_hours=args.hours)

    if args.json:
        print(json.dumps({"total_violations": len(findings), "violations": findings}, indent=2))
    else:
        print(f"Session Close Scan: {len(findings)} violating web-tool inputs found.")
        for f in findings:
            print(f"  Step {f.get('step_index')}: [{f.get('tool_name')}] {f.get('content_snippet')}")
            print(f"    Health: {f.get('health_terms')} | Attributes: {f.get('attributes')}")

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
