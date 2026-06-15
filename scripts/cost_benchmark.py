"""Measure the cost impact of model routing (before vs after).

Routing sends short/simple queries to a cheaper model tier. We replay the same
sample queries with routing OFF (baseline, all flagship) and ON (optimized), using
a fixed RNG seed so token counts are identical between runs and only the pricing
differs. Run with:  uv run python scripts/cost_benchmark.py
"""
from __future__ import annotations

import logging
import random
import sys
from pathlib import Path
from statistics import mean

# This benchmark runs the agent offline (no Langfuse keys), so silence the
# tracing SDK's "client disabled / no active span" warnings — they are expected
# here and only add noise.
for _name in ("langfuse", "opentelemetry"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json

from app.agent import LabAgent

QUERIES = Path("data/sample_queries.jsonl")


def run(enable_routing: bool) -> dict:
    random.seed(42)  # identical token draws across both runs => fair comparison
    agent = LabAgent(enable_routing=enable_routing)
    costs, qualities, models = [], [], []
    for line in QUERIES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        r = agent.run(q["user_id"], q["feature"], q["session_id"], q["message"])
        costs.append(r.cost_usd)
        qualities.append(r.quality_score)
        models.append(r.model)
    return {
        "total_cost": round(sum(costs), 6),
        "avg_quality": round(mean(qualities), 4),
        "cheap_calls": sum(1 for m in models if m != "claude-sonnet-4-5"),
        "total_calls": len(models),
    }


def main() -> None:
    before = run(enable_routing=False)
    after = run(enable_routing=True)
    saved = before["total_cost"] - after["total_cost"]
    pct = (saved / before["total_cost"] * 100) if before["total_cost"] else 0.0

    print("=== Cost Optimization: Model Routing (before vs after) ===")
    print(f"{'':14}{'BEFORE (all sonnet)':>22}{'AFTER (routed)':>18}")
    print(f"{'total_cost':14}{before['total_cost']:>22}{after['total_cost']:>18}")
    print(f"{'avg_quality':14}{before['avg_quality']:>22}{after['avg_quality']:>18}")
    print(f"{'cheap_calls':14}{before['cheap_calls']:>22}{after['cheap_calls']:>18}")
    print("-" * 54)
    print(f"Saved ${saved:.6f}  ({pct:.1f}% lower cost)  |  quality "
          f"{before['avg_quality']} -> {after['avg_quality']}")


if __name__ == "__main__":
    main()
