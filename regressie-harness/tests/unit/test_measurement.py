import copy

import pytest

import measurement as M
from scorecard import _validate_card
from test_scorecard import card


def measured(monkeypatch):
    result = card()
    inputs = {'git_sha_full': 'a' * 40, 'git_dirty': False,
              'sha256': {'gold': 'fixture', 'source/core': 'source-hash'},
              'environment': {'python': 'test', 'platform': 'test', 'packages': {}}}
    result['meta']['git_sha'] = 'a' * 7
    result['meta']['generated'] = '2026-10-19T10:00:30+00:00'
    monkeypatch.setattr(M, 'capture_inputs', lambda repo, full: copy.deepcopy(inputs))
    return M.record_measurement(result, inputs, copy.deepcopy(inputs),
                                '2026-10-19T10:00:00+00:00', '2026-10-19T10:01:00+00:00')


def test_unchanged_run_receipt_is_accepted(monkeypatch, tmp_path):
    result = measured(monkeypatch)
    assert M.verify_measurement(result, tmp_path) == result['measurement']


@pytest.mark.parametrize('change', ['results', 'old_timestamp', 'receipt_timestamps', 'missing_receipt', 'source_drift', 'dirty_run'])
def test_invalid_or_stale_measurement_claim_is_rejected(monkeypatch, tmp_path, change):
    result = measured(monkeypatch)
    if change == 'results':
        result['per_category']['IBAN']['masked'] = 0
    elif change == 'old_timestamp':
        result['meta']['generated'] = '1990-01-01T00:00:00'
    elif change == 'receipt_timestamps':
        result['measurement']['started_utc'] = '1990-01-01T00:00:00+00:00'
        result['measurement']['finished_utc'] = '1990-01-01T00:01:00+00:00'
    elif change == 'missing_receipt':
        result.pop('measurement')
    elif change == 'source_drift':
        monkeypatch.setattr(M, 'capture_inputs', lambda repo, full: {'different': 'source'})
    else:
        result['measurement']['inputs']['git_dirty'] = True
    with pytest.raises(ValueError):
        M.verify_measurement(result, tmp_path)


def test_inputs_changing_during_run_are_rejected():
    with pytest.raises(ValueError, match='changed during the run'):
        M.record_measurement(card(), {'source': 'old'}, {'source': 'new'}, 'start', 'finish')


def test_empty_category_card_is_not_a_valid_provenance_input():
    result = card()
    result['per_category'] = {}
    with pytest.raises(ValueError):
        _validate_card(result, 'Scorecard')


def test_legacy_list_changes_are_part_of_the_input_fingerprint(monkeypatch, tmp_path):
    (tmp_path / 'pyproject.toml').write_text('test', encoding='utf-8')
    folder = tmp_path / 'input_files'
    folder.mkdir()
    source = folder / 'ListClassifier Basic.xlsx'
    source.write_bytes(b'before')
    monkeypatch.setattr(M.importlib.metadata, 'version', lambda name: 'test')
    monkeypatch.setattr(M, 'git_state', lambda repo: (None, None))
    before = M.capture_inputs(tmp_path, False)
    source.write_bytes(b'after')
    after = M.capture_inputs(tmp_path, False)
    assert before['sha256']['legacy_lists/ListClassifier Basic.xlsx'] != after['sha256']['legacy_lists/ListClassifier Basic.xlsx']
    with pytest.raises(ValueError, match='changed during the run'):
        M.record_measurement(card(), before, after, 'start', 'finish')
