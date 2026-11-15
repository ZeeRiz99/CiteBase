"""Local embedding service: intfloat/multilingual-e5-small (MIT) on CPU via ONNX Runtime.

Used by embedding profile 1. Clients add the "query: " / "passage: " prefixes the model expects.
The model files are downloaded once from Hugging Face into the HF_HOME volume.

    uvicorn app.embedder.main:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from huggingface_hub import hf_hub_download
from pydantic import BaseModel, Field, StringConstraints
from tokenizers import Tokenizer

MODEL_ID = os.environ.get("EMBEDDER_MODEL", "intfloat/multilingual-e5-small")
MAX_TOKENS = 512
THREADS = int(os.environ.get("EMBEDDER_THREADS", "2"))

Text = Annotated[str, StringConstraints(max_length=20_000)]


class EmbedRequest(BaseModel):
    texts: list[Text] = Field(min_length=1, max_length=64)


class EmbedResponse(BaseModel):
    model: str
    dimension: int
    vectors: list[list[float]]


@dataclass
class Model:
    session: ort.InferenceSession
    tokenizer: Tokenizer
    input_names: set[str]
    lock: threading.Lock

    @classmethod
    def load(cls) -> Model:
        model_path = hf_hub_download(MODEL_ID, "onnx/model.onnx")
        tokenizer = Tokenizer.from_file(hf_hub_download(MODEL_ID, "tokenizer.json"))
        tokenizer.enable_truncation(MAX_TOKENS)
        pad_id = tokenizer.token_to_id("<pad>")
        tokenizer.enable_padding(
            pad_id=pad_id if pad_id is not None else 0,
            pad_token="<pad>",  # noqa: S106 - tokenizer padding token, not a credential
        )
        options = ort.SessionOptions()
        options.intra_op_num_threads = THREADS
        session = ort.InferenceSession(model_path, options, providers=["CPUExecutionProvider"])
        return cls(session, tokenizer, {i.name for i in session.get_inputs()}, threading.Lock())

    def embed(self, texts: list[str]) -> np.ndarray:
        encodings = self.tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encodings], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        with self.lock:
            hidden = np.asarray(self.session.run(None, feeds)[0], dtype=np.float32)  # (b, t, d)
        # Mean pooling over real tokens, then L2 normalisation (as the model card specifies).
        weights = mask[..., None].astype(np.float32)
        pooled = (hidden * weights).sum(axis=1) / np.clip(weights.sum(axis=1), 1e-9, None)
        normalized: np.ndarray = pooled / np.clip(
            np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None
        )
        return normalized


state: dict[str, Model] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    state["model"] = await run_in_threadpool(Model.load)
    yield
    state.clear()


app = FastAPI(title="CiteBase local embedder", lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok" if "model" in state else "loading", "model": MODEL_ID}


@app.post("/embed")
async def embed(body: EmbedRequest) -> EmbedResponse:
    vectors = await run_in_threadpool(state["model"].embed, body.texts)
    return EmbedResponse(
        model=MODEL_ID, dimension=int(vectors.shape[1]), vectors=vectors.round(7).tolist()
    )
