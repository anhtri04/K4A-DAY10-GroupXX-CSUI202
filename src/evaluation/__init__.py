"""Lightweight package init (lazy re-exports).

`metrics` pulls heavy deps (datasets, langchain, chroma...); importing it
eagerly would force the full env on every
`from evaluation.testset import ...` (CP2 needs only `pandas` + stdlib).
"""

from __future__ import annotations

_LAZY_EXPORTS = {
    "EvaluationBundle": ".metrics",
    "JudgeVerdict": ".metrics",
    "evaluate_pipeline": ".metrics",
    "build_test_set": ".testset",
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    module = importlib.import_module(_LAZY_EXPORTS[name], package=__name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
