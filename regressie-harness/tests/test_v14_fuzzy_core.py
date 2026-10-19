"""Regression checks for SymSpell fuzzy replacement in ListAnonymizer.

Preserve punctuation, restrict fuzzy Name/Address matches to capitalized words,
and use the translated Name tag. Synthetic typo names are derived from the
bundled dictionary instead of relying on one particular surname."""
from __future__ import annotations

import pytest

anonymizer = pytest.importorskip(
    "anonymizer.anonymizer", reason="source repository or runtime dependencies unavailable"
)


@pytest.fixture(scope="module")
def la():
    return anonymizer.ListAnonymizer()


@pytest.fixture(scope="module")
def typo_name(la):
    # Accept legacy sheet names so old code fails an assertion rather than fixture setup.
    names = sorted(w for w, t in la.word_to_tag_map.items()
                   if t in ("Name", "Last Name", "First Name") and len(w) > 6)
    assert names, "no case-insensitive name longer than six characters in the SymSpell dictionary"
    n = names[0]
    return (n[:3] + n[4:]).capitalize()


def test_fuzzy_name_tag_is_name_not_sheet_name(la):
    assert not any(t in ("First Name", "Last Name") for t in la.word_to_tag_map.values()), \
        "word_to_tag_map contains sheet names; fuzzy name matches would receive a <Last Name> tag"


@pytest.mark.parametrize("template,keep", [
    ("Gesproken met {n}, hij belde terug.", "<Naam>, hij"),
    ("Brief van {n}. Daarna niets meer gehoord.", "<Naam>. Daarna"),
    ("Klacht van ({n}) ontvangen.", "(<Naam>)"),
    ("Volgens {n}: geen probleem.", "<Naam>:"),
], ids=["komma", "punt", "haakjes", "dubbelepunt"])
def test_fuzzy_name_keeps_punctuation(la, typo_name, template, keep):
    out = la(template.format(n=typo_name))
    assert keep in out and typo_name not in out, f"incorrect punctuation or name: {out!r}"


def test_fuzzy_address_keeps_punctuation(la):
    # "Berkenhof" is in the bundled address list; "Berkenhoff" is a one-edit typo.
    out = la("Overlast rond de speeltuin aan de Berkenhoff, je ziet ze lopen.")
    assert "<Adres>, je ziet" in out, out


@pytest.mark.parametrize("text", [
    "Zo nodig stellen wij beroep in bij de rechtbank.",
    "De zoekgeraakte zending is nog niet terecht.",
    "Het gaat om een weiland buiten het dorp.",
    "Dat verhoogt de spanning in de buurt.",
    "Waarvan ik een factuur bijvoeg als bewijs.",
    "Kunt u mij dit in gewoon Nederlands uitleggen?",
    "De brief is in lastig nederlands geschreven.",
], ids=["stellen", "zending", "weiland", "spanning", "bijvoeg", "Nederlands", "nederlands"])
def test_ordinary_words_not_fuzzy_masked(la, text):
    out = la(text)
    assert "<" not in out, f"ordinary word was fuzzy-masked (V14): {out!r}"
