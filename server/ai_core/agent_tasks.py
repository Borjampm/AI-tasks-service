from pydantic_ai import Agent
from typing import AsyncGenerator

from ai_core.agent_factory import AgentFactory

class AgentTasks:
    def __init__(self):
        self.agent_factory = AgentFactory()

    def get_available_models(self) -> list[str]:
        """
        Get the available models.

        Returns:
            - A list of available models.
        """
        return self.agent_factory.get_available_models()

    async def q_a_with_model(self, question: str, model: str) -> AsyncGenerator[str]:
        """
        Answer a question with a given model.

        Args:
            - question: The question to answer.
            - model: The model to use to answer the question.

        Returns:
            - An async generator of the answer to the question.
        """
        agent = self.agent_factory.get_agent(model)
        async with agent.run_stream(question) as result:
            async for text in result.stream_text(delta = True):
                yield text