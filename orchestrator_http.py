"""HTTP API for the YAML-driven team orchestrator."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator
from uuid import uuid4

import uvicorn
from agent_framework import AgentResponseUpdate
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from orchestrator import _format_workflow_output, _run_workflow, open_team

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    session_id: str


@dataclass
class TeamSession:
    stack: AsyncExitStack
    workflow: object
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class SessionManager:
    """Own persistent workflows and their async tool resources."""

    def __init__(self, team_yaml: str | Path) -> None:
        self.team_yaml = Path(team_yaml)
        self._sessions: dict[str, TeamSession] = {}
        self._lock = asyncio.Lock()

    async def chat(self, message: str, session_id: str | None = None) -> ChatResponse:
        session_id, session = await self._get_or_create(session_id)
        async with session.lock:
            reply = await _run_workflow(session.workflow, message)
        return ChatResponse(reply=reply, session_id=session_id)

    async def stream(
        self, message: str, session_id: str | None = None
    ) -> AsyncIterator[dict[str, object]]:
        session_id, session = await self._get_or_create(session_id)
        yield {"type": "session", "session_id": session_id}

        async with session.lock:
            response_stream = session.workflow.run(message, stream=True)
            async for event in response_stream:
                if event.type in {"executor_invoked", "executor_completed"}:
                    yield {
                        "type": "status",
                        "agent": event.executor_id,
                        "status": (
                            "started" if event.type == "executor_invoked" else "completed"
                        ),
                        "session_id": session_id,
                    }
                elif event.type in {"intermediate", "output"}:
                    is_delta = isinstance(event.data, AgentResponseUpdate)
                    if is_delta:
                        for content in event.data.contents:
                            content_type = str(getattr(content, "type", ""))
                            if content_type.endswith("_call"):
                                tool = (
                                    getattr(content, "name", None)
                                    or getattr(content, "tool_name", None)
                                    or content_type.removesuffix("_call").replace("_", " ")
                                )
                                yield {
                                    "type": "activity",
                                    "agent": event.executor_id,
                                    "status": "calling",
                                    "tool": tool,
                                    "session_id": session_id,
                                }
                            elif content_type.endswith("_result"):
                                tool = (
                                    getattr(content, "name", None)
                                    or getattr(content, "tool_name", None)
                                    or content_type.removesuffix("_result").replace("_", " ")
                                )
                                yield {
                                    "type": "activity",
                                    "agent": event.executor_id,
                                    "status": "completed",
                                    "tool": tool,
                                    "session_id": session_id,
                                }

                    text = (
                        event.data.text
                        if is_delta
                        else _format_workflow_output(event.data)
                    )
                    if text if is_delta else text.strip():
                        yield {
                            "type": "agent_response",
                            "agent": event.executor_id,
                            "text": text,
                            "mode": "append" if is_delta else "replace",
                            "session_id": session_id,
                        }

        yield {"type": "done", "session_id": session_id}

    async def _get_or_create(self, session_id: str | None) -> tuple[str, TeamSession]:
        selected_id = session_id or str(uuid4())
        async with self._lock:
            session = self._sessions.get(selected_id)
            if session is not None:
                return selected_id, session

            stack = AsyncExitStack()
            try:
                workflow, _ = await stack.enter_async_context(open_team(self.team_yaml))
            except BaseException:
                await stack.aclose()
                raise
            session = TeamSession(stack=stack, workflow=workflow)
            self._sessions[selected_id] = session
            return selected_id, session

    async def close(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            await session.stack.aclose()


def create_app(team_yaml: str | Path) -> FastAPI:
    manager = SessionManager(team_yaml)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await manager.close()

    app = FastAPI(title="Foundry Team Orchestrator", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    async def run_chat(payload: ChatRequest) -> ChatResponse:
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message must not be empty.")
        try:
            return await manager.chat(message, payload.session_id)
        except Exception as exc:
            logger.exception("Orchestrator request failed")
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest) -> ChatResponse:
        return await run_chat(payload)

    @app.post("/chat/stream")
    async def chat_stream(payload: ChatRequest) -> StreamingResponse:
        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message must not be empty.")

        async def events() -> AsyncIterator[str]:
            try:
                async for event in manager.stream(message, payload.session_id):
                    event_type = str(event["type"])
                    yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
            except Exception as exc:
                logger.exception("Streaming orchestrator request failed")
                error = {"type": "error", "message": str(exc)}
                yield f"event: error\ndata: {json.dumps(error)}\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve a YAML team over HTTP.")
    parser.add_argument(
        "--team-yaml",
        type=Path,
        default=Path(os.getenv("TEAM_YAML", "agent_teams/vf_billing_team/team.yaml")),
    )
    parser.add_argument("--host", default=os.getenv("ORCHESTRATOR_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    )
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "info"))
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    uvicorn.run(
        create_app(args.team_yaml),
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
    )


if __name__ == "__main__":
    main()