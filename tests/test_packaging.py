"""Packaging guard — keep `pip install -e ".[dev]"` (the README's setup step) working.

Reads pyproject.toml statically (no pip run, no network): setuptools package discovery is pinned to
the real packages so the flat-layout multi-package error can't return, and uvicorn (the README's run
command) is a declared runtime dependency.
"""

import tomllib
from pathlib import Path

PYPROJECT = tomllib.loads(
    (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text(encoding="utf-8")
)


def test_build_backend_declared() -> None:
    backend = PYPROJECT.get("build-system", {}).get("build-backend")
    assert backend, "pyproject must declare a [build-system] build-backend"


def test_packages_are_explicit() -> None:
    # Without an explicit list, setuptools auto-discovery trips over web/profiles/spec/... and refuses
    # to build. Pin exactly the three installable packages.
    packages = PYPROJECT.get("tool", {}).get("setuptools", {}).get("packages")
    assert packages == ["games", "server", "agent"]


def test_uvicorn_is_a_runtime_dependency() -> None:
    # The README's "uvicorn server.main:app" run step must be satisfied by `pip install`.
    deps = PYPROJECT["project"]["dependencies"]
    assert any(dep.replace(" ", "").lower().startswith("uvicorn") for dep in deps)
