"""Verify namespace checks without importing project or model dependencies."""
import sys
import types

import pytest

from harness_config import check_anonymizer_origin, load_anonymizer


@pytest.fixture
def namespace(monkeypatch, tmp_path):
    for name in list(sys.modules):
        if name == 'anonymizer' or name.startswith('anonymizer.'):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setattr(sys, 'path', list(sys.path))
    folder = tmp_path / 'src/anonymizer'
    folder.mkdir(parents=True)
    (folder / 'anonymizer.py').touch()
    return folder


def module(name, path):
    result = types.ModuleType(name)
    result.__file__ = str(path)
    return result


def test_selected_source_is_accepted(monkeypatch, namespace):
    core = module('anonymizer.anonymizer', namespace / 'anonymizer.py')
    package = module('anonymizer', namespace / '__init__.py')
    package.__path__ = [str(namespace)]
    monkeypatch.setitem(sys.modules, 'anonymizer', package)
    monkeypatch.setitem(sys.modules, 'anonymizer.anonymizer', core)
    assert load_anonymizer(namespace.parent.parent) is core


@pytest.mark.parametrize('name', ['anonymizer', 'anonymizer.anonymizer', 'anonymizer.helpers.scoring'])
def test_foreign_cached_modules_are_rejected(monkeypatch, namespace, name):
    monkeypatch.setitem(sys.modules, name, module(name, namespace.parent.parent / 'foreign.py'))
    with pytest.raises(ValueError, match='outside the selected source'):
        load_anonymizer(namespace.parent.parent)


def test_mixed_package_search_paths_are_rejected(monkeypatch, namespace):
    package = module('anonymizer', namespace / '__init__.py')
    package.__path__ = [str(namespace), str(namespace.parent.parent / 'foreign')]
    monkeypatch.setitem(sys.modules, 'anonymizer', package)
    with pytest.raises(ValueError, match='Package search path'):
        check_anonymizer_origin(namespace.parent.parent)
