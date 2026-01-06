import grpc.aio
import ai_service_pb2, ai_service_pb2_grpc

import asyncio

async def main():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = ai_service_pb2_grpc.AIServiceStub(channel)

        question = input("What is the question? ")
        async for answer in stub.QA(ai_service_pb2.Question(question=question)):
            print(answer.answer, end="", flush=True)
        print()

if __name__ == "__main__":
    asyncio.run(main())