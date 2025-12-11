import grpc.aio
import asyncio

import ai_service_pb2, ai_service_pb2_grpc
from ai_core.agent_tasks import AgentTasks

class AIServiceServicer(ai_service_pb2_grpc.AIServiceServicer):
    def __init__(self):
        self.agent_tasks = AgentTasks()

    async def QA(self, request, context):
        async for text in self.agent_tasks.q_a_with_model(request.question, request.model):
            yield ai_service_pb2.Answer(answer=text)

    async def GetAvailableModels(self, request, context):
        return ai_service_pb2.ReturnAvailableModels(models=self.agent_tasks.get_available_models())

async def serve() -> None:
    server = grpc.aio.server()
    ai_service_pb2_grpc.add_AIServiceServicer_to_server(AIServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())