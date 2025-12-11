from google.genai import Client

from pydantic_ai import Agent, BinaryContent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

import os
from dotenv import load_dotenv
import asyncio
import logfire
from typing import AsyncGenerator


logfire.configure()  
logfire.instrument_pydantic_ai()

load_dotenv()
agent = Agent(GoogleModel('gemma-3-27b-it', provider=GoogleProvider(
    client=Client(api_key=os.getenv('GOOGLE_API_KEY'))
)))

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