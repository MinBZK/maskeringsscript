"""Required coverage for official full runs; targeted pytest runs remain available."""
import json
from harness_config import HERE


def required_items():
    cases = json.loads((HERE / 'known_failures.json').read_text(encoding='utf-8'))
    if not cases or len({case['id'] for case in cases}) != len(cases):
        raise ValueError('The known-failure inventory must be nonempty and have unique IDs.')
    required = {'tests/test_characterization.py::test_regex_snapshot': 'passed'}
    for case in cases:
        required[case['desired_test']] = 'xfail'
        required[f"tests/test_known_failure_inventory.py::test_known_failure_inventory_matches_current_output[{case['id']}]"] = 'passed'
    if len(required) != 1 + 2 * len(cases):
        raise ValueError('The known-failure inventory contains duplicate test references.')
    return required


def item_id(item):
    return item.path.resolve().relative_to(HERE).as_posix() + '::' + item.nodeid.split('::', 1)[1]


def ensure_collected(required, selected):
    missing = set(required) - set(selected)
    if missing:
        raise ValueError('Full suite is incomplete; missing required tests: ' + ', '.join(sorted(missing)))
