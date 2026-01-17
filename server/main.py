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

    async def Chat(self, request, context):
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
