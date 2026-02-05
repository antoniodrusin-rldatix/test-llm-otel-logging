"""
LangGraph agent with OpenTelemetry tracing via opentelemetry-instrumentation-langchain.
Same workflow as workflow.py: agent -> tools. Spans are created automatically by the
instrumentor for graph and node execution.
Uses OTLP HTTP export; same env as root (OTEL_EXPORTER_OTLP_*). No-SSL via otel_export.
Set TRACELOOP_TRACE_CONTENT=false to avoid logging prompt/completion content on spans.
"""
import logging
import sys

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult

from langgraph.graph import END, START, StateGraph

from workflow import State, USER_QUERY, agent_node as raw_agent_node, tools_node as raw_tools_node
from otel_export import (
    create_otlp_exporter_no_ssl,
    get_otlp_endpoint,
    get_otlp_headers,
    wrap_exporter_with_logging,
)

from opentelemetry.instrumentation.langchain import LangchainInstrumentor


def _setup_tracing():
    """Configure TracerProvider with OTLP exporter (no-SSL) and logging wrapper."""
    resource = Resource.create({"service.name": "langgraph-agent-otel"})
    provider = TracerProvider(resource=resource)
    endpoint = get_otlp_endpoint()
    headers = get_otlp_headers()
    exporter = create_otlp_exporter_no_ssl(endpoint, headers or None)
    exporter = wrap_exporter_with_logging(exporter)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider, trace.get_tracer("langgraph.agent_otel", "1.0.0"), exporter


def _build_graph():
    """Build agent→tools StateGraph and return compiled graph."""
    builder = StateGraph(State)
    builder.add_node("agent", raw_agent_node)
    builder.add_node("tools", raw_tools_node)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", "tools")
    builder.add_edge("tools", END)
    return builder.compile()


def run_one(query: str | None = None):
    """Run one instrumented invocation. Call after _setup_tracing() and LangchainInstrumentor().instrument()."""
    print("[agent_otel] run_one starting")
    graph = _build_graph()
    initial: State = {"user_query": query or USER_QUERY}
    return graph.invoke(initial)


def main() -> None:
    try:
        create_otlp_exporter_no_ssl("http://dummy", None)
    except ImportError as e:
        print(
            "OTLP HTTP trace exporter not found. "
            "pip install opentelemetry-exporter-otlp-proto-http"
        )
        print(e)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")
    provider, _, exporter = _setup_tracing()
    LangchainInstrumentor().instrument()
    endpoint = get_otlp_endpoint()
    try:
        run_one()
        provider.force_flush(3000)
        provider.shutdown()
        if getattr(exporter, "last_result", None) == SpanExportResult.SUCCESS:
            print(f"LangChain/LangGraph spans exported to {endpoint}. Service: langgraph-agent-otel.")
        else:
            print(f"Export may have failed. Endpoint: {endpoint}. Check logs above for OTLP errors.")
            if getattr(exporter, "last_error", None) is not None:
                print(f"Last export error: {exporter.last_error}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
