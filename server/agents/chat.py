"""Chat agent configuration using Pydantic AI with Google's Gemma model.

This module initializes a conversational AI agent using Google's Gemma 3 27B model
through the Pydantic AI framework. The agent is configured for streaming chat interactions
and serves as the primary AI backend for the gRPC service.

Environment Variables:
    GOOGLE_API_KEY: Required. API key for Google AI Platform access.

Exports:
    chat_agent: Configured Pydantic AI Agent instance ready for use.

Raises:
    EnvironmentError: If GOOGLE_API_KEY is not set.
"""

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
