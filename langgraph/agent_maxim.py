"""
LangGraph agent with Maxim AI SDK tracing.
Same workflow as workflow.py: agent -> tools. Uses MaximLangchainTracer in config (no decorator).
Env: MAXIM_API_KEY, MAXIM_LOG_REPO_ID.
"""
import os
import sys

from langgraph.graph import END, START, StateGraph

from workflow import USER_QUERY, State, agent_node, tools_node


def _setup_tracing():
    """Setup Maxim logger for LangChain tracing."""
    from maxim import Maxim

    api_key = os.environ.get("MAXIM_API_KEY", "").strip()
    repo_id = os.environ.get("MAXIM_LOG_REPO_ID", "").strip()
    if not api_key or not repo_id:
        raise ValueError("Set MAXIM_API_KEY and MAXIM_LOG_REPO_ID")
    maxim = Maxim({"api_key": api_key})
    return maxim.logger({"id": repo_id})


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
    """Run one invocation via compiled graph with MaximLangchainTracer in config. Returns final state."""
    print("[agent_maxim] run_one starting")
    logger = _setup_tracing()
    from maxim.logger.langchain import MaximLangchainTracer

    maxim_langchain_tracer = MaximLangchainTracer(logger)
    graph = _build_graph()
    initial: State = {"user_query": query or USER_QUERY}
    config = {"recursion_limit": 50, "callbacks": [maxim_langchain_tracer]}
    result = graph.invoke(initial, config=config)
    logger.flush()
    return result


def main() -> None:
    try:
        run_one()
        print("Maxim trace sent (callback-based). Check your Maxim Log Repository.")
    except ValueError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
