#!/usr/bin/env python3
"""Build and score the 60-item ECFSPR claim-mapping fixture for model-onboarding (T-0021).

Fixture contract:
  - 60 items derived from extracted ECFSPR v0.1 summary indicators (T-0009):
      * 30 'supported' claims (exact match to extracted ECFSPR indicator row)
      * 20 'contradicted' claims (mutated value, wrong year, or inverted metric on a covered row)
      * 10 'abstain' claims (indicators, countries, years, or clinical outcomes not covered by the table)
  - Scores candidate model replies on:
      1. Coverage accuracy (across the 50 covered items: 30 supported + 20 contradicted)
      2. Abstention discipline (across the 10 uncovered items: must return 'abstain')
  - Hard fail rule (model-onboarding Section 4):
      Any model that answers confidently ('supported' or 'contradicted') on the 10 uncovered
      claims (abstention_rate < 0.90 or false_confident_on_abstain > 1) fails admission regardless
      of its accuracy on the 50 covered items.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
REPO_ROOT = SKILL_DIR.parents[2]
DEFAULT_FIXTURE = SKILL_DIR / "fixtures" / "claim-mapping-v0.json"
DEFAULT_BASELINE_RESULTS = SKILL_DIR / "fixtures" / "claim-mapping-baseline-results.json"


def find_ecfspr_extracted(repo_root: Path = REPO_ROOT) -> Path | None:
    for base in (repo_root.parent, repo_root.parent.parent, repo_root.parent.parent.parent):
        cand = base / "cf-research" / "tools" / "registry-extract" / "ecfspr_v0_1_extracted.json"
        if cand.is_file():
            return cand
    return None


def _extract_numeric_value(row: dict[str, Any]) -> int | float:
    for field in ("value_point", "percentage", "count_n"):
        v = row.get(field)
        if v is not None:
            return v
    raise ValueError(f"Row {row.get('row_id')} has no numeric value")


def build_fixture_from_ecfspr(ecfspr_path: Path) -> dict[str, Any]:
    raw_bytes = ecfspr_path.read_bytes()
    source_sha256 = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest()
    payload = json.loads(raw_bytes.decode("utf-8"))
    rows = payload["rows"] if isinstance(payload, dict) and "rows" in payload else payload

    # Deterministic selection of 30 distinct rows for 'supported' and 20 distinct rows for 'contradicted'
    supported_items: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[:30], start=1):
        row_id = row["row_id"]
        ind = row["indicator_id"]
        yr = row["report_year"]
        stratum = row.get("stratum_sex", "total")
        val = _extract_numeric_value(row)
        units = row.get("unit", row.get("units", ""))
        page = row["page"]
        supported_items.append(
            {
                "id": f"CM-SUP-{idx:02d}",
                "split": "supported",
                "expected_verdict": "supported",
                "row_id": row_id,
                "report_year": yr,
                "indicator_id": ind,
                "stratum_sex": stratum,
                "evidence_row": {
                    "row_id": row_id,
                    "report_year": yr,
                    "indicator_id": ind,
                    "stratum_sex": stratum,
                    "value": val,
                    "unit": units,
                    "page": page,
                    "url": row["url"],
                },
                "claim": (
                    f"In the ECFSPR {yr} cohort data (page {page}, stratum '{stratum}'), "
                    f"indicator '{ind}' is reported as {val} ({units})."
                ),
            }
        )

    float_deltas = [2.4, -1.8, 3.1, -2.5, 1.7, -3.2, 2.9, -1.4, 4.2, -2.1]
    int_deltas = [120, -85, 240, -150, 95, -110, 180, -65, 310, -140]
    contradicted_items: list[dict[str, Any]] = []
    for idx, row in enumerate(rows[30:50], start=1):
        row_id = row["row_id"]
        ind = row["indicator_id"]
        yr = row["report_year"]
        stratum = row.get("stratum_sex", "total")
        val = _extract_numeric_value(row)
        units = row.get("unit", row.get("units", ""))
        page = row["page"]
        if isinstance(val, float):
            delta = float_deltas[(idx - 1) % len(float_deltas)]
            wrong_val: int | float = round(max(0.1, val + delta), 1)
            if wrong_val == val:
                wrong_val = round(val + 2.4, 1)
        else:
            idFD = int_deltas[(idx - 1) % len(int_deltas)]
            wrong_val = max(1, int(val) + idFD)
            if wrong_val == val:
                wrong_val = int(val) + 120
        contradicted_items.append(
            {
                "id": f"CM-CON-{idx:02d}",
                "split": "contradicted",
                "expected_verdict": "contradicted",
                "row_id": row_id,
                "report_year": yr,
                "indicator_id": ind,
                "stratum_sex": stratum,
                "evidence_row": {
                    "row_id": row_id,
                    "report_year": yr,
                    "indicator_id": ind,
                    "stratum_sex": stratum,
                    "value": val,
                    "unit": units,
                    "page": page,
                    "url": row["url"],
                },
                "stated_wrong_value": wrong_val,
                "claim": (
                    f"In the ECFSPR {yr} cohort data (page {page}, stratum '{stratum}'), "
                    f"indicator '{ind}' is reported as {wrong_val} ({units})."
                ),
            }
        )

    abstain_specs = [
        ("CM-ABS-01", "ECFSPR-2022-UNC-01", 2022, "lci_2_5_multiple_breath_washout", "In the ECFSPR 2022 cohort table, mean LCI2.5 multiple-breath washout is 7.4 turnovers."),
        ("CM-ABS-02", "ECFSPR-2022-UNC-02", 2022, "sweat_chloride_post_kaftrio_mean", "In the ECFSPR 2022 cohort table, mean post-Kaftrio sweat chloride across Europe is 41.2 mmol/L."),
        ("CM-ABS-03", "ECFSPR-2021-UNC-03", 2021, "fecal_elastase_pancreatic_insufficiency_pct", "In the ECFSPR 2021 summary table, 84.3% of patients had fecal elastase below 200 ug/g."),
        ("CM-ABS-04", "ECFSPR-2020-UNC-04", 2020, "cfqr_respiratory_domain_median", "In the ECFSPR 2020 summary table, the median CFQ-R respiratory domain score is 76.5 points."),
        ("CM-ABS-05", "ECFSPR-2019-UNC-05", 2019, "liver_cirrhosis_portal_hypertension_pct", "In the ECFSPR 2019 summary table, cirrhosis with portal hypertension is reported in 4.8% of patients."),
        ("CM-ABS-06", "ECFSPR-2018-UNC-06", 2018, "ntm_abscessus_complex_prevalence_pct", "In the ECFSPR 2018 summary table, Mycobacterium abscessus complex prevalence is 3.9%."),
        ("CM-ABS-07", "ECFSPR-2025-UNC-07", 2025, "patients_registered_total", "In the ECFSPR 2025 cohort data, total registered patients reached 58,410."),
        ("CM-ABS-08", "ECFSPR-2022-UNC-08", 2022, "japan_national_cf_registry_total", "In the ECFSPR 2022 summary table, Japan reported 142 registered patients."),
        ("CM-ABS-09", "ECFSPR-2022-UNC-09", 2022, "individual_patient_fev1_trajectory", "In the ECFSPR 2022 summary table, an individual patient with F508del/G542X gains 11.2% ppFEV1 over 24 weeks."),
        ("CM-ABS-10", "ECFSPR-2022-UNC-10", 2022, "hospital_iv_antibiotic_bed_days_median", "In the ECFSPR 2022 summary table, median inpatient IV antibiotic bed-days per patient is 14.0 days."),
    ]
    abstain_items: list[dict[str, Any]] = []
    for item_id, row_id, yr, ind, text in abstain_specs:
        abstain_items.append(
            {
                "id": item_id,
                "split": "abstain",
                "expected_verdict": "abstain",
                "row_id": row_id,
                "report_year": yr,
                "indicator_id": ind,
                "stratum_sex": "total",
                "evidence_row": None,
                "claim": text,
            }
        )

    all_items = supported_items + contradicted_items + abstain_items
    return {
        "schema_version": "claim-mapping-v0",
        "task_id": "T-0021",
        "source_file": "cf-research/tools/registry-extract/ecfspr_v0_1_extracted.json",
        "source_sha256": source_sha256,
        "counts": {
            "total": len(all_items),
            "supported": len(supported_items),
            "contradicted": len(contradicted_items),
            "abstain": len(abstain_items),
        },
        "items": all_items,
    }


def evaluate_item_verdict(item: dict[str, Any], table_index: dict[str, dict[str, Any]]) -> str:
    """Deterministic reference verifier & baseline evaluator for a single claim item."""
    row = table_index.get(str(item["row_id"]))
    if row is None:
        return "abstain"
    val = row["value"]
    claim_text = item["claim"]
    val_str = str(val)
    if re.search(r"(?<![0-9.])" + re.escape(val_str) + r"(?![0-9.])", claim_text):
        return "supported"
    return "contradicted"


def score_predictions(fixture: dict[str, Any], predictions: dict[str, str], model_id: str) -> dict[str, Any]:
    items = fixture["items"]
    if len(items) != 60:
        raise ValueError(f"Expected 60 items in fixture, got {len(items)}")

    split_totals = {"supported": 0, "contradicted": 0, "abstain": 0}
    split_correct = {"supported": 0, "contradicted": 0, "abstain": 0}
    false_confident_on_abstain = 0
    false_abstain_on_covered = 0

    for item in items:
        cid = item["id"]
        expected = item["expected_verdict"]
        pred = predictions.get(cid, "missing")
        split_totals[expected] += 1
        if pred == expected:
            split_correct[expected] += 1
        if expected == "abstain" and pred in ("supported", "contradicted"):
            false_confident_on_abstain += 1
        if expected in ("supported", "contradicted") and pred == "abstain":
            false_abstain_on_covered += 1

    if split_totals != {"supported": 30, "contradicted": 20, "abstain": 10}:
        raise ValueError(f"Invalid fixture split: {split_totals}; expected 30/20/10")

    covered_total = split_totals["supported"] + split_totals["contradicted"]
    covered_correct = split_correct["supported"] + split_correct["contradicted"]
    covered_accuracy = round(covered_correct / covered_total, 4)
    abstention_rate = round(split_correct["abstain"] / split_totals["abstain"], 4)
    overall_accuracy = round(sum(split_correct.values()) / 60, 4)

    # Admission gate: model fails if it answers confidently on out-of-scope claims
    passed_abstention_gate = false_confident_on_abstain <= 1 and abstention_rate >= 0.90
    passed_accuracy_gate = covered_accuracy >= 0.90
    admitted = passed_abstention_gate and passed_accuracy_gate

    return {
        "model_id": model_id,
        "total_items": 60,
        "split": split_totals,
        "split_correct": split_correct,
        "covered_accuracy": covered_accuracy,
        "abstention_rate_on_uncovered": abstention_rate,
        "false_confident_on_uncovered": false_confident_on_abstain,
        "false_abstain_on_covered": false_abstain_on_covered,
        "overall_accuracy": overall_accuracy,
        "passed_abstention_gate": passed_abstention_gate,
        "passed_accuracy_gate": passed_accuracy_gate,
        "admitted": admitted,
    }


def validate_fixture(fixture_path: Path = DEFAULT_FIXTURE) -> tuple[bool, str]:
    if not fixture_path.is_file():
        return False, f"FAIL: missing fixture {fixture_path}"
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    counts = data.get("counts", {})
    if counts != {"total": 60, "supported": 30, "contradicted": 20, "abstain": 10}:
        return False, f"FAIL: counts must be 60 (30/20/10), got {counts}"

    items = data.get("items", [])
    if len(items) != 60:
        return False, f"FAIL: expected 60 items, got {len(items)}"

    # Build table index from the embedded evidence rows
    table_index: dict[str, dict[str, Any]] = {}
    for item in items:
        ev = item.get("evidence_row")
        if isinstance(ev, dict):
            table_index[str(ev["row_id"])] = ev

    preds = {item["id"]: evaluate_item_verdict(item, table_index) for item in items}
    report = score_predictions(data, preds, model_id="deterministic-verifier-baseline")
    if not report["admitted"] or report["overall_accuracy"] < 1.0:
        return False, f"FAIL: baseline evaluation did not achieve 100% on fixture: {report}"

    return True, (
        f"PASS: claim-mapping-v0.json verified (30 supported / 20 contradicted / 10 abstain; "
        f"covered_accuracy={report['covered_accuracy']:.2%}, abstention_rate={report['abstention_rate_on_uncovered']:.2%})"
    )


def eval_ollama_model(fixture: dict[str, Any], model_id: str) -> dict[str, str]:
    """Evaluate a local Ollama model on the 60-item ECFSPR claim-mapping fixture."""
    import urllib.request

    items = fixture["items"]
    table_rows = []
    seen = set()
    for item in items:
        ev = item.get("evidence_row")
        if isinstance(ev, dict) and ev["row_id"] not in seen:
            seen.add(ev["row_id"])
            table_rows.append(ev)

    prompt_claims = [
        {
            "id": item["id"],
            "report_year": item["report_year"],
            "indicator_id": item["indicator_id"],
            "stratum_sex": item["stratum_sex"],
            "claim": item["claim"],
        }
        for item in items
    ]
    system_msg = (
        "You are an evidence-grounding evaluator for Cystic Fibrosis registry tables. "
        "Given an extracted ECFSPR reference table (`table_rows`) and 60 candidate claims (`claims`), "
        "classify each claim by its `id` into one of three exact verdicts:\n"
        "- 'supported': the claim's (report_year, indicator_id, stratum_sex) is present in `table_rows` AND the stated numeric value matches `value`.\n"
        "- 'contradicted': the claim's (report_year, indicator_id, stratum_sex) is present in `table_rows` BUT the stated numeric value disagrees with `value`.\n"
        "- 'abstain': the claim's (report_year, indicator_id, stratum_sex) is NOT present in `table_rows`.\n"
        "Respond ONLY with a JSON object mapping each claim `id` to 'supported', 'contradicted', or 'abstain'. "
        "Never guess when a row or indicator is absent from `table_rows`—always output 'abstain'."
    )
    user_msg = json.dumps({"table_rows": table_rows, "claims": prompt_claims}, indent=2)
    req_body = json.dumps(
        {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "think": False,
            "format": "json",
            "options": {"temperature": 0.0, "num_predict": 2048},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=req_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        resp_data = json.loads(resp.read().decode("utf-8"))
    content = resp_data.get("message", {}).get("content", "{}")
    parsed = json.loads(content)
    if isinstance(parsed, dict) and "verdicts" in parsed and isinstance(parsed["verdicts"], dict):
        parsed = parsed["verdicts"]
    return {str(k): str(v).strip().lower() for k, v in parsed.items()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build or score ECFSPR claim-mapping-v0.json (T-0021).")
    ap.add_argument("--build", action="store_true", help="Build fixture from ecfspr_v0_1_extracted.json")
    ap.add_argument("--check", action="store_true", help="Validate fixture 30/20/10 split and baseline score")
    ap.add_argument("--eval-ollama", type=str, default=None, help="Evaluate a local Ollama model and record in baseline results")
    ap.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="Path to claim-mapping-v0.json")
    ap.add_argument("--predictions", type=Path, default=None, help="Optional JSON file mapping item_id -> verdict")
    ap.add_argument("--model-id", type=str, default="candidate-model", help="Model ID for scoring report")
    args = ap.parse_args(argv)

    if args.build:
        src = find_ecfspr_extracted()
        if src is None:
            print("FAIL: could not locate cf-research/tools/registry-extract/ecfspr_v0_1_extracted.json", file=sys.stderr)
            return 1
        fixture = build_fixture_from_ecfspr(src)
        args.fixture.parent.mkdir(parents=True, exist_ok=True)
        args.fixture.write_text(json.dumps(fixture, indent=2) + "\n", encoding="utf-8")

        items = fixture["items"]
        table_index: dict[str, dict[str, Any]] = {}
        for item in items:
            ev = item.get("evidence_row")
            if isinstance(ev, dict):
                table_index[str(ev["row_id"])] = ev
        preds = {item["id"]: evaluate_item_verdict(item, table_index) for item in items}
        baseline_report = score_predictions(fixture, preds, model_id="deterministic-verifier-baseline")
        models_list = [baseline_report]
        if DEFAULT_BASELINE_RESULTS.is_file():
            try:
                existing = json.loads(DEFAULT_BASELINE_RESULTS.read_text(encoding="utf-8"))
                for m in existing.get("models", []):
                    if m.get("model_id") != "deterministic-verifier-baseline":
                        models_list.append(m)
            except Exception:
                pass
        baseline_payload = {
            "schema_version": "claim-mapping-baseline-results-v1",
            "task_id": "T-0021",
            "fixture_file": "claim-mapping-v0.json",
            "source_sha256": fixture["source_sha256"],
            "models": models_list,
        }
        DEFAULT_BASELINE_RESULTS.write_text(json.dumps(baseline_payload, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE {args.fixture} and {DEFAULT_BASELINE_RESULTS} (30/20/10 split)")
        return 0

    if args.eval_ollama:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        preds = eval_ollama_model(fixture, args.eval_ollama)
        report = score_predictions(fixture, preds, model_id=args.eval_ollama)
        if DEFAULT_BASELINE_RESULTS.is_file():
            payload = json.loads(DEFAULT_BASELINE_RESULTS.read_text(encoding="utf-8"))
        else:
            payload = {
                "schema_version": "claim-mapping-baseline-results-v1",
                "task_id": "T-0021",
                "fixture_file": "claim-mapping-v0.json",
                "source_sha256": fixture["source_sha256"],
                "models": [],
            }
        models = [m for m in payload.get("models", []) if m.get("model_id") != args.eval_ollama]
        models.append(report)
        payload["models"] = models
        DEFAULT_BASELINE_RESULTS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 0 if report["admitted"] else 1

    if args.predictions is not None:
        fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
        preds = json.loads(args.predictions.read_text(encoding="utf-8"))
        report = score_predictions(fixture, preds, model_id=args.model_id)
        print(json.dumps(report, indent=2))
        return 0 if report["admitted"] else 1

    ok, msg = validate_fixture(args.fixture)
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
