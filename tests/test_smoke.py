"""Smoke test — the toolchain runs and the package layout resolves on a fresh checkout.

No LLM, no network, no paid call: this only proves ``pytest`` is green and the §2 packages import.
"""

import importlib


def test_toolchain_runs() -> None:
    """pytest collects and runs at all."""
    assert True


def test_packages_import() -> None:
    """The Python packages from architecture.md §2 are importable (repo root on sys.path)."""
    for package in ("games", "server", "agent"):
        module = importlib.import_module(package)
        assert module is not None
