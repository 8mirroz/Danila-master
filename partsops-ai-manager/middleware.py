import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

# ContextVar to store correlation ID, accessible in current thread/async context
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="SYSTEM")

def get_correlation_id() -> str:
    """Retrieve current correlation ID from the context."""
    return correlation_id_var.get()

class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to extract or generate a Correlation ID for tracing
    every request lifecycle from HTTP down to LLM calls and databases,
    and measure the response latency in milliseconds.
    """
    async def dispatch(self, request: Request, call_next):
        import time
        start_time = time.time()
        corr_id = request.headers.get("X-Correlation-ID") or f"CORR-{uuid.uuid4().hex[:12].upper()}"
        
        token = correlation_id_var.set(corr_id)
        logger = StructuredLogger("request")
        logger.info(f"Incoming request {request.method} {request.url.path}")
        try:
            response = await call_next(request)
            latency_ms = int((time.time() - start_time) * 1000)
            response.headers["X-Correlation-ID"] = corr_id
            response.headers["X-Response-Time-Ms"] = str(latency_ms)
            logger.info(f"Completed request {request.method} {request.url.path} in {latency_ms}ms with status {response.status_code}")
            return response
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Failed request {request.method} {request.url.path} in {latency_ms}ms: {str(e)}")
            raise
        finally:
            correlation_id_var.reset(token)

class StructuredLogger:
    """
    Logger wrapper that injects correlation_id automatically into formatted logs.
    """
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        
    def _log_with_context(self, level, msg, *args, **kwargs):
        extra = kwargs.get("extra", {})
        extra["correlation_id"] = get_correlation_id()
        kwargs["extra"] = extra
        
        from pii import mask_for_log
        masked_msg = mask_for_log(str(msg))
        
        formatted_msg = f"[{get_correlation_id()}] {masked_msg}"
        self.logger.log(level, formatted_msg, *args, **kwargs)
        
    def info(self, msg, *args, **kwargs):
        self._log_with_context(logging.INFO, msg, *args, **kwargs)
        
    def warning(self, msg, *args, **kwargs):
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)
        
    def error(self, msg, *args, **kwargs):
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)
        
    def debug(self, msg, *args, **kwargs):
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)
