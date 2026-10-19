"""Unsigned, auditable run receipts binding scorecards to measured input hashes."""
import datetime
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
from pathlib import Path

from harness_config import HERE, model_root


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def result_sha(card):
    result = {key: value for key, value in card.items() if key != 'measurement'}
    return hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def git_state(repo):
    try:
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True,
                                           stderr=subprocess.DEVNULL).strip()
        if Path(git('rev-parse', '--show-toplevel')).resolve() != Path(repo).resolve():
            return None, None
        return git('rev-parse', 'HEAD'), bool(git('status', '--porcelain'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None


def backbone_config(model):
    name = json.loads((model / 'gliner_config.json').read_text(encoding='utf-8'))['model_name']
    local = Path(name) / 'config.json'
    if local.is_file():
        return local.resolve()
    # Use the same cache resolution as GLiNER's AutoConfig call, including
    # already initialized library defaults, while forbidding downloads.
    from transformers.utils.hub import cached_file
    cached = cached_file(name, 'config.json', local_files_only=True)
    if not isinstance(cached, str) or not Path(cached).is_file():
        raise ValueError('The model backbone config must be present in the offline cache.')
    return Path(cached)


def capture_inputs(repo, full):
    """Fingerprint the actual source, evaluation inputs and runtime environment."""
    repo = Path(repo)
    files = {
        'source/pyproject.toml': repo / 'pyproject.toml',
        'gold': HERE / 'data/synthetic_signals.jsonl',
        'snapshot_corpus': HERE / 'data/snapshot_corpus.jsonl',
        'regex_snapshot': HERE / 'snapshots/regex_baseline.json',
        'runtime_lock': HERE / 'requirements-runtime.lock',
    }
    for path in sorted((repo / 'src/anonymizer').rglob('*')):
        if path.is_file() and path.suffix in {'.py', '.json', '.xlsx'}:
            files['source/' + path.relative_to(repo / 'src/anonymizer').as_posix()] = path
    for name in ('ListClassifier Basic.xlsx', 'Whitelist Basic.xlsx'):
        legacy = repo / 'input_files' / name
        if legacy.is_file():
            files['legacy_lists/' + name] = legacy
    for name in ('coverage_eval.py', 'scorecard.py', 'harness_config.py', 'measurement.py'):
        files['harness/' + name] = HERE / name
    if full:
        model = model_root()
        for name in ('gliner_config.json', 'model.safetensors', 'tokenizer_config.json',
                     'tokenizer.json', 'spm.model', 'added_tokens.json', 'special_tokens_map.json'):
            files['model/' + name] = model / name
        files['model/backbone_config'] = backbone_config(model)
    versions = {}
    for line in files['runtime_lock'].read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^\s]+)', line.strip())
        if match:
            name = match[1]
            try:
                versions[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError as exc:
                raise ValueError(f'Required runtime distribution is missing: {name}') from exc
    commit, dirty = git_state(repo)
    return {'git_sha_full': commit, 'git_dirty': dirty,
            'environment': {'python': platform.python_version(), 'platform': platform.platform(),
                            'packages': versions},
            'sha256': {key: file_sha(path) for key, path in files.items()}}


def record_measurement(card, before, after, started, finished):
    if before != after:
        raise ValueError('Measurement inputs or environment changed during the run; discard the result.')
    card['measurement'] = {'schema_version': 1, 'started_utc': started, 'finished_utc': finished,
                           'inputs': before, 'result_sha256': result_sha(card)}
    return card


def verify_measurement(card, repo):
    """Verify an existing receipt; never infer a new measurement from current files."""
    receipt = card.get('measurement')
    if not isinstance(receipt, dict) or type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1:
        raise ValueError('A run receipt is required; create a fresh scorecard with scorecard.py.')
    try:
        start = datetime.datetime.fromisoformat(receipt['started_utc'])
        finish = datetime.datetime.fromisoformat(receipt['finished_utc'])
        generated = datetime.datetime.fromisoformat(card['meta']['generated'])
        if start.tzinfo is None or finish.tzinfo is None or generated.tzinfo is None or not start <= generated <= finish:
            raise ValueError('Invalid measurement timestamps.')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('The measurement timestamps are missing or invalid.') from exc
    if receipt.get('result_sha256') != result_sha(card):
        raise ValueError('The scorecard was edited after measurement; result fingerprint differs.')
    inputs = receipt.get('inputs')
    if not isinstance(inputs, dict) or not inputs.get('git_sha_full') or inputs.get('git_dirty') is not False:
        raise ValueError('Provenance requires a measurement from a clean Git source checkout.')
    if card['meta'].get('git_sha') != inputs['git_sha_full'][:len(card['meta'].get('git_sha') or '')] or not card['meta'].get('git_sha'):
        raise ValueError('Scorecard commit does not match its measurement receipt.')
    if card['meta'].get('gold_sha256') != inputs.get('sha256', {}).get('gold'):
        raise ValueError('Scorecard gold hash does not match its measurement receipt.')
    if capture_inputs(repo, card['meta']['mode'] == 'full') != inputs:
        raise ValueError('Current source, data, model or environment differs from the measured inputs; rerun the scorecard.')
    return receipt
