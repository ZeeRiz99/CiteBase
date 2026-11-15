"""Build docs/evals/README.md: a side-by-side table of every report in the directory.

docker compose run --rm --no-deps -u root -v ./docs/evals:/out api python -m evals.compare /out
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROWS: list[tuple[str, str]] = [
    ("Recall@1", "recall_at_1"),
    ("Recall@3", "recall_at_3"),
    ("MRR", "mrr"),
    ("Refusal accuracy", "refusal_accuracy"),
    ("False refusals", "false_refusals"),
    ("Refused by gate (no LLM call)", "gate_refusals"),
    ("Citation validity (as generated)", "raw_citation_validity"),
    ("Citation precision", "citation_precision"),
    ("Key-point recall (LLM-judged)", "key_point_recall"),
    ("Faithfulness (LLM-judged)", "faithfulness"),
    ("Injection resistance", "injection_resistance"),
    ("Latency p50 (ms)", "latency_p50_ms"),
    ("Latency p95 (ms)", "latency_p95_ms"),
]


def fmt(key: str, value: Any) -> str:
    if value is None:
        return "n/a"
    if key == "mrr":
        return f"{value:.3f}"
    if key.endswith("_ms"):
        return f"{value:,.0f}"
    if isinstance(value, float):
        return f"{value:.1%}"
    return str(value)


def build(directory: Path) -> Path:
    reports = sorted(directory.glob("*.json"))
    data = [(p.stem, json.loads(p.read_text(encoding="utf-8"))) for p in reports]
    header = "| Metric | " + " | ".join(f"[{stem}]({stem}.md)" for stem, _ in data) + " |"
    lines = [
        "# Evaluation results",
        "",
        "Every number here was produced by `backend/evals/run.py` on the fictional Larkspur Outfitters "
        "corpus (DEMO DATA) and its golden question set. LLM-judged metrics are approximate.",
        "",
        header,
        "|---|" + "---|" * len(data),
        "| Chunks in corpus | " + " | ".join(str(d["ingest"]["chunks"]) for _, d in data) + " |",
        "| Embedding profile | "
        + " | ".join(str(d["config"]["embedding_profile"]) for _, d in data)
        + " |",
        "| Answer model | " + " | ".join(f"`{d['config']['llm_model']}`" for _, d in data) + " |",
    ]
    for label, key in ROWS:
        lines.append(
            f"| {label} | " + " | ".join(fmt(key, d["summary"].get(key)) for _, d in data) + " |"
        )
    lines.append(
        "| Gate thresholds (hi / lo / kw) | "
        + " | ".join(
            f"{d['thresholds']['vec_hi']} / {d['thresholds']['vec_lo']} / {d['thresholds']['kw_coverage']}"
            for _, d in data
        )
        + " |"
    )
    path = directory / "README.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(build(Path(sys.argv[1] if len(sys.argv) > 1 else "eval-reports")))
