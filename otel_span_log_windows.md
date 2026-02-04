# Usage instructions for otel_span_log.py on Windows host with port-forwarded OTEL collector

1. Port-forward the OTEL collector's gRPC port from your Kubernetes cluster:

    kubectl port-forward svc/otel-collector 4317:4317

2. Set the environment variable OTEL_COLLECTOR_ENDPOINT to 'localhost:4317' before running the script:

    set OTEL_COLLECTOR_ENDPOINT=localhost:4317
    python otel_span_log.py

3. Ensure your Windows firewall allows outbound connections on port 4317.

4. If you still see connection errors, verify the OTEL collector is running and listening on port 4317, and is configured for OTLP gRPC.

5. For troubleshooting, check the printed endpoint in the script output and any error messages.

