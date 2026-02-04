import sys
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Set up OTEL tracer provider with service name 'pytontest'
resource = Resource.create({"service.name": "pytontest"})
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Configure OTLP gRPC exporter to send spans to otel-collector:4317
try:
    exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
    span_processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
except Exception as e:
    print(f"Failed to set up OTEL gRPC exporter: {e}")
    sys.exit(1)

# Create and log a span
try:
    with tracer.start_as_current_span("example-span") as span:
        span.set_attribute("example.key", "example-value")
        print("Span created and ended.")
    # Force flush to ensure the span is exported
    provider.shutdown()
    print("Span exported to OTEL collector at otel-collector:4317 (gRPC). Service name: pytontest.")
except Exception as e:
    print(f"Failed to log span: {e}\nCheck if the OTEL collector is running at otel-collector:4317 and is configured for OTLP gRPC.")
