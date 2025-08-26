from google.genai import Client

import logfire

from pydantic_ai import Agent, BinaryContent
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

import os
from dotenv import load_dotenv


def transcribe_image(image_path: str):
    """
    Transcribe the text in an image to markdown.
    """
    load_dotenv()
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    model_options = ['gemini-2.5-flash-lite', 'gemma-3-27b-it']

    logfire.configure()  
    logfire.instrument_pydantic_ai()

    client = Client(
        api_key=GOOGLE_API_KEY,
    )
    provider = GoogleProvider(client=client)
    model = GoogleModel(model_options[1], provider=provider)

    image = BinaryContent(
        data=open('inputs/example.jpeg', 'rb').read(),
        media_type='image/jpeg',
    )


    agent = Agent(model)

    result = agent.run_sync(
        [
            'Transcribe the text in this image to markdown',
            image
        ]
    )

    return result.output
        