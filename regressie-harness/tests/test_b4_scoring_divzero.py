"""Regression check for finite scores when no tags are present.

The resolved bug produced numpy nan rather than raising ZeroDivisionError.
Check finiteness explicitly: a float type check would also accept nan."""
from __future__ import annotations

import math

import pandas as pd
import pytest

scoring = pytest.importorskip(
    "anonymizer.helpers.scoring.scoring",
    reason="source repository or runtime dependencies unavailable",
)


@pytest.mark.b4_redgreen
def test_scoring_handles_zero_division():
    # One row without tags, false positives or false negatives: tp + fp == 0.
    df = pd.DataFrame(
        {
            "Geanonimiseerde tekst": ["geen enkele tag in deze tekst"],
            "# Onterecht gemaskeerd": [0],
            "# Gemiste maskeringen": [0],
        }
    )
    result = scoring.score(
        df, "Geanonimiseerde tekst", "# Onterecht gemaskeerd", "# Gemiste maskeringen"
    )
    assert math.isfinite(result["precision"]), "precision must be finite (no nan/inf)"
    assert math.isfinite(result["recall"]), "recall must be finite (no nan/inf)"
    assert math.isfinite(result["f_beta"]), "f_beta must be finite (no nan/inf)"
