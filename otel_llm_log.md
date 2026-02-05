# otel_llm_log.py – GenAI spans to OTLP

The script emits **synthetic** GenAI spans (no real LLM or API calls):

- One **chat** (inference) span: model, tokens, cost, response id, etc.
- One **execute_tool** child span: tool name, arguments, result.

Export is over **OTLP HTTP**, with configurable endpoint and headers so the same script works for an OTEL collector, Maxim AI, or Confident AI.

**SSL:** TLS certificate verification is disabled for the export HTTP client (Zscaler-friendly). The message "GenAI spans exported..." is only printed when export actually succeeds; on failure you get "Export failed (SSL or network error). Check logs above." and exit code 1.

## Run

```bash
# Optional: activate venv first
pip install -r requirements.txt
python otel_llm_log.py
```

Configuration is via environment variables (see scenarios below).

## 1. OTEL collector

Send traces to a local or remote OpenTelemetry collector (HTTP OTLP receiver).

**Endpoint:** `http://localhost:4318/v1/traces` (default if no env is set), or your collector URL including `/v1/traces`.

**Example:**

```bash
# Default: http://localhost:4318/v1/traces, no headers
python otel_llm_log.py
```

**Override endpoint only:**

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
python otel_llm_log.py
```

Or use the base URL (script appends `/v1/traces`):

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
python otel_llm_log.py
```

No auth headers required for a typical local collector.

---

## 2. Maxim AI

Send traces to [Maxim](https://www.getmaxim.ai/docs/tracing/opentelemetry/ingesting-via-otlp) OTLP endpoint.

**Endpoint:** `https://api.getmaxim.ai/v1/otel`  
**Headers:** `x-maxim-repo-id`, `x-maxim-api-key`

**Example:**

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://api.getmaxim.ai/v1/otel
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="x-maxim-repo-id=YOUR_REPO_ID,x-maxim-api-key=YOUR_API_KEY"
python otel_llm_log.py
```

Replace `YOUR_REPO_ID` and `YOUR_API_KEY` with your Maxim Log Repository ID and API key.

---

## 3. Confident AI

Send traces to [Confident AI](https://www.confident-ai.com/docs/integrations/opentelemetry) OTLP endpoint.

**Endpoint:** `https://otel.confident-ai.com/v1/traces`  
**Header:** `x-confident-api-key`

**Example:**

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://otel.confident-ai.com/v1/traces
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="x-confident-api-key=YOUR_CONFIDENT_API_KEY"
python otel_llm_log.py
```

Replace `YOUR_CONFIDENT_API_KEY` with your Confident API key.

---

## Env reference

| Variable | Description |
|----------|-------------|
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Full URL for traces (e.g. `https://api.getmaxim.ai/v1/otel` or `http://localhost:4318/v1/traces`). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base OTLP URL; script appends `/v1/traces` if this is set and traces endpoint is not. |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | Comma-separated headers: `key1=value1,key2=value2`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Fallback for headers if traces-specific one is not set. |

The script uses standard OTEL env vars so it works with any OTLP HTTP backend that supports GenAI semantic conventions.
