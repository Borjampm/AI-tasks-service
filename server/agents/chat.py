from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from google.genai import Client
import os
from dotenv import load_dotenv

load_dotenv()

chat_agent = Agent(
    GoogleModel(
        model_name="gemma-3-27b-it", 
        provider=GoogleProvider(client=Client(api_key=os.getenv('GOOGLE_API_KEY')))
    )
)