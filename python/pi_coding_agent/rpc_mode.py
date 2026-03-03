"""RPC mode — JSON stdin/stdout headless protocol."""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any

from pi_ai.types import AssistantMessage, TextContent
from pi_agent.types import AgentEvent

from pi_session.agent_session import AgentSession, SessionEvent


# --- RPC command handlers ---


async def _handle_prompt(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}
    await session.prompt(text)
    return {"ok": True}


async def _handle_steer(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}
    await session.steer(text)
    return {"ok": True}


async def _handle_follow_up(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    text = params.get("text", "")
    if not text:
        return {"error": "Missing 'text' parameter"}
    await session.follow_up(text)
    return {"ok": True}


async def _handle_abort(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    session.abort()
    return {"ok": True}


async def _handle_get_state(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    agent = session.agent
    return {
        "is_streaming": agent.is_streaming,
        "error": agent.error,
        "message_count": len(agent.messages),
        "model": agent.model.id if agent.model else None,
        "provider": agent.model.provider if agent.model else None,
    }


async def _handle_set_model(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    from pi_ai.models import get_model
    provider = params.get("provider", "")
    model_id = params.get("model_id", "")
    thinking_level = params.get("thinking_level")
    try:
        model = get_model(provider, model_id)
        session.set_model(model, thinking_level)
        return {"ok": True, "model": model.id}
    except ValueError as e:
        return {"error": str(e)}


async def _handle_set_thinking_level(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    level = params.get("level")
    session.agent.set_thinking_level(level)
    return {"ok": True}


async def _handle_compact(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    instructions = params.get("instructions")
    await session.manual_compact(instructions)
    return {"ok": True}


async def _handle_get_session_stats(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    stats = session.get_stats()
    return {
        "total_messages": stats.total_messages,
        "total_turns": stats.total_turns,
        "total_tokens": stats.total_tokens,
        "total_cost": stats.total_cost,
        "compactions": stats.compactions,
    }


async def _handle_get_available_models(session: AgentSession, params: dict[str, Any]) -> dict[str, Any]:
    from pi_ai.models import MODELS
    models_list = []
    for provider_models in MODELS.values():
        for model in provider_models.values():
            models_list.append({
                "id": model.id,
                "name": model.name,
                "provider": model.provider,
                "reasoning": model.reasoning,
                "context_window": model.context_window,
            })
    return {"models": models_list}


COMMAND_HANDLERS: dict[str, Any] = {
    "prompt": _handle_prompt,
    "steer": _handle_steer,
    "follow_up": _handle_follow_up,
    "abort": _handle_abort,
    "get_state": _handle_get_state,
    "set_model": _handle_set_model,
    "set_thinking_level": _handle_set_thinking_level,
    "compact": _handle_compact,
    "get_session_stats": _handle_get_session_stats,
    "get_available_models": _handle_get_available_models,
}


# --- Event emission ---


def _emit_rpc_event(event: SessionEvent) -> None:
    """Emit an event as JSON to stdout."""
    try:
        d = asdict(event)
        d["_event_type"] = type(event).__name__
        sys.stdout.write(json.dumps(d, default=str) + "\n")
        sys.stdout.flush()
    except (TypeError, ValueError):
        d = {"_event_type": type(event).__name__, "type": getattr(event, "type", "")}
        sys.stdout.write(json.dumps(d) + "\n")
        sys.stdout.flush()


def _emit_rpc_response(request_id: str | None, result: dict[str, Any]) -> None:
    """Emit a command response as JSON to stdout."""
    response = {"jsonrpc": "2.0", "result": result}
    if request_id:
        response["id"] = request_id
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _emit_rpc_error(request_id: str | None, message: str) -> None:
    """Emit an error response."""
    response = {"jsonrpc": "2.0", "error": {"message": message}}
    if request_id:
        response["id"] = request_id
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


# --- Main RPC loop ---


async def run_rpc_mode(session: AgentSession) -> None:
    """Run the agent in RPC mode, reading JSON commands from stdin."""
    # Subscribe to forward events
    session.subscribe(_emit_rpc_event)

    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader),
        sys.stdin,
    )

    try:
        while True:
            line = await reader.readline()
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                request = json.loads(line_str)
            except json.JSONDecodeError:
                _emit_rpc_error(None, "Invalid JSON")
                continue

            command = request.get("method", "")
            params = request.get("params", {})
            request_id = request.get("id")

            handler = COMMAND_HANDLERS.get(command)
            if handler is None:
                _emit_rpc_error(request_id, f"Unknown command: {command}")
                continue

            try:
                result = await handler(session, params)
                _emit_rpc_response(request_id, result)
            except Exception as e:
                _emit_rpc_error(request_id, str(e))
    finally:
        transport.close()
