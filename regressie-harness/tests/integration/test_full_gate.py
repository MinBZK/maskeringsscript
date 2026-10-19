"""Explicit offline model test, excluded from default collection."""
import pytest
from harness_config import HERE
from scorecard import compute, _gate


@pytest.mark.integration
def test_full_pipeline_gold_gate():
    assert _gate(compute(full=True), HERE / 'baseline-v2.json', 0, strict_ner=True) == 0
