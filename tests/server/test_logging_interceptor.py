"""Unit tests for LoggingInterceptor and CloudLoggingFormatter."""

import pytest
import json
import logging
import sys
import time
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, str(__file__).replace("/tests/server/test_logging_interceptor.py", "/server"))

from logging_interceptor import (
    CloudLoggingFormatter,
    setup_logging,
    LoggingInterceptor,
    _wrap_rpc,
    _wrap_stream_rpc,
    _elapsed,
)


# =============================================================================
# CloudLoggingFormatter Tests
# =============================================================================


class TestCloudLoggingFormatterFormat:
    """Tests for CloudLoggingFormatter.format() method."""

    def test_returns_json_with_severity_and_message(self):
        """format() should return JSON with severity and message."""
        formatter = CloudLoggingFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["severity"] == "INFO"
        assert parsed["message"] == "Test message"

    def test_includes_grpc_method_when_present(self):
        """format() should include grpc_method when record has method attribute."""
        formatter = CloudLoggingFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.method = "/chat.ChatService/Chat"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["grpc_method"] == "/chat.ChatService/Chat"

    def test_includes_elapsed_ms_when_present(self):
        """format() should include elapsed_ms when record has elapsed_ms attribute."""
        formatter = CloudLoggingFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.elapsed_ms = 123.45

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["elapsed_ms"] == 123.45

    def test_includes_exception_info_when_present(self):
        """format() should include exception info when record has exc_info."""
        formatter = CloudLoggingFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "Test error" in parsed["exception"]

    def test_different_severity_levels(self):
        """format() should correctly map different log levels to severity."""
        formatter = CloudLoggingFormatter()

        levels = [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.WARNING, "WARNING"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]

        for level, expected_severity in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )
            result = formatter.format(record)
            parsed = json.loads(result)
            assert parsed["severity"] == expected_severity


# =============================================================================
# setup_logging Tests
# =============================================================================


class TestSetupLogging:
    """Tests for setup_logging() function."""

    def test_configures_handler_with_cloud_logging_formatter(self):
        """setup_logging() should configure handler with CloudLoggingFormatter."""
        with patch("logging.StreamHandler") as mock_handler_class:
            mock_handler = MagicMock()
            mock_handler_class.return_value = mock_handler

            with patch("logging.basicConfig") as mock_basic_config:
                setup_logging()

                mock_handler_class.assert_called_once_with(sys.stdout)
                mock_handler.setFormatter.assert_called_once()

                formatter = mock_handler.setFormatter.call_args[0][0]
                assert isinstance(formatter, CloudLoggingFormatter)

                mock_basic_config.assert_called_once_with(
                    level=logging.INFO, handlers=[mock_handler]
                )


# =============================================================================
# LoggingInterceptor Tests
# =============================================================================


class TestLoggingInterceptorInterceptService:
    """Tests for LoggingInterceptor.intercept_service() method."""

    @pytest.mark.asyncio
    async def test_wraps_unary_unary_handlers(self):
        """intercept_service() should wrap unary_unary handlers."""
        interceptor = LoggingInterceptor()

        mock_handler = MagicMock()
        mock_handler.unary_unary = AsyncMock(return_value="response")
        mock_handler.unary_stream = None
        mock_handler.request_deserializer = MagicMock()
        mock_handler.response_serializer = MagicMock()

        mock_continuation = AsyncMock(return_value=mock_handler)
        mock_handler_call_details = MagicMock()
        mock_handler_call_details.method = "/test/Method"

        with patch("logging_interceptor.grpc") as mock_grpc:
            mock_grpc.unary_unary_rpc_method_handler = MagicMock(return_value="wrapped")

            result = await interceptor.intercept_service(
                mock_continuation, mock_handler_call_details
            )

            mock_grpc.unary_unary_rpc_method_handler.assert_called_once()
            assert result == "wrapped"

    @pytest.mark.asyncio
    async def test_wraps_unary_stream_handlers(self):
        """intercept_service() should wrap unary_stream handlers."""
        interceptor = LoggingInterceptor()

        mock_handler = MagicMock()
        mock_handler.unary_unary = None
        mock_handler.unary_stream = AsyncMock()
        mock_handler.request_deserializer = MagicMock()
        mock_handler.response_serializer = MagicMock()

        mock_continuation = AsyncMock(return_value=mock_handler)
        mock_handler_call_details = MagicMock()
        mock_handler_call_details.method = "/test/StreamMethod"

        with patch("logging_interceptor.grpc") as mock_grpc:
            mock_grpc.unary_stream_rpc_method_handler = MagicMock(return_value="wrapped_stream")

            result = await interceptor.intercept_service(
                mock_continuation, mock_handler_call_details
            )

            mock_grpc.unary_stream_rpc_method_handler.assert_called_once()
            assert result == "wrapped_stream"

    @pytest.mark.asyncio
    async def test_returns_none_handler_unchanged(self):
        """intercept_service() should return None handler unchanged."""
        interceptor = LoggingInterceptor()

        mock_continuation = AsyncMock(return_value=None)
        mock_handler_call_details = MagicMock()
        mock_handler_call_details.method = "/test/Method"

        result = await interceptor.intercept_service(
            mock_continuation, mock_handler_call_details
        )

        assert result is None


# =============================================================================
# _wrap_rpc Tests
# =============================================================================


class TestWrapRpc:
    """Tests for _wrap_rpc() function."""

    @pytest.mark.asyncio
    async def test_logs_ok_on_success_with_timing(self):
        """_wrap_rpc() should log 'OK' on success with timing."""
        async def mock_fn(request, context):
            return "response"

        start = time.perf_counter()
        wrapped = _wrap_rpc(mock_fn, "/test/Method", start)

        with patch("logging_interceptor.logger") as mock_logger:
            result = await wrapped("request", MagicMock())

            assert result == "response"
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "/test/Method" in log_message
            assert "OK" in log_message
            assert "ms" in log_message

    @pytest.mark.asyncio
    async def test_logs_error_on_exception_with_timing(self):
        """_wrap_rpc() should log 'ERROR' on exception with timing."""
        async def mock_fn(request, context):
            raise ValueError("Test error")

        start = time.perf_counter()
        wrapped = _wrap_rpc(mock_fn, "/test/Method", start)

        with patch("logging_interceptor.logger") as mock_logger:
            with pytest.raises(ValueError):
                await wrapped("request", MagicMock())

            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]
            assert "/test/Method" in log_message
            assert "ERROR" in log_message
            assert "ms" in log_message


# =============================================================================
# _wrap_stream_rpc Tests
# =============================================================================


class TestWrapStreamRpc:
    """Tests for _wrap_stream_rpc() function."""

    @pytest.mark.asyncio
    async def test_logs_ok_after_yielding_all_responses(self):
        """_wrap_stream_rpc() should log 'OK' after yielding all responses."""
        async def mock_fn(request, context):
            yield "response1"
            yield "response2"

        start = time.perf_counter()
        wrapped = _wrap_stream_rpc(mock_fn, "/test/StreamMethod", start)

        with patch("logging_interceptor.logger") as mock_logger:
            responses = []
            async for response in wrapped("request", MagicMock()):
                responses.append(response)

            assert responses == ["response1", "response2"]
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "/test/StreamMethod" in log_message
            assert "OK" in log_message
            assert "ms" in log_message

    @pytest.mark.asyncio
    async def test_logs_error_on_exception(self):
        """_wrap_stream_rpc() should log 'ERROR' on exception."""
        async def mock_fn(request, context):
            yield "response1"
            raise ValueError("Stream error")

        start = time.perf_counter()
        wrapped = _wrap_stream_rpc(mock_fn, "/test/StreamMethod", start)

        with patch("logging_interceptor.logger") as mock_logger:
            responses = []
            with pytest.raises(ValueError):
                async for response in wrapped("request", MagicMock()):
                    responses.append(response)

            assert responses == ["response1"]
            mock_logger.error.assert_called_once()
            log_message = mock_logger.error.call_args[0][0]
            assert "/test/StreamMethod" in log_message
            assert "ERROR" in log_message


# =============================================================================
# _elapsed Tests
# =============================================================================


class TestElapsed:
    """Tests for _elapsed() function."""

    def test_returns_formatted_milliseconds_string(self):
        """_elapsed() should return formatted milliseconds string."""
        start = time.perf_counter()
        time.sleep(0.01)  # Sleep 10ms

        result = _elapsed(start)

        assert result.endswith("ms")
        # Extract the number part and verify it's reasonable
        ms_value = float(result.replace("ms", ""))
        assert ms_value >= 10.0  # At least 10ms
        assert ms_value < 1000.0  # Less than 1 second

    def test_returns_one_decimal_precision(self):
        """_elapsed() should return value with one decimal precision."""
        start = time.perf_counter()

        result = _elapsed(start)

        # Should have format like "0.1ms" or "123.4ms"
        ms_part = result.replace("ms", "")
        if "." in ms_part:
            decimal_places = len(ms_part.split(".")[1])
            assert decimal_places == 1
