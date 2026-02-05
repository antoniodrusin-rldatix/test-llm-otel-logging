# LangGraph Agent (OTel, Maxim, Confident AI)

This folder contains a **LangGraph agent** with the same logical workflow as the root [`otel_llm_log.py`](../otel_llm_log.md): one **chat** (inference) step and one **execute_tool** step (`get_weather`). No real LLM is required; you can optionally use a local LLM (LM Studio, Ollama) via an OpenAI-compatible API.

## Layout

| File | Purpose |
|------|--------|
| `workflow.py` | Shared graph: `agent` → `tools`. Backend-agnostic; no tracing. |
| `agent_otel.py` | Same workflow + **OpenTelemetry** (opentelemetry-instrumentation-langchain, OTLP HTTP). |
| `agent_maxim.py` | Same workflow + **Maxim AI SDK** (trace + spans). |
| `agent_confident.py` | Same workflow + **Confident AI** (deepeval `@observe`). |
| `otel_export.py` | OTLP HTTP exporter helper (no-SSL) for `agent_otel.py`. |

## Setup

Requires **Python 3.10+** (LangGraph requirement).

```bash
cd langgraph
pip install -r requirements.txt
```

## Backend: OTEL (`agent_otel.py`)

Run: `python agent_otel.py`. The OTel agent exports over **OTLP HTTP** with configurable endpoint and headers, so the same script can send traces to a local collector, **Maxim AI**, or **Confident AI**.

| Variable | Description |
|----------|-------------|
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | Full URL for traces (e.g. collector, Maxim, or Confident URL below). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Base OTLP URL; `/v1/traces` is appended if this is set and traces endpoint is not. |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | Comma-separated headers: `key1=value1,key2=value2`. |
| `OTEL_EXPORTER_OTLP_HEADERS` | Fallback for headers if traces-specific one is not set. |
| `TRACELOOP_TRACE_CONTENT` | Set to `false` to avoid logging prompt/completion content on spans (opentelemetry-instrumentation-langchain). |

**1. OTEL collector (default)**  
Endpoint: `http://localhost:4318/v1/traces` (default if unset). No headers needed.

```bash
# Default
python agent_otel.py
# Or override:
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4318/v1/traces
python agent_otel.py
```

**2. Maxim AI (OTLP)**  
Endpoint: `https://api.getmaxim.ai/v1/otel`  
Headers: `x-maxim-repo-id`, `x-maxim-api-key`

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://api.getmaxim.ai/v1/otel
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="x-maxim-repo-id=YOUR_REPO_ID,x-maxim-api-key=YOUR_API_KEY"
python agent_otel.py
```

**3. Confident AI (OTLP)**  
Endpoint: `https://otel.confident-ai.com/v1/traces`  
Header: `x-confident-api-key`

```bash
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=https://otel.confident-ai.com/v1/traces
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="x-confident-api-key=YOUR_CONFIDENT_API_KEY"
python agent_otel.py
```

## Backend: Maxim (`agent_maxim.py`)

**Env:** `MAXIM_API_KEY`, `MAXIM_LOG_REPO_ID` (required).

**Run:**

```bash
export MAXIM_API_KEY=your_key
export MAXIM_LOG_REPO_ID=your_repo_id
python agent_maxim.py
```

Traces are sent via MaximLangchainTracer; check your Maxim Log Repository.

## Backend: Confident (`agent_confident.py`)

**Env:** `CONFIDENT_API_KEY` (required); optional `CONFIDENT_TRACE_FLUSH=YES` for short-lived scripts.

**Run:**

```bash
export CONFIDENT_API_KEY=your_key
# optional: export CONFIDENT_TRACE_FLUSH=YES
python agent_confident.py
```

Traces (agent + tools spans) are sent to Confident AI; check the Observatory.

## Local LLM (optional)

Applies to any of the three agents (`agent_otel.py`, `agent_maxim.py`, `agent_confident.py`). No real LLM is required; the agent uses a **synthetic** response (same as `otel_llm_log.py`). If you want to use a local model, run an OpenAI-compatible server and set the env vars below.

| Variable | Description |
|----------|-------------|
| `OPENAI_BASE_URL` | Base URL of the API (no trailing path beyond `/v1`). |
| `OPENAI_API_KEY` | Optional; many local servers accept any key (e.g. `ollama` or `lm-studio`). |
| `OPENAI_MODEL` | Model name (default `local`). Must match the model name on your server. |

Then run any of the agents; the agent node will call the local API and use the real response (tool-call structure is still normalized for the workflow).

### Using Ollama

1. Install and start [Ollama](https://ollama.com), then pull a model:

   ```bash
   ollama pull llama3.2
   ```

2. Set the base URL to Ollama’s OpenAI-compatible endpoint and the model name:

   ```bash
   export OPENAI_BASE_URL=http://localhost:11434/v1
   export OPENAI_MODEL=gemma3:4b
   #  key not required for local Ollama; use any placeholder if your client requires it:
   export OPENAI_API_KEY=ollama
   ```

   On Linux/macOS use `export` instead of `set`.

3. Run an agent, e.g.:

   ```bash
   python agent_otel.py
   ```

## Workflow summary

- **Agent node:** Accepts a user query (e.g. “What’s the weather in Paris?”), returns a synthetic assistant message with one tool call `get_weather(location="Paris")` (or the local LLM response if configured).
- **Tools node:** Executes `get_weather` and returns `{"temp": 18, "unit": "celsius", "location": "Paris"}`.

The three agent scripts differ only in how they **instrument** this workflow (OTel spans, Maxim trace/span API, or Confident `@observe`).
