"""Regression checks for licence-plate precision and adjacent card digits.

Hyphenated plates accept either case; compact and space-separated plates
require uppercase letters. A digit beside a valid card must not prevent masking.
The card fixture is a synthetic Luhn-valid example."""
from __future__ import annotations

import pytest

anonymizer = pytest.importorskip(
    "anonymizer.anonymizer", reason="source repository or runtime dependencies unavailable"
)

PLATE_KEEP = [
    ("hyphen-upper", "kenteken AB-12-34 gezien", "AB-12-34"),
    ("hyphen-lower", "kenteken ab-12-34 gezien", "ab-12-34"),
    ("hyphen-sidecode8", "kenteken 12-ABC-1 gezien", "12-ABC-1"),
    ("space-upper", "kenteken AB 12 34 gezien", "AB 12 34"),
    ("nosep-upper", "kenteken AB1234 gezien", "AB1234"),
    ("nosep-upper-2", "voertuig 12ABC1 gemeld", "12ABC1"),
]
PLATE_NOMASK = [
    ("in-de-30", "die zeker 60 reed in de 30-zone"),
    ("ze-is-84", "ze is 84, ik sta machteloos"),
    ("op-na-16", "niemand neemt op na 16.30"),
    ("artikel-12-sv", "of artikel 12 Sv of een andere route"),
    ("lower-nosep", "artikelcode ab1234 besteld"),
    ("lower-nosep-2", "product 12ab34 en variant 1abc12 geleverd"),
]


@pytest.mark.b4_redgreen
@pytest.mark.parametrize("rid,text,plate", PLATE_KEEP, ids=[c[0] for c in PLATE_KEEP])
def test_real_plate_is_masked(rid, text, plate):
    out = anonymizer.RegexAnonymizer()(text)
    assert plate not in out and "<Kenteken>" in out, f"{rid}: real licence plate was not masked"


@pytest.mark.b4_redgreen
@pytest.mark.parametrize("rid,text", PLATE_NOMASK, ids=[c[0] for c in PLATE_NOMASK])
def test_words_and_codes_not_masked_as_plate(rid, text):
    out = anonymizer.RegexAnonymizer()(text)
    assert "<Kenteken>" not in out, f"{rid}: overmasked as a licence plate (V17): {out!r}"


CARD_CASES = [
    ("plain", "Kaart 4539 5787 6362 1486 gebruikt."),
    ("adjacent-digit", "Kaart 4539 5787 6362 1486 2 keer gebruikt."),
    ("hyphen-tail", "Kaartnummer 4539-5787-6362-1486-1 ingevoerd."),
    ("leading-digit", "Nummers 1 4539 5787 6362 1486 genoteerd."),
]


@pytest.mark.b4_redgreen
@pytest.mark.parametrize("rid,text", CARD_CASES, ids=[c[0] for c in CARD_CASES])
def test_card_next_to_digit_is_masked(rid, text):
    out = anonymizer.RegexAnonymizer()(text)
    assert "4539" not in out and "1486" not in out, f"{rid}: card remains visible (V27): {out!r}"


def test_card_does_not_eat_trailing_space():
    out = anonymizer.RegexAnonymizer()("Kaart 4539 5787 6362 1486 gebruikt.")
    assert "> gebruikt" in out, f"space after the card was consumed: {out!r}"


def test_order_number_still_not_masked_as_card():
    # V11 regression guard: thirteen digits failing Luhn are not a card.
    out = anonymizer.RegexAnonymizer()("Bestelnummer 1234567890123 zonder Luhn.")
    assert "1234567890123" in out
