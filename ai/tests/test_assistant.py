"""Contract and privacy tests for :mod:`ai.assistant`."""

from __future__ import annotations

import inspect
from types import ModuleType

import pytest


@pytest.fixture(scope="module")
def assistant_module() -> ModuleType:
    """Import the assistant without starting a server or model download."""

    try:
        import ai.assistant as module
    except Exception as exc:  # pragma: no cover - improves failure message
        pytest.fail(f"ai.assistant could not be imported: {exc!r}")
    return module


def public_callables(module: ModuleType) -> dict[str, object]:
    return {
        name: value
        for name, value in vars(module).items()
        if not name.startswith("_")
        and (inspect.isfunction(value) or inspect.isclass(value))
        and getattr(value, "__module__", None) == module.__name__
    }


def test_assistant_module_has_public_interface(assistant_module: ModuleType) -> None:
    """The assistant module must expose at least one application interface."""

    available = public_callables(assistant_module)
    assert available, "ai.assistant has no public class or function"


def test_assistant_declared_exports_exist(assistant_module: ModuleType) -> None:
    """Every name listed in __all__ must really exist."""

    exports = getattr(assistant_module, "__all__", ())
    assert isinstance(exports, (tuple, list))
    missing = [name for name in exports if not hasattr(assistant_module, name)]
    assert missing == []


def test_assistant_source_contains_no_embedded_credentials(
    assistant_module: ModuleType,
) -> None:
    """Reject obvious hard-coded production credentials."""

    source = inspect.getsource(assistant_module).lower()
    forbidden_assignments = (
        "api_key = \"sk-",
        "api_key='sk-",
        "authorization = \"bearer ",
        "password = \"",
    )
    assert not any(item in source for item in forbidden_assignments)


def test_assistant_does_not_initialize_on_import(assistant_module: ModuleType) -> None:
    """Importing the module must not create a non-daemon worker thread."""

    import threading

    unexpected = [
        thread
        for thread in threading.enumerate()
        if thread is not threading.main_thread() and not thread.daemon
    ]
    assert unexpected == []

