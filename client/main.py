import grpc.aio
import ai_service_pb2, ai_service_pb2_grpc

import asyncio

async def main():
    async with grpc.aio.insecure_channel("localhost:50051") as channel:
        stub = ai_service_pb2_grpc.AIServiceStub(channel)
        available_models = await stub.GetAvailableModels(ai_service_pb2.EmptyMessage())
        print("Choose a model:")
        for i, model in enumerate(available_models.models)  :
            print(f"{i+1}. {model}")
        model_index = int(input("Enter the model number: "))
        model = available_models.models[model_index - 1]

        question = input("What is the question? ")
        async for answer in stub.QA(ai_service_pb2.Question(question=question, model=model)):
            print(answer.answer, end="", flush=True)
        print()

if __name__ == "__main__":
    asyncio.run(main())