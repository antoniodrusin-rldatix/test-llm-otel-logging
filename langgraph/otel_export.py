"""
OTLP HTTP trace export with no-SSL (Zscaler-friendly). Reuses logic from root otel_llm_log.py.
"""
import gzip
import logging
import os
import zlib
from io import BytesIO
from typing import Any, Optional, Sequence

from requests.exceptions import ConnectionError, Timeout, RequestException

logger = logging.getLogger(__name__)

DEFAULT_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"


def get_otlp_endpoint() -> str:
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if endpoint:
        return endpoint
    base = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip().rstrip("/")
    if not base:
        return DEFAULT_TRACES_ENDPOINT
    return base if base.endswith("v1/traces") else f"{base}/v1/traces"


def get_otlp_headers() -> dict[str, str]:
    from opentelemetry.util.re import parse_env_headers
    s = os.environ.get(
        "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
        os.environ.get("OTEL_EXPORTER_OTLP_HEADERS", ""),
    )
    return parse_env_headers(s, liberal=True) if s else {}


def create_otlp_exporter_no_ssl(endpoint: str, headers: Optional[dict]) -> Any:
    from opentelemetry.exporter.otlp.proto.http import Compression
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    class OTLPSpanExporterNoSSL(OTLPSpanExporter):
        def _export(self, serialized_data: bytes, timeout_sec: Optional[float] = None):
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
                if not resp.ok:
                    body_preview = (resp.text[:1000] + "...") if resp.text and len(resp.text) > 1000 else (resp.text or "(empty)")
                    logger.error(
                        "OTLP trace export HTTP error: status=%s reason=%s url=%s request_content_length=%s response_body=%s",
                        resp.status_code,
                        getattr(resp, "reason", ""),
                        self._endpoint,
                        len(data),
                        body_preview,
                    )
                return resp
            except Timeout as e:
                logger.error(
                    "OTLP trace export timeout: url=%s timeout_sec=%s error=%s",
                    self._endpoint,
                    timeout_sec,
                    e,
                    exc_info=True,
                )
                raise
            except ConnectionError as e:
                logger.error(
                    "OTLP trace export connection error: url=%s error=%s",
                    self._endpoint,
                    e,
                    exc_info=True,
                )
                raise
            except RequestException as e:
                logger.error(
                    "OTLP trace export request error: url=%s error=%s",
                    self._endpoint,
                    e,
                    exc_info=True,
                )
                raise
            except Exception as e:
                logger.exception(
                    "OTLP trace export unexpected error: url=%s error=%s",
                    self._endpoint,
                    e,
                )
                raise

    return OTLPSpanExporterNoSSL(endpoint=endpoint, headers=headers or None)


def wrap_exporter_with_logging(delegate: Any):
    """Wrap an OTLP span exporter to capture and log export result/errors for reporting after shutdown."""
    from opentelemetry.sdk.trace import ReadableSpan
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

    class LoggingSpanExporter(SpanExporter):
        def __init__(self, inner: Any):
            self._inner = inner
            self.last_result: Optional[SpanExportResult] = None
            self.last_error: Optional[Exception] = None

        def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
            self.last_error = None
            try:
                self.last_result = self._inner.export(spans)
                if self.last_result is not SpanExportResult.SUCCESS:
                    logger.warning(
                        "OTLP span export returned failure: result=%s span_count=%s",
                        self.last_result,
                        len(spans) if spans else 0,
                    )
                return self.last_result
            except Exception as e:
                self.last_error = e
                logger.exception("OTLP span export raised: %s", e)
                raise

        def shutdown(self) -> None:
            self._inner.shutdown()

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            return self._inner.force_flush(timeout_millis)

    return LoggingSpanExporter(delegate)
