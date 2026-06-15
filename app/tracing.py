from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


# Langfuse SDK v3 moved the decorator + context helpers to the top-level package
# (the old `langfuse.decorators` module was removed). We adapt v3's `get_client()`
# API back to the `langfuse_context` interface that `app/agent.py` expects, so the
# rest of the lab code does not need to change. If the SDK is missing or keys are
# not configured, we fall back to no-op shims so the app still runs offline.
try:
    from langfuse import observe  # type: ignore
    from langfuse import get_client  # type: ignore

    class _LangfuseContextV3:
        """Compatibility shim mapping v2 context calls onto the v3 client."""

        def update_current_trace(self, **kwargs: Any) -> None:
            try:
                get_client().update_current_trace(**kwargs)
            except Exception:
                pass

        def update_current_observation(self, **kwargs: Any) -> None:
            # v3 renamed this to update_current_span; usage_details is not a span
            # field there, so forward what is supported and ignore the rest.
            kwargs.pop("usage_details", None)
            try:
                get_client().update_current_span(**kwargs)
            except Exception:
                pass

    langfuse_context = _LangfuseContextV3()

    def span(name: str):
        """Open a child span so each agent step shows as its own bar in the
        Langfuse waterfall. Falls back to a no-op if the span cannot be created."""
        try:
            return get_client().start_as_current_span(name=name)
        except Exception:
            return nullcontext()

except Exception:  # pragma: no cover - SDK absent or incompatible
    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func
        return decorator

    class _DummyContext:
        def update_current_trace(self, **kwargs: Any) -> None:
            return None

        def update_current_observation(self, **kwargs: Any) -> None:
            return None

    langfuse_context = _DummyContext()

    def span(name: str):
        return nullcontext()
