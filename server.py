import grpc.aio
import time
import random
from concurrent import futures
import asyncio

import service_pb2, service_pb2_grpc
from ai_tasks.q_and_a import q_a_with_model

class AIServiceServicer(service_pb2_grpc.AIServiceServicer):
    async def QA(self, request, context):
        async for text in q_a_with_model(request.question):
            yield service_pb2.Answer(answer=text)

async def serve():
    server = grpc.aio.server()
    service_pb2_grpc.add_AIServiceServicer_to_server(AIServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())