"""Portable harness configuration; no project or model path is inferred from neighbours."""
import os
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def check_anonymizer_origin(repo):
    """Reject cached project modules or package search paths from another checkout."""
    expected = (Path(repo) / 'src/anonymizer').resolve()
    for name, module in list(sys.modules.items()):
        if name != 'anonymizer' and not name.startswith('anonymizer.'):
            continue
        location = getattr(module, '__file__', None)
        if not location or not Path(location).resolve().is_relative_to(expected):
            raise ValueError(f'Loaded module {name} is outside the selected source checkout; use a fresh process.')
        for path in getattr(module, '__path__', []):
            if not Path(path).resolve().is_relative_to(expected):
                raise ValueError(f'Package search path for {name} is outside the selected source checkout.')


def load_anonymizer(repo):
    """Import the chosen source and verify both cached and newly loaded modules."""
    root = repo_root(repo)
    check_anonymizer_origin(root)
    sys.path.insert(0, str(root / 'src'))
    module = importlib.import_module('anonymizer.anonymizer')
    check_anonymizer_origin(root)
    if Path(module.__file__).resolve() != (root / 'src/anonymizer/anonymizer.py').resolve():
        raise ValueError('The loaded anonymizer module does not match the selected source file.')
    return module

def repo_root(value=None):
    explicit = value or os.environ.get('ANONYMIZER_REPO')
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not (root / 'src/anonymizer/anonymizer.py').is_file():
            raise ValueError('ANONYMIZER_REPO must point to the repository containing src/anonymizer.')
        return root
    for root in HERE.parents:
        if (root / 'pyproject.toml').is_file() and (root / 'src/anonymizer/anonymizer.py').is_file():
            return root
    raise ValueError('Set ANONYMIZER_REPO to the source repository; automatic discovery requires the harness to be inside that repository.')

def model_root(value=None):
    value = value or os.environ.get('GLINER_MODEL_PATH')
    if not value:
        raise ValueError('Model runs require GLINER_MODEL_PATH pointing to a local model; automatic downloads are disabled.')
    root = Path(value).expanduser().resolve()
    for name in ['gliner_config.json', 'model.safetensors']:
        if not (root / name).is_file():
            raise ValueError(f'Missing model file: {name}')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    return root
