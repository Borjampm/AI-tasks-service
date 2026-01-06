import grpc.aio
import ai_service_pb2, ai_service_pb2_grpc
import os
import asyncio
from dotenv import load_dotenv
load_dotenv()

SERVICE_URL = os.getenv("SERVICE_URL", "localhost:50051")
print(f"Connecting to service at {SERVICE_URL}")

async def main():
    if SERVICE_URL == "localhost:50051":
        async with grpc.aio.insecure_channel(SERVICE_URL) as channel:
            stub = ai_service_pb2_grpc.AIServiceStub(channel)

            question = input("What is the question? ")
            async for answer in stub.QA(ai_service_pb2.Question(question=question)):
                print(answer.answer, end="", flush=True)
            print()
    else:
        credentials = grpc.ssl_channel_credentials()
        async with grpc.aio.secure_channel(SERVICE_URL, credentials) as channel:
            stub = ai_service_pb2_grpc.AIServiceStub(channel)

            question = input("What is the question? ")
            async for answer in stub.QA(ai_service_pb2.Question(question=question)):
                print(answer.answer, end="", flush=True)
            print()

if __name__ == "__main__":
    asyncio.run(main())