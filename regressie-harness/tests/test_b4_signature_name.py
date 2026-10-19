"""Regression checks for the resolved signature-name masking gap.

Two synthetic corpus cases contained an initial and surname after a closing
greeting. The deterministic sign-off rule now masks these names. Negative
cases guard against masking ordinary text after greetings."""
from __future__ import annotations

import pytest

anonymizer = pytest.importorskip(
    "anonymizer.anonymizer", reason="source repository or runtime dependencies unavailable"
)

# Literal signature tails from two confirmed synthetic cases.
SIGN_OFF_CASES = [
    ("WIM-0106", "Groet,\nM. Akkerman"),
    ("WIM-0293", "Met vriendelijke groet,\nR. Akkerman"),
]


@pytest.mark.b4_redgreen
@pytest.mark.parametrize("rid,tail", SIGN_OFF_CASES, ids=[c[0] for c in SIGN_OFF_CASES])
def test_signature_name_is_masked(rid, tail):
    rx = anonymizer.RegexAnonymizer()
    out = rx(tail)
    assert "Akkerman" not in out, f"{rid}: sender name remains visible in the signature"
    assert "<Naam>" in out, f"{rid}: signature name was not replaced by the Naam tag"


# Precision guard: a closing greeting WITHOUT a name on its own line must not trigger
# the sign-off rule (no over-masking). Fully fictional.
NO_SIGN_OFF_CASES = [
    ("neg-inline-groeten", "Ik doe je de hartelijke groeten en tot ziens."),
    ("neg-same-line-dank", "Met dank, tot ziens allemaal."),
    ("neg-word-after-greeting", "Groet,\nBedankt alvast voor de snelle reactie."),
]


@pytest.mark.b4_redgreen
@pytest.mark.parametrize("rid,text", NO_SIGN_OFF_CASES, ids=[c[0] for c in NO_SIGN_OFF_CASES])
def test_no_signature_overmask(rid, text):
    rx = anonymizer.RegexAnonymizer()
    out = rx(text)
    assert "<Naam>" not in out, f"{rid}: sign-off rule overmasks a greeting without a signature name"
