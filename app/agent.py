from __future__ import annotations

import time
from dataclasses import dataclass

from . import metrics
from .mock_llm import FakeLLM
from .mock_rag import retrieve
from .pii import hash_user_id, summarize_text
from .tracing import langfuse_context, observe, span


# Per-million-token pricing (input, output) in USD. Routing short/simple queries
# to the cheaper Haiku tier is the cost-optimization lever measured in
# scripts/cost_benchmark.py.
PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
}
CHEAP_MODEL = "claude-haiku-4-5"
ROUTE_LEN_THRESHOLD = 60  # queries shorter than this go to the cheaper model


@dataclass
class AgentResult:
    answer: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    cost_usd: float
    quality_score: float
    model: str


class LabAgent:
    def __init__(self, model: str = "claude-sonnet-4-5", enable_routing: bool = True) -> None:
        self.model = model
        self.enable_routing = enable_routing
        self._llms: dict[str, FakeLLM] = {}

    def _llm_for(self, model: str) -> FakeLLM:
        if model not in self._llms:
            self._llms[model] = FakeLLM(model=model)
        return self._llms[model]

    def _select_model(self, message: str, feature: str) -> str:
        # Short / simple requests do not need the flagship model; route them to
        # the cheaper tier to cut spend without measurable quality loss.
        if self.enable_routing and len(message) < ROUTE_LEN_THRESHOLD:
            return CHEAP_MODEL
        return self.model

    @observe()
    def run(self, user_id: str, feature: str, session_id: str, message: str) -> AgentResult:
        started = time.perf_counter()
        model = self._select_model(message, feature)
        llm = self._llm_for(model)
        with span("retrieve"):
            docs = retrieve(message)
        prompt = f"Feature={feature}\nDocs={docs}\nQuestion={message}"
        with span("llm.generate"):
            response = llm.generate(prompt)
        quality_score = self._heuristic_quality(message, response.text, docs)
        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_usd = self._estimate_cost(model, response.usage.input_tokens, response.usage.output_tokens)

        langfuse_context.update_current_trace(
            user_id=hash_user_id(user_id),
            session_id=session_id,
            tags=["lab", feature, model],
        )
        langfuse_context.update_current_observation(
            metadata={"doc_count": len(docs), "query_preview": summarize_text(message), "model": model},
            usage_details={"input": response.usage.input_tokens, "output": response.usage.output_tokens},
        )

        metrics.record_request(
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            quality_score=quality_score,
        )

        return AgentResult(
            answer=response.text,
            latency_ms=latency_ms,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
            cost_usd=cost_usd,
            quality_score=quality_score,
            model=model,
        )

    def _estimate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        in_price, out_price = PRICING.get(model, PRICING["claude-sonnet-4-5"])
        input_cost = (tokens_in / 1_000_000) * in_price
        output_cost = (tokens_out / 1_000_000) * out_price
        return round(input_cost + output_cost, 6)

    def _heuristic_quality(self, question: str, answer: str, docs: list[str]) -> float:
        score = 0.5
        if docs:
            score += 0.2
        if len(answer) > 40:
            score += 0.1
        if question.lower().split()[0:1] and any(token in answer.lower() for token in question.lower().split()[:3]):
            score += 0.1
        if "[REDACTED" in answer:
            score -= 0.2
        return round(max(0.0, min(1.0, score)), 2)
