import grpc.aio
import service_pb2, service_pb2_grpc
import asyncio

async def main():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = service_pb2_grpc.AIServiceStub(channel)
        question = input("What is the question? ")
        async for answer in stub.QA(service_pb2.Question(question=question)):
            print(answer.answer, end="", flush=True)
        print()

if __name__ == "__main__":
    asyncio.run(main())