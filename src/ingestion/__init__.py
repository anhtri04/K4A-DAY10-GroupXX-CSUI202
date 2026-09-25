"""Lightweight package init (lazy re-exports).

Eagerly importing cleaning/corruption here would force `pandas` on every
`from ingestion.crossref import ...` (CP0 needs only `requests` + stdlib),
so we resolve attributes lazily instead.
"""

from __future__ import annotations

_LAZY_EXPORTS = {
    "build_clean_dataframe": ".cleaning",
    "corrupt_clean_dataframe": ".corruption",
    "PaperRecord": ".crossref",
    "fetch_source_records": ".crossref",
    "load_raw_records": ".crossref",
    "parse_crossref_payload": ".crossref",
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
