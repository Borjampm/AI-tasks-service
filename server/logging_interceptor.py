"""gRPC interceptor for Cloud Logging-compatible JSON logging.

Provides structured JSON logging for gRPC requests with timing information,
formatted for Google Cloud Logging compatibility. Supports both unary and
streaming RPC handlers.

Usage:
    from logging_interceptor import setup_logging, LoggingInterceptor

    setup_logging()
    server = aio.server(interceptors=[LoggingInterceptor()])
"""

import json
import logging
import sys
import time
import grpc
from grpc import aio


class CloudLoggingFormatter(logging.Formatter):
    """Formats log records as JSON for Cloud Logging compatibility.

    Converts Python log records into structured JSON with fields:
    - severity: Log level (INFO, ERROR, etc.)
    - message: Formatted log message
    - grpc_method: RPC method name (if present)
    - elapsed_ms: Request duration in milliseconds (if present)
    - exception: Stack trace (if present)

    This format is automatically parsed by Google Cloud Logging.
    """

    def format(self, record):
        """Format a log record as a JSON string.

        Args:
            record: LogRecord instance containing log information.

        Returns:
            JSON string with severity, message, and optional context fields.
        """
        log_entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "method"):
            log_entry["grpc_method"] = record.method
        if hasattr(record, "elapsed_ms"):
            log_entry["elapsed_ms"] = record.elapsed_ms
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging():
    """Configure root logger with Cloud Logging JSON formatter.

    Sets up stdout logging at INFO level with CloudLoggingFormatter.
    Should be called once at application startup.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudLoggingFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])


logger = logging.getLogger("grpc.server")


class LoggingInterceptor(aio.ServerInterceptor):
    """gRPC async server interceptor for request/response logging.

    Logs each RPC call with method name, status (OK/ERROR), and elapsed time.
    Wraps both unary and streaming handlers to capture timing information.

    Usage:
        server = aio.server(interceptors=[LoggingInterceptor()])
    """

    async def intercept_service(self, continuation, handler_call_details):
        """Intercept RPC calls to add logging wrapper.

        Args:
            continuation: Function to invoke the next interceptor or handler.
            handler_call_details: RPC details containing method name and metadata.

        Returns:
            RpcMethodHandler with logging wrapper, or None if handler not found.
        """
        start = time.perf_counter()
        method = handler_call_details.method
        handler = await continuation(handler_call_details)
        
        if handler is None:
            return handler
        
        if handler.unary_unary:
            return grpc.unary_unary_rpc_method_handler(
                _wrap_rpc(handler.unary_unary, method, start),
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        elif handler.unary_stream:
            return grpc.unary_stream_rpc_method_handler(
                _wrap_stream_rpc(handler.unary_stream, method, start),
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler


def _wrap_rpc(fn, method, start):
    """Wrap a unary RPC handler with logging.

    Args:
        fn: Original unary handler function.
        method: RPC method name.
        start: Start time from time.perf_counter().

    Returns:
        Wrapped async function that logs on success or error.
    """
    async def wrapper(request, context):
        try:
            response = await fn(request, context)
            logger.info(f"{method} OK {_elapsed(start)}")
            return response
        except Exception as e:
            logger.error(f"{method} ERROR {_elapsed(start)} - {e}")
            raise
    return wrapper


def _wrap_stream_rpc(fn, method, start):
    """Wrap a streaming RPC handler with logging.

    Args:
        fn: Original streaming handler function (async generator).
        method: RPC method name.
        start: Start time from time.perf_counter().

    Returns:
        Wrapped async generator that logs after stream completion or error.
    """
    async def wrapper(request, context):
        try:
            async for response in fn(request, context):
                yield response
            logger.info(f"{method} OK {_elapsed(start)}")
        except Exception as e:
            logger.error(f"{method} ERROR {_elapsed(start)} - {e}")
            raise
    return wrapper


def _elapsed(start):
    """Calculate elapsed time since start.

    Args:
        start: Start time from time.perf_counter().

    Returns:
        Formatted string with elapsed milliseconds (e.g., "123.4ms").
    """
    return f"{(time.perf_counter() - start) * 1000:.1f}ms"