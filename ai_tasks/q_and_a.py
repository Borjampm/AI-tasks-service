from google.genai import Client

from pydantic_ai import Agent, BinaryContent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

import os
from dotenv import load_dotenv

def q_a_with_model(question: str) -> str:
    """
    Answer a question using the model.
    """
    load_dotenv()
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    model_options = ['gemma-3-27b-it']

    client = Client(
        api_key=GOOGLE_API_KEY,
    )
    provider = GoogleProvider(client=client)
    model = GoogleModel(model_options[0], provider=provider)

    agent = Agent(
        model
        )
    result = agent.run_sync(
        question
        )
    return result.output