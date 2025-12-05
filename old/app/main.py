from fastapi import FastAPI

from dotenv import load_dotenv
from app.ai.models.google_model import BaseGoogleModel

load_dotenv()

app = FastAPI()
model 

@app.get("/")
async def root():
    return {"message": "Hello World"}
