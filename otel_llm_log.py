"""
Emit synthetic GenAI spans (chat/inference + execute_tool) via OTLP HTTP.
No real LLM or API calls. Configurable endpoint and headers for:
  1. OTEL collector, 2. Maxim AI, 3. Confident AI.
See otel_llm_log.md for scenario env examples.
SSL verification is disabled for export (Zscaler-friendly).
"""
import gzip
import json
import os
import sys
import zlib
from io import BytesIO
from typing import Optional, Sequence

from requests.exceptions import ConnectionError

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExportResult,
    SpanExporter,
)
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.trace import SpanKind

from opentelemetry.semconv._incubating.attributes import gen_ai_attributes as GenAI
from opentelemetry.semconv.attributes.server_attributes import SERVER_ADDRESS

if getattr(GenAI, "GEN_AI_PROVIDER_NAME", None) is None:
    raise AttributeError(
        "GEN_AI_PROVIDER_NAME not found in gen_ai_attributes. "
        "Upgrade with: pip install 'opentelemetry-semantic-conventions>=0.59b0'"
    )

# Not in gen_ai_attributes in some semconv versions; use literals so we still get errors for other attrs
GEN_AI_TOOL_CALL_ARGUMENTS = "gen_ai.tool.call.arguments"
GEN_AI_TOOL_CALL_RESULT = "gen_ai.tool.call.result"
# Custom (not in GenAI semconv)
GEN_AI_COST = "gen_ai.cost"

# Default endpoint for local HTTP collector; override via OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
# or OTEL_EXPORTER_OTLP_ENDPOINT (latter gets /v1/traces appended by exporter)
DEFAULT_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"


def _get_endpoint() -> str:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if endpoint:
        return endpoint
    base = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
    if not base:
        return DEFAULT_TRACES_ENDPOINT
    return base if base.endswith("v1/traces") else f"{base}/v1/traces"


def _get_headers():
    """Parse OTEL_EXPORTER_OTLP_TRACES_HEADERS or OTEL_EXPORTER_OTLP_HEADERS (key=value,key2=value2)."""
    from opentelemetry.util.re import parse_env_headers

    s = os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""),
    )
    return parse_env_headers(s, liberal=True) if s else {}


def _create_otlp_exporter_no_ssl(endpoint: str, headers: Optional[dict]):
    """Create OTLP HTTP span exporter with SSL verification disabled (Zscaler-friendly)."""
    from opentelemetry.exporter.otlp.proto.http import Compression
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    class OTLPSpanExporterNoSSL(OTLPSpanExporter):
        """Subclass that overrides _export to pass verify=False."""

        def _export(
            self, serialized_data: bytes, timeout_sec: Optional[float] = None
        ):
            data = serialized_data
            if self._compression == Compression.Gzip:
                gzip_data = BytesIO()
                with gzip.GzipFile(fileobj=gzip_data, mode="w") as gzip_stream:
                    gzip_stream.write(serialized_data)
                data = gzip_data.getvalue()
            elif self._compression == Compression.Deflate:
                data = zlib.compress(serialized_data)

            if timeout_sec is None:
                timeout_sec = self._timeout

            try:
                resp = self._session.post(
                    url=self._endpoint,
                    data=data,
                    verify=False,
                    timeout=timeout_sec,
                    cert=self._client_cert,
                )
            except ConnectionError:
                resp = self._session.post(
                    url=self._endpoint,
                    data=data,
                    verify=False,
                    timeout=timeout_sec,
                    cert=self._client_cert,
                )
            return resp

    return OTLPSpanExporterNoSSL(endpoint=endpoint, headers=headers or None)


class TrackingSpanExporter(SpanExporter):
    """Wraps a SpanExporter and records last export result and any exception."""

    def __init__(self, delegate: SpanExporter):
        self._delegate = delegate
        self.last_result: Optional[SpanExportResult] = None
        self.last_error: Optional[Exception] = None

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.last_error = None
        try:
            self.last_result = self._delegate.export(spans)
            return self.last_result
        except Exception as e:
            self.last_error = e
            self.last_result = SpanExportResult.FAILURE
            raise

    def shutdown(self) -> None:
        self._delegate.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._delegate.force_flush(timeout_millis)


def main() -> None:
    resource = Resource.create({"service.name": "otel-llm-log"})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    try:
        _create_otlp_exporter_no_ssl("http://dummy", None)
    except ImportError as e:
        print(
            "Failed to import OTLP HTTP trace exporter. "
            "Install: pip install opentelemetry-exporter-otlp-proto-http"
        )
        print(e)
        sys.exit(1)

    endpoint = _get_endpoint()
    headers = _get_headers()
    exporter = _create_otlp_exporter_no_ssl(endpoint, headers or None)
    tracking = TrackingSpanExporter(exporter)
    provider.add_span_processor(BatchSpanProcessor(tracking))
    tracer = trace.get_tracer(__name__)

    # Synthetic values for the "chat" and "execute_tool" spans
    model = "gpt-4o"
    operation_name = "chat"
    span_name_chat = f"{operation_name} {model}"
    input_tokens = 42
    output_tokens = 18
    cost_usd = 0.0012
    response_id = "chatcmpl-synthetic-abc123"
    server_address = "api.openai.com"

    tool_name = "get_weather"
    tool_call_id = "call_synthetic_xyz"
    tool_args = {"location": "Paris"}
    tool_result = {"temp": 18, "unit": "celsius"}

    # Synthetic input/output messages (GenAI input/output message schema as JSON)
    input_messages = [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "What's the weather in Paris?"}],
        },
    ]
    output_messages = [
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "tool_call",
                    "id": tool_call_id,
                    "name": tool_name,
                    "arguments": tool_args,
                }
            ],
            "finish_reason": "tool_calls",
        },
    ]

    try:
        with tracer.start_as_current_span(
            span_name_chat,
            kind=SpanKind.CLIENT,
        ) as chat_span:
            # Required / recommended inference attributes
            chat_span.set_attribute(GenAI.GEN_AI_OPERATION_NAME, operation_name)
            chat_span.set_attribute(GenAI.GEN_AI_PROVIDER_NAME, "openai")
            chat_span.set_attribute(GenAI.GEN_AI_REQUEST_MODEL, model)
            chat_span.set_attribute(GenAI.GEN_AI_RESPONSE_MODEL, model)
            chat_span.set_attribute(GenAI.GEN_AI_USAGE_INPUT_TOKENS, input_tokens)
            chat_span.set_attribute(GenAI.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens)
            chat_span.set_attribute(GenAI.GEN_AI_RESPONSE_ID, response_id)
            chat_span.set_attribute(
                GenAI.GEN_AI_RESPONSE_FINISH_REASONS, ["stop"]
            )
            chat_span.set_attribute(SERVER_ADDRESS, server_address)
            # Input/output messages (JSON string per semconv when structured not supported on span)
            chat_span.set_attribute(
                GenAI.GEN_AI_INPUT_MESSAGES, json.dumps(input_messages)
            )
            chat_span.set_attribute(
                GenAI.GEN_AI_OUTPUT_MESSAGES, json.dumps(output_messages)
            )
            # Custom cost (not in semconv)
            chat_span.set_attribute(GEN_AI_COST, cost_usd)

            # Child: execute_tool span
            tool_span_name = f"execute_tool {tool_name}"
            with tracer.start_as_current_span(
                tool_span_name,
                kind=SpanKind.INTERNAL,
            ) as tool_span:
                tool_span.set_attribute(
                    GenAI.GEN_AI_OPERATION_NAME, "execute_tool"
                )
                tool_span.set_attribute(GenAI.GEN_AI_TOOL_NAME, tool_name)
                tool_span.set_attribute(
                    GenAI.GEN_AI_TOOL_DESCRIPTION,
                    "Get the current weather in a given location",
                )
                tool_span.set_attribute(GenAI.GEN_AI_TOOL_CALL_ID, tool_call_id)
                tool_span.set_attribute(GenAI.GEN_AI_TOOL_TYPE, "function")
                tool_span.set_attribute(
                    GEN_AI_TOOL_CALL_ARGUMENTS,
                    json.dumps(tool_args),
                )
                tool_span.set_attribute(
                    GEN_AI_TOOL_CALL_RESULT,
                    json.dumps(tool_result),
                )

        provider.shutdown()
        if tracking.last_result == SpanExportResult.SUCCESS:
            print(
                f"GenAI spans exported (chat + execute_tool) to {endpoint}. "
                "Service: otel-llm-log."
            )
        else:
            print(
                "Export failed (SSL or network error). Check logs above. "
                f"Endpoint: {endpoint}"
            )
            if tracking.last_error:
                print(f"Error: {tracking.last_error}")
            sys.exit(1)
    except Exception as e:
        print(f"Failed to create or export spans: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
