import grpc.aio
import asyncio
import os

import ai_service_pb2, ai_service_pb2_grpc
from agents import chat_agent

class AIServiceServicer(ai_service_pb2_grpc.AIServiceServicer):

    async def QA(self, request, context):
        async with chat_agent.run_stream(request.question) as result:
            async for text in result.stream_text(delta = True):
                yield ai_service_pb2.Answer(answer=text)

async def serve() -> None:
    port = os.environ.get("PORT", "50051")
    server = grpc.aio.server()
    ai_service_pb2_grpc.add_AIServiceServicer_to_server(AIServiceServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    print(f"Server starting on port {port}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())