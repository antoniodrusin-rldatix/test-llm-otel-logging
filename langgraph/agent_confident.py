"""
LangGraph agent with Confident AI tracing via deepeval @observe.
Same workflow as workflow.py: agent -> tools. One trace per run with two spans (chat + execute_tool).
Env: CONFIDENT_API_KEY; optional CONFIDENT_TRACE_FLUSH=YES for short-lived scripts.
"""
import os
import sys
from typing import Any

from deepeval.tracing import observe
from langgraph.graph import END, START, StateGraph

from workflow import (
    DEFAULT_MODEL,
    TOOL_ARGS,
    TOOL_CALL_ID,
    TOOL_NAME,
    TOOL_RESULT,
    USER_QUERY,
    State,
    _call_local_llm_if_configured,
    agent_node as raw_agent_node,
    tools_node as raw_tools_node,
)


def _setup_tracing():
    """Check Confident API key is set for tracing."""
    if not os.environ.get("CONFIDENT_API_KEY", "").strip():
        raise ValueError("Set CONFIDENT_API_KEY for Confident AI tracing.")




@observe()
def agent_node(state: State) -> dict[str, Any]:
    """
    Agent (chat) node: takes user query, returns synthetic assistant message with one tool call,
    or calls local LLM if OPENAI_BASE_URL is set.
    """
    print("[agent_confident] agent_node entered")
    query = state.get("user_query") or USER_QUERY
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


@observe()
def tools_node(state: State) -> dict[str, Any]:
    """
    Tools node: executes get_weather with arguments from agent_output; returns tool result.
    """
    print("[agent_confident] tools_node entered")
    agent_out = state.get("agent_output") or {}
    tool_calls = agent_out.get("tool_calls") or [{"name": TOOL_NAME, "arguments": TOOL_ARGS}]
    # Use first tool call; for get_weather return fixed result
    args = TOOL_ARGS
    for tc in tool_calls:
        if tc.get("name") == TOOL_NAME:
            args = tc.get("arguments") or TOOL_ARGS
            break
    # Synthetic result (could vary by args in a real impl)
    result = {**TOOL_RESULT, "location": args.get("location", "Paris")}
    return {"tool_result": result}


def _build_graph():
    """Build agent→tools StateGraph and return compiled graph."""
    builder = StateGraph(State)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tools_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    return builder.compile()


def run_one(query: str | None = None):
    """Run one invocation. Each node is @observe-decorated; set CONFIDENT_TRACE_FLUSH=YES to flush before exit."""
    graph = _build_graph()
    initial: State = {"user_query": query or USER_QUERY}
    return graph.invoke(initial)


def main() -> None:
    try:
        _setup_tracing()
        run_one()
        print("Confident AI trace (agent + tools spans) sent. Check the Observatory.")
    except ValueError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
