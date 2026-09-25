"""Lightweight package init (lazy re-exports).

`embeddings`/`index` pull torch/chromadb and `agent`/`llm` pull langchain;
eager imports would force the full env on every lightweight
`from retrieval.qa import ...`. Attributes resolve lazily instead.
"""

from __future__ import annotations

_LAZY_EXPORTS = {
    "build_agent": ".agent",
    "run_agent_question": ".agent",
    "MiniLMEmbeddings": ".embeddings",
    "LocalEmbeddingIndex": ".index",
    "SearchResult": ".index",
    "build_llm": ".llm",
    "AnswerResult": ".qa",
    "answer_question": ".qa",
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
