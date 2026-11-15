# Evaluation results

Every number here was produced by `backend/evals/run.py` on the fictional Larkspur Outfitters corpus (DEMO DATA) and its golden question set. LLM-judged metrics are approximate.

| Metric | [2026-11-15-baseline](2026-11-15-baseline.md) | [2026-11-15-chunk-200](2026-11-15-chunk-200.md) | [2026-11-15-local-e5](2026-11-15-local-e5.md) |
|---|---|---|---|
| Chunks in corpus | 10 | 15 | 10 |
| Embedding profile | 2 | 2 | 1 |
| Answer model | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` |
| Recall@1 | 100.0% | 92.9% | 100.0% |
| Recall@3 | 100.0% | 100.0% | 100.0% |
| MRR | 1.000 | 0.958 | 1.000 |
| Refusal accuracy | 100.0% | 100.0% | 97.4% |
| False refusals | 0 | 0 | 1 |
| Refused by gate (no LLM call) | 5 | 5 | 8 |
| Citation validity (as generated) | 100.0% | 100.0% | 100.0% |
| Citation precision | 100.0% | 97.1% | 100.0% |
| Key-point recall (LLM-judged) | 100.0% | 100.0% | 100.0% |
| Faithfulness (LLM-judged) | 100.0% | 96.4% | 100.0% |
| Injection resistance | 100.0% | 100.0% | 100.0% |
| Latency p50 (ms) | 1,380 | 1,322 | 886 |
| Latency p95 (ms) | 3,578 | 2,641 | 2,723 |
| Gate thresholds (hi / lo / kw) | 0.59 / 0.59 / 0.0 | 0.6 / 0.6 / 0.0 | 0.8 / 0.8 / 0.0 |
