"""Model prices for cost estimates (USD per 1M tokens).

Only prices read from the provider's pricing page are listed, with the date and how they were
verified. Models without an entry are reported as "price not configured", never guessed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_m: float
    output_per_m: float | None  # embeddings have no output price
    source: str


PRICES: dict[str, Price] = {
    "gemini-3.5-flash-lite": Price(
        0.30, 2.50, "aistudio.google.com/docs/pricing, read verbatim 2026-11-15 (standard tier)"
    ),
    "gemini-embedding-2": Price(
        0.20, None, "aistudio.google.com/docs/pricing, 2026-11-15 (from a page summary; re-check)"
    ),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int = 0) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    total = input_tokens * price.input_per_m / 1_000_000
    if price.output_per_m is not None:
        total += output_tokens * price.output_per_m / 1_000_000
    return total
