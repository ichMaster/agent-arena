"""Smoke test: the toolchain runs and the package layout imports (ARENA-OPUS-OPUS-001).

No LLM, no network, no paid call — just proves a fresh checkout is `pytest`-green and the three
Python packages resolve for imports + mypy.
"""


def test_packages_import() -> None:
    import agent  # noqa: F401
    import games  # noqa: F401
    import server  # noqa: F401


def test_toolchain_runs() -> None:
    assert True
