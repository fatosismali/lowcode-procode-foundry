"""Tests for the orchestrator HTTP session adapter."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from agent_framework import AgentResponseUpdate, Content

import orchestrator_http


@pytest.mark.asyncio
async def test_session_manager_reuses_workflow_and_closes_resources(monkeypatch):
    workflow = object()
    opened = []
    closed = []
    tasks = []

    @asynccontextmanager
    async def fake_open_team(team_yaml):
        opened.append(team_yaml)
        try:
            yield workflow, None
        finally:
            closed.append(team_yaml)

    async def fake_run_workflow(selected_workflow, task):
        assert selected_workflow is workflow
        tasks.append(task)
        return f"reply to {task}"

    monkeypatch.setattr(orchestrator_http, "open_team", fake_open_team)
    monkeypatch.setattr(orchestrator_http, "_run_workflow", fake_run_workflow)

    manager = orchestrator_http.SessionManager("team.yaml")
    first = await manager.chat("first")
    second = await manager.chat("second", first.session_id)

    assert first.reply == "reply to first"
    assert second.reply == "reply to second"
    assert second.session_id == first.session_id
    assert opened == [manager.team_yaml]
    assert tasks == ["first", "second"]

    await manager.close()
    assert closed == [manager.team_yaml]


@pytest.mark.asyncio
async def test_chat_endpoint_returns_reply_and_session(monkeypatch):
    async def fake_chat(self, message, session_id=None):
        assert message == "check my latest bill"
        assert session_id == "existing-session"
        return orchestrator_http.ChatResponse(reply="Your bill is ready.", session_id=session_id)

    monkeypatch.setattr(orchestrator_http.SessionManager, "chat", fake_chat)
    app = orchestrator_http.create_app("team.yaml")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/chat",
            json={"message": "check my latest bill", "session_id": "existing-session"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Your bill is ready.",
        "session_id": "existing-session",
    }


@pytest.mark.asyncio
async def test_session_manager_streams_each_agent_response(monkeypatch):
    class FakeStream:
        def __init__(self):
            self.events = iter(
                [
                    SimpleNamespace(
                        type="executor_invoked", executor_id="profile", data=None
                    ),
                    SimpleNamespace(
                        type="intermediate",
                        executor_id="profile",
                        data=AgentResponseUpdate(
                            contents=[Content(type="text", text="profile")]
                        ),
                    ),
                    SimpleNamespace(
                        type="intermediate",
                        executor_id="profile",
                        data=AgentResponseUpdate(
                            contents=[Content(type="text", text=" ")]
                        ),
                    ),
                    SimpleNamespace(
                        type="intermediate",
                        executor_id="profile",
                        data=AgentResponseUpdate(
                            contents=[
                                Content(
                                    type="function_call",
                                    name="get_billing_profiles",
                                    call_id="call-1",
                                    arguments={},
                                )
                            ]
                        ),
                    ),
                    SimpleNamespace(
                        type="intermediate",
                        executor_id="profile",
                        data=AgentResponseUpdate(
                            contents=[Content(type="text", text="output")]
                        ),
                    ),
                    SimpleNamespace(
                        type="executor_completed", executor_id="profile", data=None
                    ),
                    SimpleNamespace(
                        type="output", executor_id="response", data="final output"
                    ),
                ]
            )

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.events)
            except StopIteration:
                raise StopAsyncIteration

    class FakeWorkflow:
        def run(self, message, *, stream=False):
            assert message == "show progress"
            assert stream is True
            return FakeStream()

    @asynccontextmanager
    async def fake_open_team(team_yaml):
        yield FakeWorkflow(), None

    monkeypatch.setattr(orchestrator_http, "open_team", fake_open_team)
    manager = orchestrator_http.SessionManager("team.yaml")

    events = [event async for event in manager.stream("show progress")]

    assert [event["type"] for event in events] == [
        "session",
        "status",
        "agent_response",
        "agent_response",
        "activity",
        "agent_response",
        "status",
        "agent_response",
        "done",
    ]
    assert events[2]["text"] == "profile"
    assert events[2]["mode"] == "append"
    assert events[3]["text"] == " "
    assert events[4]["tool"] == "get_billing_profiles"
    assert events[5]["text"] == "output"
    assert events[7]["text"] == "final output"
    assert events[7]["mode"] == "replace"
    assert len({event["session_id"] for event in events}) == 1

    await manager.close()


@pytest.mark.asyncio
async def test_stream_endpoint_frames_typed_sse_events(monkeypatch):
    async def fake_stream(self, message, session_id=None):
        assert message == "stream this"
        yield {"type": "session", "session_id": "session-2"}
        yield {
            "type": "agent_response",
            "agent": "profile",
            "text": "profile output",
            "final": False,
            "session_id": "session-2",
        }
        yield {"type": "done", "session_id": "session-2"}

    monkeypatch.setattr(orchestrator_http.SessionManager, "stream", fake_stream)
    app = orchestrator_http.create_app("team.yaml")
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/chat/stream", json={"message": "stream this"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: session\n" in response.text
    assert "event: agent_response\n" in response.text
    assert '"text": "profile output"' in response.text
    assert response.text.endswith('data: {"type": "done", "session_id": "session-2"}\n\n')


def test_flask_ui_renders_and_proxies_chat(monkeypatch):
    from ui import app as ui_app

    upstream = SimpleNamespace(
        status_code=200,
        json=lambda: {"reply": "Billing response", "session_id": "session-1"},
    )

    def fake_post(endpoint, json, timeout):
        assert endpoint == "http://127.0.0.1:8000/chat"
        assert json == {"message": "hello"}
        assert timeout == ui_app.REQUEST_TIMEOUT
        return upstream

    monkeypatch.setattr(ui_app.requests, "post", fake_post)
    client = ui_app.app.test_client()

    page = client.get("/")
    response = client.post(
        "/api/chat",
        json={"message": "hello", "endpoint": "http://127.0.0.1:8000/chat"},
    )

    assert page.status_code == 200
    assert b"Billing Assistant" in page.data
    assert response.status_code == 200
    assert response.get_json() == {
        "reply": "Billing response",
        "session_id": "session-1",
    }


def test_flask_ui_forwards_stream_without_buffering(monkeypatch):
    from ui import app as ui_app

    closed = []

    class Upstream:
        status_code = 200

        def iter_lines(self, chunk_size):
            assert chunk_size == 1
            yield b"event: agent_response"
            yield b'data: {"type":"agent_response","text":"working"}'
            yield b""

        def close(self):
            closed.append(True)

    def fake_post(endpoint, json, timeout, stream):
        assert endpoint == "http://127.0.0.1:8000/chat/stream"
        assert json == {"message": "hello", "session_id": "session-1"}
        assert timeout == ui_app.REQUEST_TIMEOUT
        assert stream is True
        return Upstream()

    monkeypatch.setattr(ui_app.requests, "post", fake_post)
    client = ui_app.app.test_client()
    response = client.post(
        "/api/chat/stream",
        json={
            "message": "hello",
            "endpoint": "http://127.0.0.1:8000/chat",
            "session_id": "session-1",
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "text/event-stream"
    assert response.data == (
        b"event: agent_response\n"
        b'data: {"type":"agent_response","text":"working"}\n\n'
    )
    assert closed == [True]