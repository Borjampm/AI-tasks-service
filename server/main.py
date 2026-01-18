"""Async gRPC server for AI chat service with health checks and graceful shutdown.

This module serves as the main entry point for the gRPC server that handles
streaming chat requests. It manages the server lifecycle including health checks,
session management, and graceful shutdown on SIGTERM/SIGINT signals.

The server exposes two services:
- ChatService: Streaming chat with session persistence
- Health: Standard gRPC health check protocol

Architecture:
    Browser (gRPC-Web) -> Envoy Proxy (:8080) -> gRPC Server (:50051)
"""

import grpc
from grpc import aio
import asyncio
import logging
import os
import signal
import logfire

from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_health.v1.health import HealthServicer

from logging_interceptor import LoggingInterceptor, setup_logging

import chat_service_pb2, chat_service_pb2_grpc
from agents import chat_agent
from sessions import session_store

logger = logging.getLogger(__name__)


class ChatServiceServicer(chat_service_pb2_grpc.ChatServiceServicer):
    """gRPC service implementation for streaming chat with session persistence.

    Handles incoming chat requests by:
    - Managing session IDs for conversation continuity
    - Retrieving and updating message history per session
    - Streaming AI agent responses in real-time

    The servicer integrates with the chat_agent (Pydantic AI) and session_store
    to maintain conversational context across multiple requests.
    """

    async def Chat(self, request, context):
        """Handle streaming chat requests with session-based message history.

        Creates or retrieves a session, streams AI agent responses to the client,
        and updates the session history after completion. Responses are streamed
        as deltas (incremental chunks) for real-time display.

        Args:
            request: ChatRequest protobuf message containing:
                - message: User's chat message
                - session_id: Optional session identifier for conversation continuity
            context: gRPC ServicerContext for setting status codes and details

        Yields:
            ChatResponse: Protobuf messages containing:
                - message: Incremental text chunk from the AI agent
                - session_id: Session identifier for tracking conversation

        Raises:
            grpc.RpcError: With INTERNAL status code if chat processing fails

        Note:
            The final chunk has trailing newlines stripped to avoid rendering issues.
            Session history is updated only after successful completion.
        """
        session_id = request.session_id or session_store.create_session_id()

        try:
            message_history = await session_store.get_history(session_id)

            async with chat_agent.run_stream(
                request.message,
                message_history=message_history
            ) as result:
                pending_chunk = None
                async for text in result.stream_text(delta=True):
                    if pending_chunk is not None:
                        yield chat_service_pb2.ChatResponse(message=pending_chunk, session_id=session_id)
                    pending_chunk = text

                if pending_chunk is not None:
                    yield chat_service_pb2.ChatResponse(
                        message=pending_chunk.rstrip("\n"),
                        session_id=session_id
                    )

                await session_store.update_history(session_id, result.all_messages())
        except Exception:
            logger.exception("Chat request failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details("An internal error occurred")
            raise


async def serve() -> None:
    """Start the gRPC server with health checks and graceful shutdown handling.

    Server lifecycle:
    1. Initializes logging (JSON format for Cloud Logging) and Logfire instrumentation
    2. Starts session cleanup background task (removes expired sessions)
    3. Creates gRPC server with logging interceptor
    4. Registers ChatService and Health services
    5. Binds to port from PORT env var (default: 50051)
    6. Sets up signal handlers for SIGTERM/SIGINT
    7. Starts server and waits for termination

    Graceful shutdown sequence:
    1. Sets health status to NOT_SERVING (stops new requests)
    2. Stops session cleanup task
    3. Waits up to 30 seconds for in-flight RPCs to complete
    4. Closes server

    Environment Variables:
        PORT: Server port (default: 50051)
        GOOGLE_API_KEY: Required for AI agent
        DATABASE_URL: Optional for database-backed features

    Raises:
        RuntimeError: If required environment variables are missing
        OSError: If port binding fails

    Note:
        This function blocks until the server receives a shutdown signal.
        Use asyncio.run(serve()) as the main entry point.
    """
    setup_logging()
    logfire.configure()
    logfire.instrument_pydantic_ai()

    await session_store.start_cleanup_task()

    server = aio.server(
        interceptors=[LoggingInterceptor()]
    )

    chat_service_pb2_grpc.add_ChatServiceServicer_to_server(ChatServiceServicer(), server)

    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    port = os.environ.get("PORT", "50051")
    server.add_insecure_port(f"[::]:{port}")
    print(f"Server starting on port {port}")

    shutdown_task = None

    async def shutdown():
        print("Shutting down gracefully...")
        health_servicer.set("", health_pb2.HealthCheckResponse.NOT_SERVING)
        await session_store.stop_cleanup_task()
        await server.stop(30)

    def handle_signal():
        nonlocal shutdown_task
        if shutdown_task is None:
            shutdown_task = asyncio.create_task(shutdown())

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, handle_signal)
    loop.add_signal_handler(signal.SIGINT, handle_signal)

    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())
