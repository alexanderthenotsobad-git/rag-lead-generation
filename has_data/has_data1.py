import requests
import os
from dotenv import load_dotenv

load_dotenv()

url = "https://api.hasdata.com/scrape/google-maps/reviews"
headers = {"x-api-key": os.getenv("HASDATA_API_KEY")}
params = {"placeId": "ChIJj6arSYLHwoAROfRRqiOfX2s"}  # Park's BBQ

response = requests.get(url, headers=headers, params=params)
print(response.json())
