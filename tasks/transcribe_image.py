from google.genai import Client

import logfire

from pydantic_ai import Agent, BinaryContent
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

import os
from dotenv import load_dotenv


SYSTEM_PROMPT = """
<task>
Transcribe the content of the following images to text, maintaining the exact words used. If more than one image is provided, concatenate the text to form one output.
</task>
<output>
The text should be formatted as markdown, and only text from the image should be returned.
</output>
<special-characters>
Use the following notation explicitly for special characters, including -
<checkboxes>
- [ ] (slash space bracket space close-bracket)
</checkboxes>
<completed-checkbox>
- [x]
</completed-checkbox>
<lines>
___
</lines>
<dashed-text>
Wrap text with ~~
</special-characters>
<exceptions>
If there are stars in the margins, DO NOT INCLUDE THEM
</exceptions>
"""

class TranscribeImageAgent():
    def __init__(self):
        load_dotenv()
        GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        model_options = ['gemini-2.5-flash','gemini-2.5-flash-lite', 'gemma-3-27b-it']

        logfire.configure()  
        logfire.instrument_pydantic_ai()

        client = Client(
            api_key=GOOGLE_API_KEY,
        )
        provider = GoogleProvider(client=client)
        self.model = GoogleModel(model_options[0], provider=provider)

    def transcribe(self, image_path: str):
        image = self._get_image(image_path)

        agent = Agent(
            self.model,
            )

        result = agent.run_sync(
            [
                SYSTEM_PROMPT,
                image
            ]
        )

        return result.output

    def _get_image(self, image_path: str):
        return BinaryContent(
            data=open(image_path, 'rb').read(),
            media_type='image/jpeg',
        )

if __name__ == "__main__":
    transcribe_image_agent = TranscribeImageAgent()
    image1_transcription = transcribe_image_agent.transcribe("inputs/example.jpeg")
    image2_transcription = transcribe_image_agent.transcribe("inputs/example2.jpeg")


    # Save transcription to a .md file
    import os
    
    # Create outputs directory if it doesn't exist
    os.makedirs("outputs", exist_ok=True)
    
    with open("outputs/transcription.md", "w") as f:
        f.write(image1_transcription)
        f.write("\n")
        f.write(image2_transcription)
        