"""Chat API end to end: SSE turns, persistence, refusals, feedback, limits, stop, isolation.

Real Postgres + pgvector; fake embedder and fake LLMs (no network, no cost).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import set_tenant
from app.models import Workspace
from app.providers.http import ProviderError, ProviderNotConfigured
from app.providers.llm import FakeLLM, GenerationParams, LLMChunk, LLMMessage, LLMUsage
from app.rag.constants import REFUSAL_TEXT
from app.rag.engine import EngineConfig, RagEngine
from app.rag.factory import build_engine
from app.repositories import workspaces as ws_repo
from app.services.chat import Actor, ChatService
from tests.conftest import Api, Mailbox
from tests.integration.test_rag import FAKE_THRESHOLDS, LEAVE, SHIPPING, ingest, me

LEAVE_Q = "How many days of annual leave do new employees receive?"
OFF_TOPIC = "What is the boiling point of mercury on Jupiter?"


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events: list[tuple[str, Any]] = []
    for block in body.strip().split("\n\n"):
        name, data = None, None
        for line in block.splitlines():
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if name:
            events.append((name, data))
    return events


def rewrite_responder(system: str, messages: list[LLMMessage]) -> str:
    """Cheap-model stand-in: the rewritten question is the latest question, marked."""
    latest = messages[-1].content.rsplit("Latest question:", 1)[-1].strip()
    return f"standalone: {latest}"


def factory(
    llm: Any = None, cheap: FakeLLM | None = None
) -> Callable[[AsyncSession, Settings, Workspace, httpx.AsyncClient], RagEngine]:
    def build(
        db: AsyncSession, settings: Settings, workspace: Workspace, http: httpx.AsyncClient
    ) -> RagEngine:
        return build_engine(
            db,
            settings,
            workspace,
            http,
            config=EngineConfig(thresholds=FAKE_THRESHOLDS),
            llm=llm or FakeLLM(),
            cheap_llm=cheap or FakeLLM(responder=rewrite_responder),
        )

    return build


@pytest.fixture(autouse=True)
def fake_engine(app: FastAPI) -> None:
    app.state.engine_factory = factory()


@pytest.fixture
async def kb(api: Api, mailbox: Mailbox) -> dict[str, Any]:
    await api.register()
    await ingest(api, mailbox, "Leave Policy.txt", LEAVE)
    await ingest(api, mailbox, "Shipping.txt", SHIPPING)
    return await me(api)


async def new_conversation(api: Api) -> str:
    response = await api.post("/api/v1/conversations", {})
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def ask(api: Api, conversation_id: str, question: str) -> httpx.Response:
    return await api.post(
        f"/api/v1/conversations/{conversation_id}/messages", {"question": question}
    )


async def ask_events(api: Api, conversation_id: str, question: str) -> list[tuple[str, Any]]:
    response = await ask(api, conversation_id, question)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_sse(response.text)


def done_message(events: list[tuple[str, Any]]) -> dict[str, Any]:
    assert events[-1][0] == "done"
    return dict(events[-1][1]["message"])


async def test_answer_streams_with_citations_and_is_saved(api: Api, kb: dict[str, Any]) -> None:
    cid = await new_conversation(api)
    events = await ask_events(api, cid, LEAVE_Q)
    names = [name for name, _ in events]
    assert names[0] == "meta" and names[-2:] == ["citations", "done"]
    assert "token" in names

    meta = events[0][1]
    assert meta["conversation_id"] == cid and meta["evidence"] in ("strong", "partial")
    streamed = "".join(d["text"] for n, d in events if n == "token")
    message = done_message(events)
    assert message["status"] == "complete"
    assert message["content"] == streamed and "[1]" in message["content"]
    cited = [s for s in message["sources"] if s["cited"]]
    assert cited and cited[0]["document_title"] == "Leave Policy"
    assert message["sources"][0]["cited"]  # cited sources come first
    assert events[-2][1]["citations"] == cited

    thread = (await api.get(f"/api/v1/conversations/{cid}")).json()
    assert [m["role"] for m in thread["messages"]] == ["user", "assistant"]
    assert thread["title"] == LEAVE_Q
    assert thread["messages"][1]["content"] == message["content"]


async def test_refusal_is_logged_and_counted(
    api: Api, kb: dict[str, Any], owner_engine: Any
) -> None:
    cid = await new_conversation(api)
    await ask_events(api, cid, LEAVE_Q)
    events = await ask_events(api, cid, OFF_TOPIC)
    refusal = dict(events)["refusal"]
    assert refusal == {"text": REFUSAL_TEXT, "reason": "gate"}
    message = done_message(events)
    assert message["status"] == "refused" and message["refusal_reason"] == "gate"

    listing = (await api.get("/api/v1/unanswered-questions")).json()
    assert listing["total"] == 1 and listing["items"][0]["status"] == "open"
    assert listing["items"][0]["question"] == OFF_TOPIC

    summary = (await api.get("/api/v1/dashboard/summary")).json()
    assert summary["questions"]["last_7d"] == 2
    assert summary["questions"]["unanswered_open"] == 1

    item = listing["items"][0]["id"]
    updated = await api.patch(f"/api/v1/unanswered-questions/{item}", {"status": "resolved"})
    assert updated.json()["status"] == "resolved"
    assert (await api.get("/api/v1/unanswered-questions?status=open")).json()["total"] == 0

    with owner_engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.workspace_id', :w, true)"), {"w": kb["workspace"]["id"]}
        )
        events_logged = conn.execute(
            text("SELECT count(*) FROM domain_events WHERE event_type = 'question.unanswered'")
        ).scalar_one()
    assert events_logged == 1


async def test_follow_up_is_rewritten_with_history(
    app: FastAPI, api: Api, kb: dict[str, Any]
) -> None:
    cheap = FakeLLM(responder=rewrite_responder)
    app.state.engine_factory = factory(cheap=cheap)
    cid = await new_conversation(api)
    await ask_events(api, cid, LEAVE_Q)
    assert cheap.calls == []  # first question: no rewrite

    await ask_events(api, cid, "And do unused days carry over?")
    assert len(cheap.calls) == 1
    transcript = cheap.calls[0][1][-1].content
    assert LEAVE_Q in transcript and "Annual leave policy. [1]" in transcript

    trace_id = (await api.get(f"/api/v1/conversations/{cid}")).json()["messages"][-1]["id"]
    trace = (await api.get(f"/api/v1/messages/{trace_id}/trace")).json()
    assert trace["standalone_query"] == "standalone: And do unused days carry over?"


async def test_regenerate_replaces_only_the_latest_answer(api: Api, kb: dict[str, Any]) -> None:
    cid = await new_conversation(api)
    first = done_message(await ask_events(api, cid, LEAVE_Q))
    second = done_message(
        await ask_events(api, cid, "When does Express delivery to Germany arrive?")
    )

    stale = await api.post(f"/api/v1/messages/{first['id']}/regenerate")
    assert stale.status_code == 409

    response = await api.post(f"/api/v1/messages/{second['id']}/regenerate")
    assert response.status_code == 200, response.text
    regenerated = done_message(parse_sse(response.text))
    assert regenerated["regenerated_from_id"] == second["id"]

    messages = (await api.get(f"/api/v1/conversations/{cid}")).json()["messages"]
    assert [m["id"] for m in messages if m["role"] == "assistant"] == [
        first["id"],
        regenerated["id"],
    ]


async def test_feedback_updates_helpful_rate(
    api: Api, kb: dict[str, Any], owner_engine: Any
) -> None:
    cid = await new_conversation(api)
    answer = done_message(await ask_events(api, cid, LEAVE_Q))
    url = f"/api/v1/messages/{answer['id']}/feedback"

    assert (await api.post(url, {"rating": "helpful"})).status_code == 200
    assert (await api.get("/api/v1/dashboard/summary")).json()["questions"]["helpful_rate"] == 1.0

    await api.post(url, {"rating": "not_helpful", "comment": "  Too short  "})
    summary = (await api.get("/api/v1/dashboard/summary")).json()["questions"]
    assert summary["helpful_rate"] == 0.0 and summary["rated"] == 1
    thread = (await api.get(f"/api/v1/conversations/{cid}")).json()
    assert thread["messages"][1]["feedback"] == {"rating": "not_helpful", "comment": "Too short"}

    assert (await api.delete(url)).status_code == 200
    assert (await api.get("/api/v1/dashboard/summary")).json()["questions"]["rated"] == 0

    question_id = thread["messages"][0]["id"]  # only answers can be rated
    assert (
        await api.post(f"/api/v1/messages/{question_id}/feedback", {"rating": "helpful"})
    ).status_code == 404


async def test_trace_shows_signals_thresholds_and_usage(api: Api, kb: dict[str, Any]) -> None:
    cid = await new_conversation(api)
    answer = done_message(await ask_events(api, cid, LEAVE_Q))
    trace = (await api.get(f"/api/v1/messages/{answer['id']}/trace")).json()
    assert trace["question"] == LEAVE_Q
    assert trace["llm_model"] == "fake-llm" and trace["prompt_version"] == "answer-v1"
    assert trace["cost_usd"] is None  # no price configured for the fake model: never guessed
    assert trace["input_tokens"] > 0 and trace["latency_ms"] >= 0
    body = trace["trace"]
    assert body["thresholds"] == {"vec_hi": 0.30, "vec_lo": 0.15, "kw_coverage": 0.3}
    assert body["embedding_profile"] == "gemini-embedding-2-768"
    assert {"vec_max", "kw_coverage"} <= set(body["signals"])
    assert any(s["cited"] for s in body["sources"])

    usage = (await api.get("/api/v1/workspace/usage")).json()
    assert usage["tokens_used"] == trace["input_tokens"] + trace["output_tokens"]
    assert usage["token_limit"] == 2_000_000


async def test_monthly_token_limit_blocks_new_questions(
    api: Api, kb: dict[str, Any], owner_engine: Any
) -> None:
    cid = await new_conversation(api)
    await ask_events(api, cid, LEAVE_Q)
    with owner_engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.workspace_id', :w, true)"), {"w": kb["workspace"]["id"]}
        )
        conn.execute(text("UPDATE workspaces SET monthly_token_limit = 1"))
    response = await ask(api, cid, LEAVE_Q)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "usage_limit_reached"


async def test_chat_rate_limit(app: FastAPI, api: Api, kb: dict[str, Any]) -> None:
    app.state.settings = app.state.settings.model_copy(update={"chat_rate_per_minute": 2})
    cid = await new_conversation(api)
    for _ in range(2):
        assert (await ask(api, cid, LEAVE_Q)).status_code == 200
    third = await ask(api, cid, LEAVE_Q)
    assert third.status_code == 429 and third.json()["error"]["code"] == "rate_limited"


async def test_request_errors_happen_before_streaming(
    app: FastAPI, api: Api, kb: dict[str, Any], owner_engine: Any
) -> None:
    cid = await new_conversation(api)
    too_long = await ask(api, cid, "x" * 2001)
    assert too_long.status_code == 422 and too_long.json()["error"]["code"] == "question_too_long"
    blank = await ask(api, cid, "   ")
    assert blank.status_code == 422

    def unconfigured(*_args: Any) -> RagEngine:
        raise ProviderNotConfigured("gemini")

    app.state.engine_factory = unconfigured
    response = await ask(api, cid, LEAVE_Q)
    assert response.status_code == 503 and response.json()["error"]["code"] == "ai_not_configured"
    app.state.engine_factory = factory()

    with owner_engine.begin() as conn:  # an answer still being written blocks a second turn
        conn.execute(
            text("SELECT set_config('app.workspace_id', :w, true)"), {"w": kb["workspace"]["id"]}
        )
        conn.execute(
            text(
                "INSERT INTO messages (id, workspace_id, conversation_id, role, status) "
                "VALUES (:id, :w, :c, 'assistant', 'streaming')"
            ),
            {"id": str(uuid.uuid4()), "w": kb["workspace"]["id"], "c": cid},
        )
    busy = await ask(api, cid, LEAVE_Q)
    assert busy.status_code == 409


class FailingLLM:
    name = "gemini"
    model = "gemini-test"

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncIterator[LLMChunk]:
        yield LLMChunk(text="Partial answer ")
        raise ProviderError("gemini", "upstream closed", status=503, retryable=True)


async def test_provider_error_mid_answer_is_reported(
    app: FastAPI, api: Api, kb: dict[str, Any]
) -> None:
    app.state.engine_factory = factory(llm=FailingLLM())
    cid = await new_conversation(api)
    events = await ask_events(api, cid, LEAVE_Q)
    assert [n for n, _ in events][-2:] == ["error", "done"]
    assert dict(events)["error"]["code"] == "provider_error"
    message = done_message(events)
    assert message["status"] == "error" and message["content"] == "Partial answer"


class SlowLLM:
    """Streams one word every 50 ms, like a real provider, so a test can stop it midway."""

    name = "gemini"
    model = "gemini-3.5-flash-lite"

    def __init__(self) -> None:
        self.closed = False

    async def stream(
        self, system: str, messages: list[LLMMessage], params: GenerationParams
    ) -> AsyncIterator[LLMChunk]:
        try:
            for word in ["New ", "employees ", "receive ", "twenty ", "days ", "[1] ", "[9] "]:
                await asyncio.sleep(0.05)
                yield LLMChunk(text=word)
            yield LLMChunk(usage=LLMUsage(model=self.model, input_tokens=100, output_tokens=7))
        finally:
            self.closed = True


async def _service(app: FastAPI, settings: Settings, who: dict[str, Any], llm: Any) -> ChatService:
    db: AsyncSession = app.state.sessionmaker()
    wid, uid = uuid.UUID(who["workspace"]["id"]), uuid.UUID(who["user"]["id"])
    await set_tenant(db, workspace_id=wid, user_id=uid)
    workspace = await ws_repo.get_workspace(db, wid)
    assert workspace is not None
    return ChatService(
        db,
        settings,
        Actor(user_id=uid, workspace=workspace),
        http=app.state.http,
        limiter=app.state.limiter,
        engine_factory=factory(llm=llm),
    )


@pytest.mark.parametrize("how", ["close", "cancel"])
async def test_stop_saves_the_partial_answer(
    app: FastAPI, settings: Settings, api: Api, kb: dict[str, Any], how: str
) -> None:
    llm = SlowLLM()
    service = await _service(app, settings, kb, llm)
    cid = uuid.UUID(await new_conversation(api))
    turn = await service.prepare_ask(cid, LEAVE_Q)
    stream = service.stream(turn)

    if how == "close":  # the response closes the generator after a disconnect
        received = [await anext(stream) for _ in range(4)]  # meta + 3 tokens
        assert received[0].startswith(b"event: meta")
        await stream.aclose()
    else:  # Starlette cancels the task while the generator waits for the provider

        async def consume() -> None:
            async for _ in stream:
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.18)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    await service.db.close()

    assert llm.closed  # the provider stream was closed, not left running
    thread = (await api.get(f"/api/v1/conversations/{cid}")).json()
    answer = thread["messages"][1]
    assert answer["status"] == "stopped"
    assert answer["content"] and "[9]" not in answer["content"]
    trace = (await api.get(f"/api/v1/messages/{answer['id']}/trace")).json()
    assert trace["trace"]["stopped"] is True
    usage = (await api.get("/api/v1/workspace/usage")).json()
    assert usage["tokens_used"] > 0  # estimated, since the provider never reported usage

    # The conversation is free again.
    assert (await ask(api, str(cid), LEAVE_Q)).status_code == 200


async def test_chunk_context_and_purge(api: Api, kb: dict[str, Any], mailbox: Mailbox) -> None:
    cid = await new_conversation(api)
    answer = done_message(await ask_events(api, cid, LEAVE_Q))
    source = next(s for s in answer["sources"] if s["cited"])

    context = (await api.get(f"/api/v1/chunks/{source['chunk_id']}/context")).json()
    assert context["document"]["title"] == "Leave Policy"
    assert context["document"]["is_current"] is True
    chunk = context["chunk"]
    page = next(p for p in context["pages"] if p["page_number"] == chunk["page_start"])
    assert page["text"][chunk["char_start"] : chunk["char_start"] + 30] == chunk["text"][:30]

    purge = await api.post(f"/api/v1/documents/{source['document_id']}/purge")
    assert purge.status_code == 202
    await mailbox.drain()
    assert (await api.get(f"/api/v1/chunks/{source['chunk_id']}/context")).status_code == 404
    kept = (await api.get(f"/api/v1/conversations/{cid}")).json()["messages"][1]
    gone = next(s for s in kept["sources"] if s["number"] == source["number"])
    assert gone["available"] is False and gone["snippet"] == "" and gone["chunk_id"] is None
    assert gone["document_title"] == "Leave Policy"  # the citation label survives


async def test_suggested_questions_are_cached_until_documents_change(
    app: FastAPI, api: Api, mailbox: Mailbox
) -> None:
    await api.register()
    assert (await api.get("/api/v1/suggested-questions")).json() == {"questions": []}

    cheap = FakeLLM(
        responder=lambda _s, _m: json.dumps(
            {
                "questions": [
                    "How many days of leave do new hires get",
                    "x",
                    "How many days of leave do new hires get?",
                ]
            }
        )
    )
    app.state.cheap_llm_factory = lambda _settings, _http: cheap
    await ingest(api, mailbox, "Leave Policy.txt", LEAVE)
    first = (await api.get("/api/v1/suggested-questions")).json()
    assert first == {"questions": ["How many days of leave do new hires get?"]}
    await api.get("/api/v1/suggested-questions")
    assert len(cheap.calls) == 1  # cached

    await ingest(api, mailbox, "Shipping.txt", SHIPPING)
    await api.get("/api/v1/suggested-questions")
    assert len(cheap.calls) == 2  # the document set changed


async def test_conversations_list_rename_delete(api: Api, kb: dict[str, Any]) -> None:
    a = await new_conversation(api)
    await ask_events(api, a, LEAVE_Q)
    b = await new_conversation(api)
    await ask_events(api, b, "When does Express delivery to Germany arrive?")

    listing = (await api.get("/api/v1/conversations")).json()
    assert [c["id"] for c in listing] == [b, a]  # most recent first
    found = (await api.get("/api/v1/conversations?q=germany")).json()
    assert [c["id"] for c in found] == [b]
    assert (await api.get("/api/v1/conversations?q=%25")).json() == []  # LIKE wildcards escaped

    renamed = await api.patch(f"/api/v1/conversations/{a}", {"title": "  Leave  "})
    assert renamed.json()["title"] == "Leave"
    assert (await api.patch(f"/api/v1/conversations/{a}", {"title": "  "})).status_code == 422

    assert (await api.delete(f"/api/v1/conversations/{a}")).status_code == 200
    assert (await api.get(f"/api/v1/conversations/{a}")).status_code == 404
    assert [c["id"] for c in (await api.get("/api/v1/conversations")).json()] == [b]


async def test_chat_is_workspace_isolated(
    api: Api, api_b: Api, kb: dict[str, Any], mailbox: Mailbox
) -> None:
    cid = await new_conversation(api)
    answer = done_message(await ask_events(api, cid, LEAVE_Q))
    refused = done_message(await ask_events(api, cid, OFF_TOPIC))
    chunk_id = next(s for s in answer["sources"] if s["cited"])["chunk_id"]
    item = (await api.get("/api/v1/unanswered-questions")).json()["items"][0]["id"]
    assert refused["status"] == "refused"

    await api_b.register(email="bob@example.com", name="Bob Builder")
    await ingest(api_b, mailbox, "Leave Policy.txt", LEAVE)  # same text, other workspace
    checks = [
        await api_b.get(f"/api/v1/conversations/{cid}"),
        await api_b.patch(f"/api/v1/conversations/{cid}", {"title": "mine"}),
        await api_b.delete(f"/api/v1/conversations/{cid}"),
        await ask(api_b, cid, LEAVE_Q),
        await api_b.post(f"/api/v1/messages/{answer['id']}/regenerate"),
        await api_b.post(f"/api/v1/messages/{answer['id']}/feedback", {"rating": "helpful"}),
        await api_b.get(f"/api/v1/messages/{answer['id']}/trace"),
        await api_b.get(f"/api/v1/chunks/{chunk_id}/context"),
        await api_b.patch(f"/api/v1/unanswered-questions/{item}", {"status": "dismissed"}),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)

    assert (await api_b.get("/api/v1/conversations")).json() == []
    assert (await api_b.get("/api/v1/unanswered-questions")).json()["total"] == 0
    b_summary = (await api_b.get("/api/v1/dashboard/summary")).json()["questions"]
    assert b_summary["last_30d"] == 0
    assert (await api_b.get("/api/v1/workspace/usage")).json()["tokens_used"] == 0

    # B's own answer cites only B's document.
    b_cid = await new_conversation(api_b)
    b_answer = done_message(await ask_events(api_b, b_cid, LEAVE_Q))
    b_chunks = {s["chunk_id"] for s in b_answer["sources"]}
    a_chunks = {s["chunk_id"] for s in answer["sources"]}
    assert b_chunks and not (b_chunks & a_chunks)
