import json
import sys

import pytest

import repin
from test_measurement import measured
from test_scorecard import card


@pytest.mark.parametrize('case', ['empty_categories', 'old_card_without_receipt', 'edited_timestamp', 'source_drift'])
def test_repin_rejects_unverified_claims_without_writing(monkeypatch, tmp_path, case):
    data = measured(monkeypatch)
    if case == 'empty_categories':
        data['per_category'] = {}
    elif case == 'old_card_without_receipt':
        data = card()
        data['meta']['generated'] = '1990-01-01T00:00:00'
    elif case == 'edited_timestamp':
        data['meta']['generated'] = '1990-01-01T00:00:00'
    else:
        import measurement
        monkeypatch.setattr(measurement, 'capture_inputs', lambda repo, full: {'new': 'source'})
    source, output = tmp_path / 'card.json', tmp_path / 'provenance.json'
    source.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(repin, 'repo_root', lambda: tmp_path)
    monkeypatch.setattr(sys, 'argv', ['repin.py', '--card', str(source), '--output', str(output), '--note', 'test'])
    with pytest.raises(SystemExit) as result:
        repin.main()
    assert result.value.code == 2
    assert not output.exists()


def test_repin_uses_recorded_measurement_hashes(monkeypatch, tmp_path):
    data = measured(monkeypatch)
    source, output = tmp_path / 'card.json', tmp_path / 'provenance.json'
    source.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(repin, 'repo_root', lambda: tmp_path)
    monkeypatch.setattr(sys, 'argv', ['repin.py', '--card', str(source), '--output', str(output), '--note', 'test'])
    repin.main()
    result = json.loads(output.read_text(encoding='utf-8'))
    for key, value in data['measurement']['inputs']['sha256'].items():
        assert result['sha256'][key] == value
    assert result['measurement_result_sha256'] == data['measurement']['result_sha256']
    assert 'not independent proof' in result['scope']
