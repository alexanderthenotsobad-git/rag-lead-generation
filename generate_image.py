import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

client = genai.Client(api_key=API_KEY)

prompt = "Create a picture of a map of Los Angeles County with a robot version of Roldan's The thinking man"
response = client.models.generate_content(
    model="gemini-3.6-flash",  # Text model that can also output images
    contents=prompt,
    config=types.GenerateContentConfig(
        response_modalities=["IMAGE"],
    ),
)

for part in response.parts:
    if part.inline_data is not None:
        image = part.as_image()
        image.save("generated_image.png")
