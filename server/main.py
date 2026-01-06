from grpc import aio
import asyncio
import os
import signal

from grpc_health.v1 import health_pb2, health_pb2_grpc
from grpc_health.v1.health import HealthServicer

from logging_interceptor import LoggingInterceptor, setup_logging

import ai_service_pb2, ai_service_pb2_grpc
from agents import chat_agent

class AIServiceServicer(ai_service_pb2_grpc.AIServiceServicer):

    async def QA(self, request, context):
        async with chat_agent.run_stream(request.question) as result:
            async for text in result.stream_text(delta = True):
                yield ai_service_pb2.Answer(answer=text)

async def serve() -> None:
    setup_logging()
    server = aio.server(
        interceptors=[LoggingInterceptor()]
    )

    ai_service_pb2_grpc.add_AIServiceServicer_to_server(AIServiceServicer(), server)

    health_servicer = HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    port = os.environ.get("PORT", "50051")
    server.add_insecure_port(f"[::]:{port}")
    print(f"Server starting on port {port}")

    async def shutdown():
        print("Shutting down gracefully...")
        health_servicer.set("", health_pb2.HealthCheckResponse.NOT_SERVING)
        await server.stop(30)

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(shutdown()))
    loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(shutdown()))
    
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())