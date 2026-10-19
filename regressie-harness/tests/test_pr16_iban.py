"""PR #16: complete account masking, precision, rule priority and API compatibility."""
import itertools
import pytest
from anonymizer import anonymizer as A


def make_iban(country, bban):
    # Independent ISO check-digit construction, not the production validator.
    numeric=''.join(str(ord(c)-55) if c.isalpha() else c for c in bban+country+'00')
    return country+f'{98-int(numeric)%97:02d}'+bban


def spaced(value):
    return ' '.join(value[i:i+4] for i in range(0,len(value),4))

REGISTRY_LENGTHS = {'AD': 24, 'AE': 23, 'AL': 28, 'AT': 20, 'AZ': 28, 'BA': 20, 'BE': 16, 'BG': 22, 'BH': 22, 'BI': 27, 'BR': 29, 'BY': 28, 'CH': 21, 'CR': 22, 'CY': 28, 'CZ': 24, 'DE': 22, 'DJ': 27, 'DK': 18, 'DO': 28, 'EE': 20, 'EG': 29, 'ES': 24, 'FI': 18, 'FK': 18, 'FO': 18, 'FR': 27, 'GB': 22, 'GE': 22, 'GI': 23, 'GL': 18, 'GR': 27, 'GT': 28, 'HN': 28, 'HR': 21, 'HU': 28, 'IE': 22, 'IL': 23, 'IQ': 23, 'IS': 26, 'IT': 27, 'JO': 30, 'KW': 30, 'KZ': 20, 'LB': 28, 'LC': 32, 'LI': 21, 'LT': 20, 'LU': 20, 'LV': 21, 'LY': 25, 'MC': 27, 'MD': 24, 'ME': 22, 'MK': 19, 'MN': 20, 'MR': 27, 'MT': 31, 'MU': 30, 'NI': 28, 'NL': 18, 'NO': 15, 'OM': 23, 'PK': 24, 'PL': 28, 'PS': 29, 'PT': 25, 'QA': 29, 'RO': 24, 'RS': 22, 'RU': 33, 'SA': 24, 'SC': 31, 'SD': 18, 'SE': 24, 'SI': 19, 'SK': 24, 'SM': 27, 'SO': 23, 'ST': 25, 'SV': 28, 'TL': 23, 'TN': 24, 'TR': 26, 'UA': 29, 'VA': 22, 'VG': 24, 'XK': 20, 'YE': 30}

@pytest.mark.parametrize('iban', [
 'NL91 ABNA 0417 1643 00','NL 91 ABNA 0417 1643 00',
 'NL12 RABO 0123 4567 89','NL12 INGB 0987 6543 21',
 'NL91 ABNA 0417 1643 01','NL00 ABNA 0417 1643 00',
])
def test_keep_legacy_dutch_coverage(iban):
    assert A.RegexAnonymizer()('Rekening '+iban+'.')=='Rekening <IBAN>.'


@pytest.mark.parametrize('country,length', sorted(REGISTRY_LENGTHS.items()))
@pytest.mark.parametrize('formatting', ['compact','spaced','lowercase'])
def test_registered_country_coverage(country,length,formatting):
    value=make_iban(country, 'ABNA'+'0'*10 if country=='NL' else '0'*(length-4))
    # These synthetic values check country/length/checksum, not national bank formats.
    assert A.is_valid_iban(value)
    if formatting=='spaced':value=spaced(value)
    if formatting=='lowercase':value=value.lower()
    assert A.RegexAnonymizer()('Rekening '+value+'.')=='Rekening <IBAN>.'


@pytest.mark.parametrize('value', [
 'BE68 5390 0754 7034','DE89 3704 0044 0532 0130 00',
 'GB33BUKB20201555555555','TR33 0006 1005 1978 6457 8413 26',
 'PL61 1090 1014 0000 0712 1981 2874','FR14 2004 1010 0505 0001 3M02 606',
 'ES91 2100 0418 4502 0005 1332','NO93 8601 1117 947',
 'FK88SC123456789012','MN121234123456789123','OM810180000001299123456',
 'NI45BAPR00000013000003558124','HN88CABF00000000000250005469',
 'YE15CBYE0001018861234567891234',
])
def test_published_examples(value):
    assert A.is_valid_iban(value)
    assert A.RegexAnonymizer()('Rekening '+value+' gebruikt.')=='Rekening <IBAN> gebruikt.'


@pytest.mark.parametrize('first,second', [
 ('BE68 5390 0754 7034','DE89 3704 0044 0532 0130 00'),
 ('BE68 5390 0754 7034','NL91 ABNA 0417 1643 00'),
 ('NL91 ABNA 0417 1643 00','BE68 5390 0754 7034'),
 ('NO93 8601 1117 947','BE68 5390 0754 7034'),
])
def test_consecutive_accounts(first,second):
    assert A.RegexAnonymizer()(first+' '+second)=='<IBAN> <IBAN>'


@pytest.mark.parametrize('url', [
 'https://example.org/GB33BUKB20201555555555/testgebruiker',
 'https://GB33BUKB20201555555555.example/testgebruiker',
 'https://example.org/BE68539007547034/testgebruiker',
 'https://example.org/zoeken?iban=GB33BUKB20201555555555&naam=testgebruiker',
])
def test_complete_url_is_not_split(url):
    assert A.RegexAnonymizer()(url)=='<URL>'


@pytest.mark.parametrize('text', [
 'Ongeldig BE68 5390 0754 7035.', 'BTW NL123456789B01.',
 'Zaaknummer AB12 3456 7890.', 'Kenmerk XX99 1234 5678 9012.',
 'Bel mij op 06-12345678.', 'Bedrag van 1.250,00 euro is betaald.',
 'in de 30-zone gereden', 'kenteken AB-12-34 genoteerd',
 'BE68 5390 0754 7034graag',
 'MA64 0115 1900 0001 2050 0053 4921',
])
def test_rejected_or_unregistered_value_has_no_iban_tag(text):
    assert '<IBAN>' not in A.RegexAnonymizer()(text)


@pytest.mark.parametrize('value', [
 None, '', 'BE68539007547035','XX99539007547034','NI45BAPR000000130000035581240000',
 'MA64011519000001205000534921','BE６８539007547034','BE6853900754703４',
])
def test_validator_rejects_invalid_values(value):
    assert not A.is_valid_iban(value)


def test_checksum_digits_00_01_99_rejected_even_with_remainder_one():
    found=set()
    for n in range(1000):
        good=make_iban('BE',f'{n:012d}')
        check=int(good[2:4])
        bad={97:'00',98:'01',2:'99'}.get(check)
        if bad:
            found.add(bad)
            assert not A.is_valid_iban('BE'+bad+good[4:])
    assert found=={'00','01','99'}


@pytest.mark.parametrize('language',['nl','en'])
@pytest.mark.parametrize('mask',['<{tag}>','[{tag}]'])
@pytest.mark.parametrize('distinct',[False,True])
def test_configuration(monkeypatch,language,mask,distinct):
    monkeypatch.setattr(A,'TAG_LANGUAGE',language)
    rx=A.RegexAnonymizer(mask=mask,distinct_tags=distinct)
    assert rx('BE68 5390 0754 7034')==mask.format(tag=A.TRANSLATIONS[language]['IBAN'])


def test_existing_positional_constructor_contract():
    assert A.RegexAnonymizer(None,'<{tag}>',True,True,True)._distinct_tags is True


def test_custom_iban_pattern_keeps_direct_matching(monkeypatch):
    monkeypatch.setitem(A.TAGGED_PATTERNS,'IBAN',r'\bREK[0-9]+\b')
    assert A.RegexAnonymizer()('REK12345')=='<IBAN>'


def test_iban_tag_disabled():
    assert A.RegexAnonymizer(tags=['Email'])('BE68 5390 0754 7034')=='BE68 5390 0754 7034'


def test_url_disabled_still_masks_account():
    assert A.RegexAnonymizer(tags=['IBAN'])('https://example.org/BE68539007547034/name')=='https://example.org/<IBAN>/name'


@pytest.mark.parametrize('cue,tail', [
 ('BSN','123456789'),('PIER','12'),('DANK','\nA. Voorbeeldnaam'),
])
def test_additional_account_preserves_later_context(cue,tail):
    if cue=='BSN':value=spaced(make_iban('OM','0'*16+cue))
    elif cue=='PIER':value=spaced(make_iban('LC','0'*24+cue))
    else:value=spaced(make_iban('LC','0'*24+cue)).replace(' DANK','\nDANK')
    text=value+' '+tail if cue!='DANK' else value+tail
    out=A.RegexAnonymizer()(text)
    assert tail.strip() not in out


def test_following_count_not_consumed():
    assert A.RegexAnonymizer()('BE68 5390 0754 7034 12 dossiers')=='<IBAN> 12 dossiers'


@pytest.mark.parametrize('separator',['\u00a0','\u202f','\u2003','\t','\n'])
def test_single_unicode_whitespace_between_foreign_groups(separator):
    value='BE68 5390 0754 7034'.replace(' ',separator)
    assert A.RegexAnonymizer()(value)=='<IBAN>'


@pytest.mark.parametrize('value',[
    'BE６８539007547034','BK68539007547034',
    'GB33BUKB20201555555555','GB33BUſB20201555555555',
])
def test_non_ascii_iban_symbols_are_not_accepted(value):
    assert not A.is_valid_iban(value)
    assert '<IBAN>' not in A.RegexAnonymizer()(value)
