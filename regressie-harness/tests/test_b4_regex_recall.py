"""Regression checks for contextual BSN masking and credit-card false positives.

The original B4 fixes have landed. These checks have no expected-failure markers;
remaining known errors are listed separately in KNOWN_FAILURES.md.
"""
from __future__ import annotations

import pytest

anonymizer = pytest.importorskip(
    "anonymizer.anonymizer", reason="source repository or runtime dependencies unavailable"
)

VALID_BSN = "111222333"     # Passes the eleven-test checksum.
INVALID_BSN = "123456789"   # Fails the eleven-test checksum.


def test_is_valid_bsn_reference():
    # Establish the validator behavior independently of masking.
    assert anonymizer.is_valid_bsn(VALID_BSN) is True
    assert anonymizer.is_valid_bsn(INVALID_BSN) is False


def test_valid_bsn_is_masked_today():
    # A valid BSN must be masked.
    rx = anonymizer.RegexAnonymizer()
    out = rx(f"Het burgerservicenummer {VALID_BSN} stond in de brief.")
    assert VALID_BSN not in out


@pytest.mark.b4_redgreen  # V01 landed (2026-06-25): regression check.
def test_invalid_bsn_in_context_is_masked():
    rx = anonymizer.RegexAnonymizer()
    out = rx(f"Het burgerservicenummer {INVALID_BSN} stond in de brief.")
    assert INVALID_BSN not in out, "invalid BSN remains visible"


def test_invalid_bsn_without_context_is_not_overmasked():
    # Precision guard: preserve an invalid nine-digit number without BSN context.
    rx = anonymizer.RegexAnonymizer()
    out = rx(f"Het ordernummer {INVALID_BSN} is verwerkt.")
    assert INVALID_BSN in out, "invalid nine-digit number without context was overmasked"


@pytest.mark.b4_redgreen  # V11 landed (2026-06-29): regression check.
def test_order_number_not_overmasked():
    rx = anonymizer.RegexAnonymizer()
    order = "1234 5678 9012 345"  # Fifteen digits with spaces, not a credit card.
    out = rx(f"Bestelnummer {order} is verzonden.")
    assert order in out, "order number was overmasked as Credit_Card"
