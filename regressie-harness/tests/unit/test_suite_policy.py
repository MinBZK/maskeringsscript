import pytest

from suite_policy import required_items, ensure_collected


def test_full_suite_requires_snapshot_and_every_documented_case():
    required = required_items()
    assert required['tests/test_characterization.py::test_regex_snapshot'] == 'passed'
    assert sum(value == 'xfail' for value in required.values()) == 11
    assert sum('test_known_failure_inventory' in name for name in required) == 11
    ensure_collected(required, set(required))


@pytest.mark.parametrize('missing', ['snapshot', 'desired', 'inventory'])
def test_missing_required_checks_fail(missing):
    required = required_items()
    selected = set(required)
    name = next(name for name in selected if
                ('test_regex_snapshot' in name if missing == 'snapshot' else
                 required[name] == 'xfail' if missing == 'desired' else
                 'test_known_failure_inventory' in name))
    selected.remove(name)
    with pytest.raises(ValueError, match='Full suite is incomplete'):
        ensure_collected(required, selected)
