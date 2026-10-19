"""PR #15: postcode coverage, precision and documented limitations.

Inputs are synthetic. Strict expected failures describe desired behavior;
they do not count as passing tests. House-number behavior is characterized
separately and is unchanged by the postcode extension."""
import itertools
import re
import string

import pytest

A = pytest.importorskip('anonymizer.anonymizer')


@pytest.mark.parametrize('text,expected', [
    ('Ik woon op 3011 ab in Rotterdam.', 'Ik woon op <Postcode> in Rotterdam.'),
    ('adres 2595bm den haag', 'adres <Postcode> den haag'),
    ('Postcode 1012 Ab Amsterdam', 'Postcode <Postcode> Amsterdam'),
    ('woont 9999 Ab ergens', 'woont <Postcode> ergens'),
    ('verhuisd naar 3011ad 2 hoog', 'verhuisd naar <Postcode> hoog'),
    ('2595 bm 14 Den Haag', '<Postcode> Den Haag'),
    ('Postcode: 5701 en', 'Postcode: <Postcode>'),
    ('POSTCODE = 5701 En', 'POSTCODE = <Postcode>'),
    ('postcode\t:\t5701 eN', 'postcode\t:\t<Postcode>'),
    ('Mijn postcode is 5701en.', 'Mijn postcode is <Postcode>.'),
    ('Mijn postcode luidt 5701 en.', 'Mijn postcode luidt <Postcode>.'),
    ('Postcode:\n5701 en', 'Postcode:\n<Postcode>'),
    ('Postcode: 3011 jl', 'Postcode: <Postcode>'),
    ('Postcode: 3011 nr', 'Postcode: <Postcode>'),
])
def test_postcode_recall(text, expected):
    assert A.RegexAnonymizer()(text) == expected


@pytest.mark.parametrize('text', [
    'sinds 1998 en is dit bekend', 'sinds 1998 En is dit bekend',
    'In 2015 Op de locatie', 'Motor van 1600 Cc', 'Vermogen 2500 kW',
    'Geheugen 2000 Mb', 'Zitting in 2020 jl.', 'Sinds 2020 ca. 12 meldingen.',
    'In 2020 nr. 12 behandeld.', 'In 2020 bv. 12 zaken.',
    'Artikel 2020 vs 12 bekeken.', 'Afstand 1200 Km.', 'Opslag 2000 mB.',
    'Resolutie 1200 pX.', 'Oppervlakte 2000 Ha.', 'De zaak loopt al 3000 uur door.',
    'Een postcode hoort bij 2020 en eerdere aanvragen.',
    'Het veld postcode is leeg sinds 2020 en wordt aangevuld.',
])
def test_ordinary_text_not_masked_as_postcode(text):
    assert A.RegexAnonymizer()(text) == text


def test_all_uppercase_letter_pairs_preserved():
    rx = A.RegexAnonymizer(tags=['Postcode'])
    for a, b in itertools.product(string.ascii_uppercase, repeat=2):
        assert rx('3011 ' + a + b) == '<Postcode>', (a, b)


def test_postcode_pattern_is_independent_of_ignorecase():
    pattern = A.TAGGED_PATTERNS['Postcode']
    normal = re.compile(pattern, re.VERBOSE)
    ignore = re.compile(pattern, re.VERBOSE | re.IGNORECASE)
    for a, b in itertools.product(string.ascii_letters + 'İıſK', repeat=2):
        text = '3011 ' + a + b
        assert bool(normal.fullmatch(text)) == bool(ignore.fullmatch(text)), text
    assert not normal.fullmatch('3011 İS')


@pytest.mark.parametrize('language', ['nl', 'en'])
@pytest.mark.parametrize('mask', ['<{tag}>', '[{tag}]'])
@pytest.mark.parametrize('distinct', [False, True])
def test_postcode_callback_respects_tag_configuration(monkeypatch, language, mask, distinct):
    monkeypatch.setattr(A, 'TAG_LANGUAGE', language)
    tag = mask.format(tag=A.TRANSLATIONS[language]['Postcode'])
    rx = A.RegexAnonymizer(mask=mask, distinct_tags=distinct)
    assert rx('postcode: 5701 en 12A') == 'postcode: ' + tag
    assert rx('Vermogen 2500 kW') == 'Vermogen 2500 kW'


def test_postcode_tag_can_be_disabled():
    assert A.RegexAnonymizer(tags=['Email'])('postcode: 5701 en') == 'postcode: 5701 en'


@pytest.mark.xfail(strict=True, reason='Known postcode limitations; desired behavior is not yet implemented (see KNOWN_FAILURES.md)')
@pytest.mark.parametrize('text,expected', [
    ('ik woon 5701 En Helmond', 'ik woon <Postcode> Helmond'),
    ('5701 En Helmond', '<Postcode> Helmond'),
    ('Postcode 2020 en huisnummer 14 ontbreken.', 'Postcode 2020 en huisnummer 14 ontbreken.'),
    ('Postcode: 2020 en huisnummer 14 ontbreken.', 'Postcode: 2020 en huisnummer 14 ontbreken.'),
    ('Benoemd in 2020 ad interim.', 'Benoemd in 2020 ad interim.'),
    ('In 2020 ad hoc besloten.', 'In 2020 ad hoc besloten.'),
    ('Geheugen 2000 MB', 'Geheugen 2000 MB'),
], ids=['K01', 'K02', 'K03', 'K04', 'K05', 'K06', 'K07'])
def test_known_postcode_limitations_desired_behavior(text, expected):
    """Check desired behavior; known failures must not count as passing tests."""
    assert A.RegexAnonymizer()(text) == expected


@pytest.mark.parametrize('suffix,expected', [
    (' 12A', '<Postcode>'), (' 2 hoog', '<Postcode> hoog'),
    (' 2026 dossiers', '<Postcode> dossiers'), ('\n2026 dossiers', '<Postcode> dossiers'),
    ('\n12A', '<Postcode>'), (' 12-14', '<Postcode>-14'),
    (' 12/3', '<Postcode>/3'), (' 12 bis', '<Postcode> bis'),
    (' 12 34', '<Postcode> 34'),
])
def test_existing_house_number_behavior(suffix, expected):
    """Characterize existing house-number behavior, including cross-line matches and residuals."""
    rx = A.RegexAnonymizer()
    assert rx('3011 AB' + suffix) == expected
    assert rx('3011 ab' + suffix) == expected


@pytest.mark.parametrize('url', [
    'https://3011ab.example/gebruikers/henkzwartendijk',
    'http://3011Ab.example/gebruikers/henkzwartendijk',
    'www.3011ab.nl/mijn-account/henkzwartendijk',
    'https://example.org/dossiers/3011ab/henkzwartendijk',
    pytest.param('https://example.org/dossiers/3011AB/henkzwartendijk', marks=pytest.mark.xfail(strict=True, reason='K08: existing URL rule-order bug; see KNOWN_FAILURES.md'), id='K08'),
    'https://example.org/zoeken?postcode=3011ab&gebruiker=henkzwartendijk',
    'https://example.org/zoeken?postcode=5701en&gebruiker=henkzwartendijk',
    'https://example.org/meldingen#3011ab-gebruiker-henkzwartendijk',
    'https://example.org/3011ab/3012Ab/henkzwartendijk',
])
def test_postcode_does_not_break_complete_url(url):
    """Mask the complete URL without leaving a postcode tag or a URL tail."""
    rx = A.RegexAnonymizer()
    out = rx('Zie ' + url + ' voor uw dossier.')
    assert out == 'Zie <URL> voor uw dossier.'
    assert 'henkzwartendijk' not in out
    assert '<Postcode>' not in out


@pytest.mark.parametrize('language', ['nl', 'en'])
@pytest.mark.parametrize('mask', ['<{tag}>', '[{tag}]'])
@pytest.mark.parametrize('distinct', [False, True])
def test_url_postcode_overlap_respects_configuration(monkeypatch, language, mask, distinct):
    monkeypatch.setattr(A, 'TAG_LANGUAGE', language)
    url = 'https://3011ab.example/dossiers/henkzwartendijk'
    rx = A.RegexAnonymizer(mask=mask, distinct_tags=distinct)
    expected = mask.format(tag=A.TRANSLATIONS[language]['URL'])
    assert rx(url) == expected
    assert 'henkzwartendijk' not in rx(url)


def test_mixed_urls_and_free_postcodes():
    rx = A.RegexAnonymizer()
    text = ('https://3011ab.example/henkzwartendijk '
            'Postcode: 5701 en. https://example.org/3011ab/henkzwartendijk. '
            'Andere postcode: 3012 Ab.')
    assert rx(text) == '<URL> Postcode: <Postcode>. <URL>. Andere postcode: <Postcode>.'


def test_postcode_overlapping_partial_url_preserves_previous_url_masking():
    # The space ends the URL; "ab/dossier" was already outside URL masking.
    rx = A.RegexAnonymizer()
    assert rx('https://example.org/3011 ab/dossier') == '<URL> ab/dossier'
    assert rx('https://example.org/3011 ab/dossier 3012 ab') == '<URL> ab/dossier <Postcode>'


def test_postcode_still_works_when_url_tag_is_disabled():
    rx = A.RegexAnonymizer(tags=['Postcode'])
    url = 'https://3011ab.example/dossiers/henkzwartendijk'
    assert rx(url) == 'https://<Postcode>.example/dossiers/henkzwartendijk'


def test_excluded_url_domain_keeps_postcode_handling():
    # The URL pass excludes rotterdam.nl; the postcode pass has no domain whitelist.
    rx = A.RegexAnonymizer()
    assert rx('https://www.rotterdam.nl/3011ab/melding') == 'https://www.rotterdam.nl/<Postcode>/melding'


def test_postcodes_in_email_do_not_escape_email_masking():
    # Email precedes Postcode and must still mask the complete email address.
    rx = A.RegexAnonymizer()
    assert rx('Mail 3011ab@example.org of postcode5701en@example.org.') == 'Mail <Email> of <Email>.'


def test_postcode_tag_order_is_unchanged():
    assert list(A.TAGGED_PATTERNS) == [
        'Money', 'Number', 'Date', 'Date_Ext', 'Age', 'Email', 'IBAN', 'Postcode',
        'Licence_Plate', 'Phone', 'URL', 'ID_Number', 'BSN', 'KVK', 'BTW',
        'IP_Address', 'Credit_Card',
    ]


@pytest.mark.parametrize('text,expected', [
    ('https://example.org/3011ab postcode 5701 en', '<URL> postcode <Postcode>'),
    ('https://example.org/3011ab postcode is 5701 en', '<URL> postcode is <Postcode>'),
    ('https://example.org/3011ab postcode: 5701 en', '<URL> postcode: <Postcode>'),
    ('https://example.org/3011ab https://example.org/3012ab postcode 5701 en',
     '<URL> <URL> postcode <Postcode>'),
])
def test_plaintext_postcode_cue_after_url(text, expected):
    assert A.RegexAnonymizer()(text) == expected


def test_word_inside_url_is_not_plaintext_postcode_cue():
    assert A.RegexAnonymizer()('https://example.org/3011ab/postcode 1998 en later') == '<URL> 1998 en later'


@pytest.mark.parametrize('url_template', [
    'https://{code}.example/gebruikers/testgebruiker',
    'https://example.org/dossiers/{code}/testgebruiker',
    'https://example.org/zoeken?postcode={code}&gebruiker=testgebruiker',
])
def test_complete_urls_with_all_letter_pairs(url_template):
    """Postcode-like host, path and query values must not leave URL fragments."""
    rx = A.RegexAnonymizer()
    for a, b in itertools.product(string.ascii_letters + 'İıſK', repeat=2):
        if a in string.ascii_uppercase and b in string.ascii_uppercase:
            continue  # Existing uppercase URL debt is tracked separately above.
        url = url_template.format(code='3011' + a + b)
        text = 'Zie ' + url + ' voor uw dossier.'
        assert rx(text) == 'Zie <URL> voor uw dossier.', (a, b, text)


@pytest.mark.xfail(strict=True, reason='Known house-number limitation: ranges and suffixes are not fully masked (see KNOWN_FAILURES.md)')
@pytest.mark.parametrize('text', [
    '3011 AB 12-14',
    '3011 AB 12/3',
    '3011 AB 12bis',
], ids=['K09', 'K10', 'K11'])
def test_complete_house_number_parts_desired_behavior(text):
    assert A.RegexAnonymizer()(text) == '<Postcode>'


@pytest.mark.parametrize('text,expected', [
    ('Bel mij op 06 1234 3011 ma t/m vr.', 'Bel mij op <Telefoon> ma t/m vr.'),
    ('Telefoon 010 123 3011 ab genoemd.', 'Telefoon <Telefoon> ab genoemd.'),
    ('Call 06 1234 3011 at night.', 'Call <Telefoon> at night.'),
    ('Kaart 4539 5787 6362 1486 at checkout.', 'Kaart <Credit_Card> at checkout.'),
    ('Kaart 4539 5787 6362 1486 ma gebruikt.', 'Kaart <Credit_Card> ma gebruikt.'),
    ('Kenteken AB-CD-1234 ab genoemd.', 'Kenteken <Kenteken> ab genoemd.'),
    ('Zaaknummer 123456-1234 ab genoemd.', 'Zaaknummer <ID_Nummer> ab genoemd.'),
])
@pytest.mark.parametrize('validate', [False, True])
def test_additional_postcode_does_not_break_existing_fields(text, expected, validate):
    assert A.RegexAnonymizer(validate_bsn=validate, validate_credit_card=validate)(text) == expected


def test_url_handling_keeps_existing_bsn_context_protection():
    text = 'Ga naar https://example.org/3011AB/bsn 123456789 voor details.'
    out = A.RegexAnonymizer()(text)
    assert '123456789' not in out
    assert '<BSN>' in out


@pytest.mark.parametrize('pattern,text,expected', [
    (r'\b\d{5}\b', 'Adres 12345 12A', 'Adres <Postcode>'),
    (r'(?i:\bsw1a\s?1en\b)', 'Adres sw1a 1en', 'Adres <Postcode>'),
])
def test_custom_postcode_formats_keep_configured_behavior(monkeypatch, pattern, text, expected):
    monkeypatch.setitem(A.TAGGED_PATTERNS, 'Postcode', pattern)
    assert A.RegexAnonymizer()(text) == expected


def test_adjacent_additional_postcodes_are_masked_before_house_numbers():
    assert A.RegexAnonymizer()('3011 ab 3012 ab 12A') == '<Postcode> <Postcode>'


def test_additional_postcode_output_is_deterministic_and_preserves_control_text():
    text = '\0POSTCODE-raw\x01 3011 ab 12A / 3012 ab 34'
    rx = A.RegexAnonymizer(tags=['Postcode'])
    expected = '\0POSTCODE-raw\x01 <Postcode> / <Postcode>'
    assert rx(text) == rx(text) == expected
