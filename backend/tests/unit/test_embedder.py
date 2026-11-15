"""Local embedder pooling maths, with a stub ONNX session (no model download)."""

from __future__ import annotations

import threading
from typing import Any

import numpy as np
from tokenizers import Tokenizer, models, pre_tokenizers

from app.embedder.main import Model


class StubSession:
    """Returns token embeddings where the padding position holds a huge value."""

    def run(self, _outputs: Any, feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        ids = feeds["input_ids"]
        hidden = np.ones((*ids.shape, 4), dtype=np.float32)
        hidden[:, :, 0] = ids  # first dimension encodes the token id
        hidden[feeds["attention_mask"] == 0] = 1000.0  # must be ignored by pooling
        return [hidden]


def make_model() -> Model:
    tokenizer = Tokenizer(
        models.WordLevel({"<pad>": 0, "a": 1, "b": 2, "c": 3, "[UNK]": 4}, unk_token="[UNK]")
    )
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.enable_padding(pad_id=0, pad_token="<pad>")
    return Model(StubSession(), tokenizer, {"input_ids", "attention_mask"}, threading.Lock())  # type: ignore[arg-type]


def test_mean_pooling_ignores_padding_and_normalizes() -> None:
    vectors = make_model().embed(["a b c", "a"])
    assert vectors.shape == (2, 4)
    np.testing.assert_allclose(np.linalg.norm(vectors, axis=1), [1.0, 1.0], rtol=1e-6)
    # "a" alone: hidden = [1, 1, 1, 1] -> normalized 0.5 each; padding (1000s) did not leak in.
    np.testing.assert_allclose(vectors[1], [0.5, 0.5, 0.5, 0.5], rtol=1e-6)
    # "a b c": mean of ids 1, 2, 3 is 2 in dimension 0.
    expected = np.array([2.0, 1.0, 1.0, 1.0])
    np.testing.assert_allclose(vectors[0], expected / np.linalg.norm(expected), rtol=1e-6)
