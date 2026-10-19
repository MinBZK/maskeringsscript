"""Exact characterization of the regex pass on 952 synthetic texts.

Compare current output with the reviewed snapshot. The snapshot preserves
behavior, including existing mistakes; it is not a correctness gold set.
Model coverage is checked separately and is not part of this exact snapshot.
Only use SNAPSHOT_UPDATE=1 for an intentional, separately reviewed update."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SNAP = HERE.parent / "snapshots" / "regex_baseline.json"

anonymizer = pytest.importorskip(
    "anonymizer.anonymizer", reason="source repository or runtime dependencies unavailable"
)


def _current_outputs(records):
    rx = anonymizer.RegexAnonymizer()  # No files or model needed.
    return {r["id"]: rx(r["text"]) for r in records}


def test_regex_snapshot(snapshot_records):
    current = _current_outputs(snapshot_records)

    if os.environ.get("SNAPSHOT_UPDATE"):
        SNAP.parent.mkdir(parents=True, exist_ok=True)
        SNAP.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        pytest.skip(f"baseline written: {SNAP} -- review before committing")

    if not SNAP.exists():
        pytest.fail(
            "No baseline. Create one explicitly with: SNAPSHOT_UPDATE=1 pytest "
            f"{Path(__file__).name}  -- review before committing {SNAP}"
        )

    baseline = json.loads(SNAP.read_text(encoding="utf-8"))

    diffs = {
        k: (baseline.get(k), current.get(k))
        for k in set(baseline) | set(current)
        if baseline.get(k) != current.get(k)
    }
    assert not diffs, (
        "Regex output differs from the baseline; review the differences before using SNAPSHOT_UPDATE=1:\n"
        + "\n".join(
            f"  [{k}]\n    was: {b!r}\n    now: {c!r}" for k, (b, c) in sorted(diffs.items())
        )
    )
