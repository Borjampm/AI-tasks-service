import asyncio
import logfire
from typing import AsyncGenerator

from ai_tasks.agent_factory import AgentFactory

agent_factory = AgentFactory()
agent = agent_factory.get_agent('gemma-3-27b-it')

async def q_a_with_model(question: str) -> AsyncGenerator[str]:
    """
    Answer a question using the model.
    """
    async with agent.run_stream(question) as result:
        async for text in result.stream_text(delta = True):
            yield text




if __name__ == "__main__":
    question = "What is the capital of France?"
    print(f"Question: {question}")
    async def response():
        async for text in q_a_with_model(question):
            print(text, end="", flush=True)
        print()
    asyncio.run(response())