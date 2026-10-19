"""The public inventory must describe exactly the actual outstanding behavior."""
import json

import pytest
from anonymizer import anonymizer as A
from harness_config import HERE

CASES = json.loads((HERE / 'known_failures.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['id'])
def test_known_failure_inventory_matches_current_output(case):
    assert A.RegexAnonymizer()(case['input']) == case['actual']
    assert case['actual'] != case['desired']
