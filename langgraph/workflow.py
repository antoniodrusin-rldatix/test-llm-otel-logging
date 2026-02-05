"""
Shared LangGraph workflow: agent node (chat) + tools node (execute_tool).
No tracing/observability imports. Matches otel_llm_log.py: synthetic chat + get_weather.
Optional local LLM via OPENAI_BASE_URL / OPENAI_API_KEY.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional, TypedDict

# Synthetic constants matching otel_llm_log.py
DEFAULT_MODEL = "gpt-4o"
TOOL_NAME = "get_weather"
TOOL_CALL_ID = "call_synthetic_xyz"
TOOL_ARGS = {"location": "Paris"}
TOOL_RESULT = {"temp": 18, "unit": "celsius"}
USER_QUERY = "What's the weather in Paris?"


class State(TypedDict, total=False):
    """State passed through the graph."""
    user_query: str
    agent_output: dict  # synthetic assistant message with tool_calls
    tool_result: dict
    messages: list  # optional: accumulated messages for LLM-style flow


def _call_local_llm_if_configured(query: str) -> Optional[dict[str, Any]]:
    """
    If OPENAI_BASE_URL (and optionally OPENAI_API_KEY) are set, call local LLM.
    Returns None if not configured; then caller uses synthetic response.
    """
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    if not base_url:
        print("[workflow] Local LLM not configured (OPENAI_BASE_URL unset), using synthetic response")
        return None
    query_snippet = (query[:80] + "...") if len(query) > 80 else query
    print(f"[workflow] Calling local LLM (OPENAI_BASE_URL={base_url}) for query: {query_snippet}")
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY", "lm-studio"))
        model = os.environ.get("OPENAI_MODEL", "local")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": query}],
        )
        content = resp.choices[0].message.content or ""
        tool_calls = getattr(resp.choices[0].message, "tool_calls", None) or []
        content_preview = (content[:200] + "...") if len(content) > 200 else content
        print(f"[workflow] Local LLM response: model={resp.model or model}, content_length={len(content)}, tool_calls={len(tool_calls)}, content_preview={content_preview!r}")
        # If model didn't return tool calls, we still emit synthetic tool call for workflow parity
        return {
            "content": content,
            "tool_calls": [
                {"id": TOOL_CALL_ID, "name": TOOL_NAME, "arguments": TOOL_ARGS}
            ] if not tool_calls else [{"id": tc.id, "name": getattr(tc.function, "name", TOOL_NAME), "arguments": json.loads(getattr(tc.function, "arguments", "{}") or "{}")} for tc in tool_calls],
            "model": resp.model or DEFAULT_MODEL,
        }
    except Exception as e:
        print(f"[workflow] Local LLM call failed: {e}")
        return None


def agent_node(state: State) -> dict[str, Any]:
    """
    Agent (chat) node: takes user query, returns synthetic assistant message with one tool call,
    or calls local LLM if OPENAI_BASE_URL is set.
    """
    query = state.get("user_query") or USER_QUERY
    query_snippet = (query[:80] + "...") if len(query) > 80 else query
    print(f"[workflow] agent_node called, user_query={query_snippet!r}")
    out = _call_local_llm_if_configured(query)
    if out is None:
        # Synthetic response matching otel_llm_log.py
        return {
            "agent_output": {
                "content": "",
                "tool_calls": [{"id": TOOL_CALL_ID, "name": TOOL_NAME, "arguments": TOOL_ARGS}],
                "model": DEFAULT_MODEL,
            }
        }
    return {"agent_output": out}


def tools_node(state: State) -> dict[str, Any]:
    """
    Tools node: executes get_weather with arguments from agent_output; returns tool result.
    """
    agent_out = state.get("agent_output") or {}
    tool_calls = agent_out.get("tool_calls") or [{"name": TOOL_NAME, "arguments": TOOL_ARGS}]
    # Use first tool call; for get_weather return fixed result
    args = TOOL_ARGS
    tool_name = TOOL_NAME
    for tc in tool_calls:
        if tc.get("name") == TOOL_NAME:
            args = tc.get("arguments") or TOOL_ARGS
            tool_name = tc.get("name", TOOL_NAME)
            break
    print(f"[workflow] tools_node called, tool={tool_name}, arguments={args}")
    # Synthetic result (could vary by args in a real impl)
    result = {**TOOL_RESULT, "location": args.get("location", "Paris")}
    return {"tool_result": result}


def build_graph():
    """Build and return the compiled StateGraph (agent -> tools -> END)."""
    from langgraph.graph import END, START, StateGraph

    builder = StateGraph(State)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    return builder.compile()


def run_one(query: str | None = None) -> dict[str, Any]:
    """Run one invocation of the workflow. Returns final state."""
    graph = build_graph()
    initial: State = {"user_query": query or USER_QUERY}
    return graph.invoke(initial)
