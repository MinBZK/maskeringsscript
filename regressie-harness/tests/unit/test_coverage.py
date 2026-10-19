import itertools

import pytest

from coverage_eval import assess_record, gold_span, visible_source


def status(text, output, value=None):
    return assess_record({'text': text, 'pii': [{'value': value or text}]}, output)[0]['status']


@pytest.mark.parametrize('output,expected', [
    ('<IBAN>', 'fully_masked'),
    ('NL12 RABO <Telefoon>', 'partially_masked'),
    ('<IBAN>9', 'partially_masked'),
    ('N<IBAN>', 'partially_masked'),
    ('NL12 RABO 0123456789', 'unmasked'),
    ('NL12RABO0123456789', 'indeterminate'),
    ('[REDACTED]', 'indeterminate'),
])
def test_account_fragments(output, expected):
    assert status('NL12 RABO 0123456789', output) == expected


def test_all_single_account_characters_are_detected():
    text = 'NL12RABO0123456789'
    for char in text:
        assert status(text, '<IBAN>' + char + '<IBAN>') != 'fully_masked'


def test_repeated_values_are_not_assigned_to_safest_occurrence():
    record = {'text': '123 123', 'pii': [
        {'value': '123', 'start': 0, 'end': 3},
        {'value': '123', 'start': 4, 'end': 7},
    ]}
    assert all(x['status'] != 'fully_masked' for x in assess_record(record, '<IBAN>123<IBAN>'))


@pytest.mark.parametrize('item', [
    {'value': ''}, {'value': 'absent'}, {'value': '123'},
    {'value': '123', 'start': 0, 'end': 2},
])
def test_invalid_or_ambiguous_gold_fails(item):
    with pytest.raises((ValueError, KeyError)):
        gold_span('123 123', item)


def test_existing_literal_tags_are_not_redaction_proof():
    assert status('<Naam> Jan', '<Naam><Naam>', 'Naam') != 'fully_masked'


def test_unsupported_rewrite_and_budget_fail_closed():
    assert visible_source('Jan Jansen', 'JAN <Naam>') is None
    assert visible_source('Jan Jansen', '<Naam>', max_cells=1) is None
    assert status('Jan Jansen', '<Naam> Jansen') == 'partially_masked'


def test_punctuation_is_not_identifying():
    assert status('12-34', '<IBAN>-<IBAN>') == 'fully_masked'


def test_alignment_matches_exhaustive_small_oracle():
    for n in range(1, 6):
        for chars in itertools.product('ab', repeat=n):
            text = ''.join(chars)
            for literal in ('a', 'b', 'ab'):
                expected = set()
                for start in range(n - len(literal) + 1):
                    if text[start:start + len(literal)] == literal:
                        expected.update(range(start, start + len(literal)))
                got = visible_source(text, '<Naam>' + literal + '<Naam>')
                assert got == (expected if expected else None)
