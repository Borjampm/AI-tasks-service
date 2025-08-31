from fastapi import FastAPI
from enum import Enum

from google.genai import Client
from dotenv import load_dotenv
import os

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
model_options = ['gemini-2.5-flash-lite', 'gemma-3-27b-it']

client = Client(
    api_key=GOOGLE_API_KEY,
)

class Provider(str, Enum):
    google = "google"

app = FastAPI()

@app.get("/models/{provider}")
async def get_model(provider: Provider):
    models = client.models.list()
    return {"message": models}

@app.get("/")
async def root():
    return {"message": "Hello World"}
