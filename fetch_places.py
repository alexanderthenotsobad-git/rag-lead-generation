import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_PLACES_API_KEY not found in .env file")


def search_restaurants(max_results=20):
    """Search for mid-priced restaurants near zip 90018."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.location,places.id",
    }
    payload = {
        "textQuery": "restaurants",
        "maxResultCount": max_results,
        "locationRestriction": {
            "rectangle": {
                "low": {
                    "latitude": 34.0000,
                    "longitude": -118.3400
                },
                "high": {
                    "latitude": 34.0600,
                    "longitude": -118.2900
                }
            }
        },
        "priceLevels": ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"]
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json().get("places", [])
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []


# --- Test the function ---
print("Searching for mid-priced restaurants near zip 90018...")
places = search_restaurants(20)

print(f"\nFound {len(places)} restaurants:")
for place in places:
    print(f"- {place.get('displayName', {}).get('text', 'N/A')}")
    print(f"  ID: {place.get('id', 'N/A')}")   
    print(f"  Address: {place.get('formattedAddress', 'N/A')}")
    print(f"  Rating: {place.get('rating', 'N/A')}")
    print(f"  Price Level: {place.get('priceLevel', 'N/A')}")
    print("-" * 40)