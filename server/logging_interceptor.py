import json
import logging
import sys
import time
import grpc
from grpc import aio


class CloudLoggingFormatter(logging.Formatter):
    def format(self, record):
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
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(CloudLoggingFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])


logger = logging.getLogger("grpc.server")


class LoggingInterceptor(aio.ServerInterceptor):
    async def intercept_service(self, continuation, handler_call_details):
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
    return f"{(time.perf_counter() - start) * 1000:.1f}ms"