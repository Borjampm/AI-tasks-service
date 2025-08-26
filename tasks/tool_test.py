from google.genai import Client

from pydantic_ai import Agent, BinaryContent
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

import os
from dotenv import load_dotenv

import logfire


logfire.configure()  
logfire.instrument_pydantic_ai()

def tool_test():
    """
    Transcribe the text in an image to markdown.
    """
    load_dotenv()
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    model_options = ['gemini-2.5-flash-lite', 'gemma-3-27b-it']

    client = Client(
        api_key=GOOGLE_API_KEY,
    )
    provider = GoogleProvider(client=client)
    model = GoogleModel(model_options[1], provider=provider)

    agent = Agent(
        model,
        # system_prompt="You are a chatbot that can help the user to answer questions",
        )

    # @agent.tool_plain
    # async def database_inventory() -> str:
    #     """Return the contents of a database"""
    #     return {"umbrellas": 5, "shoes": 10}

    user_message = input("What do you want to talk about?")
    result = agent.run_sync(
        user_message
        )
    print(result.output)
    previous_result = result

    while True:
        user_message = input("_______" + "\n")
        if user_message == "exit":
            break
        result = agent.run_sync(
            user_message,
            message_history=previous_result.all_messages()
            )
        print(result.output)
        previous_result = result

    return result.output

if __name__ == "__main__":
    tool_test()