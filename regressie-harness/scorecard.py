#!/usr/bin/env python3
"""Annotated source-span masking coverage, with conservative fragment detection.

This is not a population recall or precision estimate. Unsupported output
rewrites count as indeterminate, never as fully masked. NER gates are advisory
unless --strict-ner is supplied. Legacy v1 baselines are incompatible.
"""
from __future__ import annotations

import argparse
import math

from coverage_eval import METRIC, assess_record
from harness_config import repo_root, model_root, load_anonymizer
from measurement import capture_inputs, record_measurement, utc_now
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "synthetic_signals.jsonl"
NER_PASSES = {"ner"}


def _repo_root() -> Path:
    return repo_root()


def _load_records():
    recs = []
    with DATA.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    if not recs:
        raise ValueError("Empty gold set")
    return recs


def _build_masker(full: bool, repo: Path):
    model_path = model_root() if full else None
    A = load_anonymizer(repo)

    # Resolve list paths independently of the working directory.
    # Prefer bundled package data; retain the legacy root-level layout fallback.
    _list_dirs = [repo / "src" / "anonymizer" / "input_files", repo / "input_files"]
    _list_dir = next((d for d in _list_dirs if (d / "ListClassifier Basic.xlsx").exists()), _list_dirs[-1])
    A.LIST_PATH = str(_list_dir / "ListClassifier Basic.xlsx")
    A.WHITELIST_PATH = str(_list_dir / "Whitelist Basic.xlsx")

    rx = A.RegexAnonymizer()
    la = A.ListAnonymizer()
    if full:
        # Pass regex/list placeholders to NER, matching CombinedAnonymizer.
        extra_weak = list(rx.weak_ner_tags)
        for tag_format in la.weak_ner_tags:
            if tag_format not in extra_weak:
                extra_weak.append(tag_format)
        # The local model and cached backbone are required; never download.
        ner = A.NERAnonymizer(model_name=str(model_path), extra_weak_whitelist=extra_weak)
        return lambda t: ner(la(rx(t)))
    return lambda t: la(rx(t))


def evaluate(records, mask, full=False):
    if not records:
        raise ValueError("Empty gold set")
    ids = [record['id'] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate record ID in the gold set')
    if any(item.get('pass', 'regex') not in {'regex', 'list', 'ner'}
           for record in records for item in record.get('pii', [])):
        raise ValueError('Unknown pass in the gold set')
    return _evaluate(records, mask, full)


def compute(full: bool):
    repo = _repo_root()
    if full:
        model_root()
    load_anonymizer(repo)
    started = utc_now()
    before = capture_inputs(repo, full)
    records = _load_records()
    mask = _build_masker(full, repo)

    card = evaluate(records, mask, full)
    commit = before['git_sha_full']
    card["meta"]["git_sha"] = commit[:7] if commit else None
    card["meta"]["gold_sha256"] = before['sha256']['gold']
    return record_measurement(card, before, capture_inputs(repo, full), started, utc_now())


def _evaluate(records, mask, full):
    per_cat = defaultdict(lambda: {"total": 0, "masked": 0, "residual": [], "passes": set()})
    overmasking = []  # PII-free records that nevertheless receive a tag.

    for r in records:
        text = r["text"]
        out = mask(text)
        if not isinstance(out, str):
            raise ValueError('The masker must return a string')
        for item in assess_record(r, out):
            cat = item["category"]
            val = item["value"]
            pas = item.get("pass", "regex")
            if not full and pas in NER_PASSES:
                continue  # Name/Address require --full.
            per_cat[cat]["total"] += 1
            per_cat[cat]["passes"].add(pas)
            if item["status"] == "fully_masked":
                per_cat[cat]["masked"] += 1
            else:
                per_cat[cat]["residual"].append({"id": r["id"], **item, "out": out})
        if not r.get("pii") and out != text and "<" in out and ">" in out:
            overmasking.append({"id": r["id"], "text": text, "out": out})

    scorecard = {}
    for cat, d in sorted(per_cat.items()):
        recall = d["masked"] / d["total"] if d["total"] else None
        # Categories containing a NER span use the NER gate policy.
        gate_pass = "ner" if (d["passes"] & NER_PASSES) else "regex"
        scorecard[cat] = {
            "support": d["total"],
            "masked": d["masked"],
            "recall": recall,
            "pass": gate_pass,
            "residual_pii": d["residual"],
        }

    meta = {
        "generated": utc_now(),
        "mode": "full" if full else "regex+list",
        "git_sha": None,
        "metric": METRIC,
        "schema_version": 2,
        "records": len(records),
        "note": "Complete masking of synthetic gold spans; recall is a legacy field name, not population recall or precision.",
    }
    return {"meta": meta, "per_category": scorecard, "overmasking_warnings": overmasking}


def _print(card, strict_ner=False):
    m = card["meta"]
    print(
        f"# Scorecard ({m['mode']}, {m['records']} records, git {m['git_sha']}, {m['generated']})"
    )
    print(f"{'category':<16}{'support':>8}{'masked':>8}{'coverage':>9}  {'gate':<6}residual PII")
    for cat, d in card["per_category"].items():
        rec = "n/a" if d["recall"] is None else f"{d['recall']:.2f}"
        gate = "soft" if d.get("pass") in NER_PASSES and not strict_ner else "hard"
        print(f"{cat:<16}{d['support']:>8}{d['masked']:>8}{rec:>9}  {gate:<6}{len(d['residual_pii'])}")
    if card["overmasking_warnings"]:
        ids = ", ".join(w["id"] for w in card["overmasking_warnings"])
        print(
            f"\n[warning] overmasking on {len(card['overmasking_warnings'])} "
            f"PII-free record(s): {ids}"
        )


def _reject_nonfinite_json(value):
    raise ValueError(f'Non-finite JSON number is not allowed: {value}')


def _validate_card(card, label):
    """Reject missing, non-finite or internally inconsistent gate measurements."""
    if not isinstance(card, dict) or not isinstance(card.get('meta'), dict):
        raise ValueError(f'{label}: missing scorecard metadata.')
    meta = card['meta']
    if meta.get('metric') != METRIC or type(meta.get('schema_version')) is not int or meta['schema_version'] != 2:
        raise ValueError(f'{label}: incompatible metric or schema; do not automatically replace a legacy baseline.')
    if meta.get('mode') not in {'full', 'regex+list'}:
        raise ValueError(f'{label}: unsupported evaluation mode.')
    if type(meta.get('records')) is not int or meta['records'] <= 0:
        raise ValueError(f'{label}: records must be a positive integer.')
    categories = card.get('per_category')
    if not isinstance(categories, dict) or not categories:
        raise ValueError(f'{label}: category measurements are missing.')
    for category, data in categories.items():
        if not isinstance(category, str) or not category or not isinstance(data, dict):
            raise ValueError(f'{label}: invalid category measurement.')
        support, masked, recall = (data.get(key) for key in ('support', 'masked', 'recall'))
        if type(support) is not int or support <= 0 or type(masked) is not int or not 0 <= masked <= support:
            raise ValueError(f'{label}/{category}: invalid support or masked count.')
        if type(recall) not in {int, float} or not math.isfinite(recall) or not 0 <= recall <= 1:
            raise ValueError(f'{label}/{category}: recall must be a finite number in [0, 1].')
        if not math.isclose(recall, masked / support, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f'{label}/{category}: recall does not match masked/support.')
        residuals = data.get('residual_pii')
        if not isinstance(residuals, list) or len(residuals) != support - masked or not all(isinstance(r, dict) for r in residuals):
            raise ValueError(f'{label}/{category}: residuals do not match support minus masked.')
        if data.get('pass') not in {'regex', 'ner'} or (meta['mode'] == 'regex+list' and data['pass'] == 'ner'):
            raise ValueError(f'{label}/{category}: invalid pass for the evaluation mode.')


def _gate(card, baseline_path: Path, tol: float, strict_ner: bool = False) -> int:
    """Compare validated coverage; NER is advisory unless explicitly made strict."""
    if type(tol) not in {int, float} or not math.isfinite(tol) or not 0 <= tol <= 1:
        raise ValueError('Tolerance must be a finite number in [0, 1].')
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"), parse_constant=_reject_nonfinite_json)
    _validate_card(baseline, 'Baseline')
    _validate_card(card, 'Candidate')
    if not card['meta'].get('gold_sha256') or card['meta']['gold_sha256'] != baseline['meta'].get('gold_sha256'):
        raise ValueError('The gold set differs from the baseline.')
    if card['meta']['records'] != baseline['meta']['records']:
        raise ValueError('Record count differs from the baseline.')
    base = baseline.get('per_category', {})
    cur = card['per_category']
    expected = {cat for cat, d in base.items()
                if card['meta']['mode'] == 'full' or d['pass'] != 'ner'}
    if not expected or set(cur) != expected:
        raise ValueError('Missing or changed categories in the gate.')
    if card['meta']['mode'] == 'full' and baseline['meta']['mode'] != 'full':
        raise ValueError('A full run requires a full baseline.')
    for cat in expected:
        if cur[cat]['support'] != base[cat]['support'] or cur[cat]['pass'] != base[cat]['pass']:
            raise ValueError('Support or pass differs: ' + cat)
    hard_regressions = []
    soft_warnings = []
    for cat, d in cur.items():
        b = base[cat]['recall']
        if d["recall"] < b - tol:
            is_soft = (d.get("pass") in NER_PASSES) and not strict_ner
            (soft_warnings if is_soft else hard_regressions).append((cat, b, d["recall"]))

    if soft_warnings:
        print("WARNING -- reduced NER coverage (advisory; gold has not been independently validated):")
        for cat, b, c in soft_warnings:
            print(f"  {cat}: {b:.2f} -> {c:.2f}")
    if hard_regressions:
        print("REGRESSION -- deterministic masking coverage below baseline:")
        for cat, b, c in hard_regressions:
            print(f"  {cat}: {b:.2f} -> {c:.2f}")
        return 1
    ner_note = "NER enforced" if strict_ner else "NER advisory only"
    print(f"OK -- no hard masking-coverage regression against baseline (tolerance={tol}; {ner_note}).")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--full", action="store_true", help="include the NER pass (requires a local GLiNER model)")
    ap.add_argument("--save", metavar="PATH", help="write the scorecard to JSON")
    ap.add_argument(
        "--gate", metavar="PATH", help="compare with a baseline JSON; exit 1 on a hard coverage regression"
    )
    ap.add_argument(
        "--tolerance", type=float, default=0.0, help="permitted masking-coverage decrease per category"
    )
    ap.add_argument(
        "--strict-ner",
        action="store_true",
        help="also enforce NER coverage (Name/Address/Organisation) as a hard gate",
    )
    args = ap.parse_args()

    if not 0 <= args.tolerance <= 1:
        ap.error("tolerance must be between 0 and 1")
    if args.save and args.gate and Path(args.save).resolve() == Path(args.gate).resolve():
        ap.error("--save and --gate must not refer to the same file")
    card = compute(full=args.full)
    _print(card, strict_ner=args.strict_ner)

    result = _gate(card, Path(args.gate), args.tolerance, strict_ner=args.strict_ner) if args.gate else 0
    if args.save:
        Path(args.save).write_text(
            json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nscorecard written: {args.save}")
    return result


if __name__ == "__main__":
    sys.exit(main())
