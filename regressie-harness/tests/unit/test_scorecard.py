import json
import sys

import pytest

from scorecard import evaluate, _gate
from harness_config import HERE


def card(output='<IBAN>'):
    result = evaluate([{'id': 'T1', 'text': 'NL12 RABO 0123456789',
                        'pii': [{'value': 'NL12 RABO 0123456789', 'category': 'IBAN'}]}], lambda _: output)
    result['meta']['gold_sha256'] = 'fixture'
    return result


def save(tmp_path, baseline):
    path = tmp_path / 'baseline.json'
    path.write_text(json.dumps(baseline), encoding='utf-8')
    return path


def test_partial_account_fails_previously_green_gate(tmp_path):
    candidate = card('NL12 RABO <Telefoon>')
    assert candidate['per_category']['IBAN']['recall'] == 0
    assert candidate['per_category']['IBAN']['residual_pii'][0]['status'] == 'partially_masked'
    assert _gate(candidate, save(tmp_path, card()), 0) == 1


@pytest.mark.parametrize('change', ['legacy', 'missing', 'support', 'gold', 'empty'])
def test_incompatible_or_incomplete_runs_fail(tmp_path, change):
    baseline, current = card(), card()
    if change == 'legacy':
        baseline['meta'].pop('metric')
    elif change == 'missing':
        current['per_category'].clear()
    elif change == 'support':
        current['per_category']['IBAN']['support'] = 0
    elif change == 'gold':
        current['meta']['gold_sha256'] = 'different'
    else:
        baseline['per_category'].clear()
    with pytest.raises(ValueError):
        _gate(current, save(tmp_path, baseline), 0)


def test_ner_is_only_hard_with_explicit_strict_flag(tmp_path):
    baseline, current = card(), card('NL12 RABO <Telefoon>')
    for c in (baseline, current):
        c['per_category']['IBAN']['pass'] = 'ner'
        c['meta']['mode'] = 'full'
    path = save(tmp_path, baseline)
    assert _gate(current, path, 0) == 0
    assert _gate(current, path, 0, strict_ner=True) == 1


def test_empty_gold_is_an_error():
    with pytest.raises(ValueError):
        evaluate([], lambda t: t)


def test_gate_cannot_overwrite_its_reference(monkeypatch, tmp_path):
    from scorecard import main
    path = str(tmp_path / 'reference.json')
    monkeypatch.setattr(sys, 'argv', ['scorecard.py', '--gate', path, '--save', path])
    with pytest.raises(SystemExit) as result:
        main()
    assert result.value.code == 2


def test_harness_imports_do_not_load_model_libraries():
    import subprocess
    result = subprocess.run([sys.executable, '-c',
        "import scorecard,sys; assert not {'torch','gliner','transformers','anonymizer'} & set(sys.modules)"],
        capture_output=True, text=True, cwd=HERE)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('side', ['baseline', 'candidate'])
@pytest.mark.parametrize('value', [None, float('nan'), float('inf'), -float('inf'), '1', True, -0.1, 1.1])
def test_invalid_scores_cannot_make_a_fragment_gate_green(tmp_path, side, value):
    baseline, candidate = card(), card('NL12 RABO <Telefoon>')
    target = baseline if side == 'baseline' else candidate
    target['per_category']['IBAN']['recall'] = value
    with pytest.raises(ValueError):
        _gate(candidate, save(tmp_path, baseline), 0)


@pytest.mark.parametrize('side', ['baseline', 'candidate'])
@pytest.mark.parametrize('change', [
    'missing_score', 'wrong_ratio', 'zero_support', 'fractional_support', 'boolean_count',
    'negative_masked', 'too_many_masked', 'missing_residuals', 'wrong_residual_count',
    'invalid_residual', 'invalid_mode', 'invalid_pass', 'invalid_schema', 'invalid_records',
])
def test_inconsistent_measurements_are_rejected(tmp_path, side, change):
    baseline, candidate = card(), card('NL12 RABO <Telefoon>')
    target = baseline if side == 'baseline' else candidate
    data = target['per_category']['IBAN']
    if change == 'missing_score':
        data.pop('recall')
    elif change == 'wrong_ratio':
        data['recall'] = 0.5
    elif change == 'zero_support':
        data['support'] = 0
    elif change == 'fractional_support':
        data['support'] = 1.5
    elif change == 'boolean_count':
        data['masked'] = True
    elif change == 'negative_masked':
        data['masked'] = -1
    elif change == 'too_many_masked':
        data['masked'] = 2
    elif change == 'missing_residuals':
        data.pop('residual_pii')
    elif change == 'wrong_residual_count':
        data['residual_pii'] = [] if side == 'candidate' else [{}]
    elif change == 'invalid_residual':
        data['masked'], data['recall'], data['residual_pii'] = 0, 0, [None]
    elif change == 'invalid_mode':
        target['meta']['mode'] = 'unknown'
    elif change == 'invalid_pass':
        data['pass'] = 'unknown'
    elif change == 'invalid_schema':
        target['meta']['schema_version'] = 1
    else:
        target['meta']['records'] = 0
    with pytest.raises(ValueError):
        _gate(candidate, save(tmp_path, baseline), 0)


@pytest.mark.parametrize('tolerance', [None, True, float('nan'), float('inf'), -0.1, 1.1])
def test_invalid_tolerance_cannot_disable_the_gate(tmp_path, tolerance):
    with pytest.raises(ValueError):
        _gate(card('NL12 RABO <Telefoon>'), save(tmp_path, card()), tolerance)


def test_valid_partial_reference_remains_comparable(tmp_path):
    partial = card('NL12 RABO <Telefoon>')
    assert _gate(partial, save(tmp_path, partial), 0) == 0
