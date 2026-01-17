from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from google.genai import Client
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    raise EnvironmentError("GOOGLE_API_KEY environment variable is required")

chat_agent = Agent(
    GoogleModel(
        model_name="gemma-3-27b-it",
        provider=GoogleProvider(client=Client(api_key=api_key))
    )
)
