import os

import pytest

import harness_config as config


def test_repo_requires_real_source_and_has_no_neighbour_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv('ANONYMIZER_REPO', raising=False)
    monkeypatch.setattr(config, 'HERE', tmp_path / 'harness')
    with pytest.raises(ValueError):
        config.repo_root()
    source = tmp_path / 'src/anonymizer'
    source.mkdir(parents=True)
    (source / 'anonymizer.py').touch()
    (tmp_path / 'pyproject.toml').touch()
    assert config.repo_root() == tmp_path
    with pytest.raises(ValueError):
        config.repo_root(tmp_path / 'absent')


def test_model_is_explicit_and_offline(monkeypatch, tmp_path):
    monkeypatch.delenv('GLINER_MODEL_PATH', raising=False)
    with pytest.raises(ValueError):
        config.model_root()
    with pytest.raises(ValueError):
        config.model_root(tmp_path)
    for name in ('gliner_config.json', 'model.safetensors'):
        (tmp_path / name).touch()
    monkeypatch.setenv('HF_HUB_OFFLINE', '0')
    monkeypatch.setenv('TRANSFORMERS_OFFLINE', '0')
    assert config.model_root(tmp_path) == tmp_path
    assert os.environ['HF_HUB_OFFLINE'] == os.environ['TRANSFORMERS_OFFLINE'] == '1'
