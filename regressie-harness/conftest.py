"""Explicit test tiers; missing runtime dependencies fail collection."""
import json
import os
import sys
from pathlib import Path
import pytest
from harness_config import HERE, repo_root, model_root, load_anonymizer
from suite_policy import required_items, item_id, ensure_collected

def pytest_addoption(parser):
    parser.addoption('--unit-only', action='store_true')
    parser.addoption('--run-integration', action='store_true')
    parser.addoption('--require-full-suite', action='store_true', help='Require the snapshot and all documented known-failure checks')

def pytest_configure(config):
    if config.getoption('--require-full-suite') and (config.getoption('--unit-only') or os.environ.get('SNAPSHOT_UPDATE')):
        raise pytest.UsageError('A full regression run cannot use --unit-only or SNAPSHOT_UPDATE.')
    if config.getoption('--unit-only') and config.getoption('--run-integration'):
        raise pytest.UsageError('--unit-only and --run-integration are mutually exclusive.')
    if config.getoption('--run-integration'):
        try:
            model_root()
        except ValueError as exc:
            raise pytest.UsageError(str(exc)) from exc
    if not config.getoption('--unit-only'):
        try:
            load_anonymizer(repo_root())
        except Exception as exc:
            raise pytest.UsageError(f'Runtime tests require the source repo and runtime dependencies: {exc}') from exc

def pytest_ignore_collect(collection_path, config):
    path = Path(collection_path)
    if config.getoption('--unit-only') and path.parent.name == 'tests' and path.name.startswith('test_'):
        return True
    if path.name == 'integration' and not config.getoption('--run-integration'):
        return True

@pytest.fixture(autouse=True)
def _restore_anonymizer_globals():
    module = sys.modules.get('anonymizer.anonymizer')
    if module is None:
        yield
        return
    saved = module.LIST_PATH, module.WHITELIST_PATH
    try:
        yield
    finally:
        module.LIST_PATH, module.WHITELIST_PATH = saved

def _read_jsonl(path):
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if not records:
        raise ValueError('Empty test set: ' + path.name)
    return records

@pytest.fixture
def synthetic_records():
    return _read_jsonl(HERE / 'data/synthetic_signals.jsonl')

@pytest.fixture
def snapshot_records():
    return _read_jsonl(HERE / 'data/synthetic_signals.jsonl') + _read_jsonl(HERE / 'data/snapshot_corpus.jsonl')


def pytest_collection_modifyitems(config, items):
    known = {case['id'] for case in json.loads((HERE / 'known_failures.json').read_text(encoding='utf-8'))}
    found = set()
    for item in items:
        marker = item.get_closest_marker('xfail')
        if marker is None:
            continue
        case_id = getattr(getattr(item, 'callspec', None), 'id', None)
        if case_id not in known or not marker.kwargs.get('strict') or case_id in found:
            raise pytest.UsageError('Undocumented, duplicate or non-strict xfail: ' + item.nodeid)
        found.add(case_id)
    if found:
        print(f'Known failures: {len(found)} strict xfails selected; see KNOWN_FAILURES.md (no quality guarantee).')


def pytest_collection_finish(session):
    if not session.config.getoption('--require-full-suite'):
        return
    try:
        required = required_items()
        ensure_collected(required, {item_id(item) for item in session.items if item.path.resolve().is_relative_to(HERE)})
    except (ValueError, KeyError) as exc:
        raise pytest.UsageError(str(exc)) from exc
    session.config._harness_required = required
    session.config._harness_completed = set()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    required = getattr(item.config, '_harness_required', {})
    if not required or report.when != 'call' or not item.path.resolve().is_relative_to(HERE):
        return
    name = item_id(item)
    status = 'xfail' if report.skipped and hasattr(report, 'wasxfail') else report.outcome
    if required.get(name) == status:
        item.config._harness_completed.add(name)


def pytest_sessionfinish(session, exitstatus):
    required = getattr(session.config, '_harness_required', {})
    missing = set(required) - getattr(session.config, '_harness_completed', set())
    if missing and exitstatus == 0:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        terminal = session.config.pluginmanager.get_plugin('terminalreporter')
        if terminal:
            terminal.write_line('Full suite did not execute required checks: ' + ', '.join(sorted(missing)), red=True)
