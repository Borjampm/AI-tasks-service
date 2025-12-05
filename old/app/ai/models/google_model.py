from app.ai.models.base_model import BaseModel
from google.genai import Client
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.models.google import GoogleModel
import os
from dotenv import load_dotenv
import logfire

logfire.configure()  
logfire.instrument_pydantic_ai()

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

class BaseGoogleModel(BaseModel):

    def __init__(self, model_name: str):
        self.__model_name = model_name
        client = Client(api_key=GOOGLE_API_KEY)
        provider = GoogleProvider(client=client)
        self.__model = GoogleModel(model_name, provider=provider)

    def get_model(self):
        return self.__model