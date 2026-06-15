# Day 13 Observability Lab Report

> **Instruction**: Fill in all sections below. This report is designed to be parsed by an automated grading assistant. Ensure all tags (e.g., `[GROUP_NAME]`) are preserved.

## 1. Team Metadata
- [GROUP_NAME]: Huynh An Nghiep (2A202600853) — Individual submission
- [REPO_URL]: https://github.com/anhuynh219/2A202600853-Huynh_An_Nghiep-Day13
- [MEMBERS]:
  - Member A: Huynh An Nghiep | Role: Logging & PII
  - Member B: Huynh An Nghiep | Role: Tracing & Enrichment
  - Member C: Huynh An Nghiep | Role: SLO & Alerts
  - Member D: Huynh An Nghiep | Role: Load Test & Dashboard
  - Member E: Huynh An Nghiep | Role: Demo & Report

---

## 2. Group Performance (Auto-Verified)
- [VALIDATE_LOGS_FINAL_SCORE]: 100/100
- [TOTAL_TRACES_COUNT]: 50+ (verified via Langfuse API; >10 required)
- [PII_LEAKS_FOUND]: 0

---

## 3. Technical Evidence (Group)

### 3.1 Logging & Tracing
- [EVIDENCE_CORRELATION_ID_SCREENSHOT]: docs/evidence/correlation_id.png  <!-- TODO: chụp header x-request-id hoặc 2 dòng log cùng req-id -->
- [EVIDENCE_PII_REDACTION_SCREENSHOT]: docs/evidence/pii_redaction.png  <!-- TODO: chụp dòng log có [REDACTED_EMAIL]/[REDACTED_CREDIT_CARD] -->
- [EVIDENCE_TRACE_WATERFALL_SCREENSHOT]: docs/evidence/trace_waterfall.png
- [TRACE_WATERFALL_EXPLANATION]: In the `rag_slow` trace, the parent span `run` took 2.652s. Its child span `retrieve` (RAG vector lookup) accounts for 2.501s, while the child span `llm.generate` took only 0.151s. This proves the latency bottleneck is the retrieval step, not the LLM — the textbook Metrics→Traces→Logs drill-down that localizes the root cause.

### 3.2 Dashboard & SLOs
- [DASHBOARD_6_PANELS_SCREENSHOT]: [Path to image]
- [SLO_TABLE]:
| SLI | Target | Window | Current Value |
|---|---:|---|---:|
| Latency P95 | < 3000ms | 28d | 150ms (healthy) / 2663ms during rag_slow |
| Error Rate | < 2% | 28d | 0% |
| Cost Budget | < $2.5/day | 1d | ~$0.002 avg/req |

### 3.3 Alerts & Runbook
- [ALERT_RULES_SCREENSHOT]: docs/evidence/alert_rules.png  <!-- TODO: chụp config/alert_rules.yaml -->
- [SAMPLE_RUNBOOK_LINK]: docs/alerts.md#1-high-latency-p95 (3 rules defined in config/alert_rules.yaml: high_latency_p95, high_error_rate, cost_budget_spike)

---

## 4. Incident Response (Group)
- [SCENARIO_NAME]: rag_slow
- [SYMPTOMS_OBSERVED]: Latency P95 jumped from 150ms (baseline) to 2663ms after injection (`/metrics`), while error_rate stayed 0% and avg_cost_usd stayed ~$0.002 — isolating the problem to latency, not errors or cost.
- [ROOT_CAUSE_PROVED_BY]: Langfuse trace `run` shows total latency ≈2.65s with the time spent inside the retrieval (RAG) step, not the LLM step (LLM only sleeps 0.15s). Confirmed in logs by `response_sent` line with `"latency_ms": 2663`. Root cause = artificial 2.5s `time.sleep` in `app/mock_rag.py::retrieve` when the `rag_slow` toggle is on (a slow vector store).
- [FIX_ACTION]: Disabled the incident via `POST /incidents/rag_slow/disable`; in production this maps to adding a retrieval timeout + fallback to a faster replica / cached docs.
- [PREVENTIVE_MEASURE]: Add a P95-latency alert (already in `config/alert_rules.yaml`: `high_latency_p95`), set a hard timeout on the RAG call, and emit a dedicated span for retrieval so the slow step is immediately visible in the trace waterfall.

---

## 5. Individual Contributions & Evidence

> Individual submission — all roles completed by Huynh An Nghiep.

### Huynh An Nghiep — Logging & PII (Member A)
- [TASKS_COMPLETED]: Added Vietnamese passport + address PII regex and enabled the `scrub_event` processor in the structlog pipeline so email/phone/CCCD/credit-card/passport/address are redacted before logs are written. Verified 0 PII leaks via `validate_logs.py`.
- [EVIDENCE_LINK]: commit d534d87 (app/pii.py, app/logging_config.py)

### Huynh An Nghiep — Tracing & Enrichment (Member B)
- [TASKS_COMPLETED]: Implemented the correlation-ID middleware; enriched every /chat log with user_id_hash/session_id/feature/model/env; fixed Langfuse v3 SDK incompatibility (removed `langfuse.decorators`) and added `retrieve`/`llm.generate` child spans for waterfall drill-down. 50+ traces live.
- [EVIDENCE_LINK]: commits dc27ca0 (middleware), 6cd91d7 (tracing), 62c4f2c (enrichment)

### Huynh An Nghiep — SLO & Alerts (Member C)
- [TASKS_COMPLETED]: Reviewed `config/slo.yaml` targets (P95<3000ms, error<2%, cost<$2.5/day, quality≥0.75) and the 3 alert rules in `config/alert_rules.yaml` with runbook links in `docs/alerts.md`.
- [EVIDENCE_LINK]: config/slo.yaml, config/alert_rules.yaml, docs/alerts.md

### Huynh An Nghiep — Load Test & Dashboard (Member D)
- [TASKS_COMPLETED]: Ran load tests (concurrency 5) and built a same-origin self-refreshing 6-panel dashboard at `GET /dashboard` with SLO threshold lines that turn red on breach.
- [EVIDENCE_LINK]: commit 62c4f2c (app/main.py, docs/dashboard.html)

### Huynh An Nghiep — Demo & Report (Member E)
- [TASKS_COMPLETED]: Injected the `rag_slow` incident, performed the Metrics→Traces→Logs root-cause analysis, and authored this report.
- [EVIDENCE_LINK]: Section 4 above; docs/evidence/trace_waterfall.png

---

## 6. Bonus Items (Optional)
- [BONUS_COST_OPTIMIZATION]: Cost is tracked live (`avg_cost_usd`, `total_cost_usd`) and the `cost_spike` incident (output tokens x4) is observable on the dashboard cost panel — baseline ~$0.0018/req vs ~4x during spike.
- [BONUS_AUDIT_LOGS]: AUDIT_LOG_PATH is wired in `.env` for a separate audit stream (optional extension).
- [BONUS_CUSTOM_METRIC]: Automation — same-origin self-refreshing 6-panel dashboard served by the app at `GET /dashboard` (`docs/dashboard.html`), with SLO threshold lines that turn red on breach; plus per-step trace spans (`retrieve`, `llm.generate`) for waterfall drill-down. Evidence: commits `62c4f2c` (dashboard) and `6cd91d7` (spans).
