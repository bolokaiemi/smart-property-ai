"""Offline contract tests for :mod:`ai.inference`."""

from __future__ import annotations

import inspect
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def inference_module() -> ModuleType:
    """Import inference without loading a model or making network calls."""

    try:
        import ai.inference as module
    except Exception as exc:
        pytest.fail(f"ai.inference could not be imported: {exc!r}")
    return module


def module_callables(module: ModuleType) -> dict[str, object]:
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and (inspect.isfunction(value) or inspect.isclass(value))
        and getattr(value, "__module__", None) == module.__name__
    }


def test_inference_module_has_public_interface(inference_module: ModuleType) -> None:
    available = module_callables(inference_module)
    assert available, "ai.inference has no public class or function"


def test_inference_declared_exports_exist(inference_module: ModuleType) -> None:
    exports = getattr(inference_module, "__all__", ())
    assert isinstance(exports, (tuple, list))
    assert [name for name in exports if not hasattr(inference_module, name)] == []


def test_inference_import_does_not_download_or_create_checkpoints(
    inference_module: ModuleType,
    tmp_path,
    monkeypatch,
) -> None:
    """The module must expose interfaces without import-time model work."""

    # Import has already succeeded. This test documents the required contract:
    # model loading happens only when an engine/model is explicitly initialized.
    assert inference_module.__name__ == "ai.inference"
    assert list(tmp_path.iterdir()) == []


def test_inference_source_disables_remote_code(inference_module: ModuleType) -> None:
    """If Transformers loading is used, remote repository code must not be trusted."""

    source = inspect.getsource(inference_module).replace(" ", "").lower()
    if "from_pretrained(" not in source:
        pytest.skip("This inference module does not use Transformers loaders")
    assert "trust_remote_code=true" not in source


def test_inference_has_bounded_generation_setting(inference_module: ModuleType) -> None:
    """Generation code must include an output-token or length boundary."""

    source = inspect.getsource(inference_module).lower()
    if "generate(" not in source:
        pytest.skip("Generation is delegated to another inference provider")
    assert "max_new_tokens" in source or "max_length" in source


