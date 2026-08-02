import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise ValueError("GOOGLE_PLACES_API_KEY not found in .env file")


def search_restaurants(location, max_results=10):
    """Search for restaurants in a given location using the Places API (New)."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.location,places.id",
    }
    payload = {"textQuery": f"restaurants in {location}", "maxResultCount": max_results}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        return response.json().get("places", [])
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return []


def get_place_details(place_id):
    """Fetch detailed information and reviews for a specific place."""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "displayName,formattedAddress,rating,priceLevel,reviews,types",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching details: {response.status_code}")
        return None


# --- Test the functions ---
print("Searching for restaurants in Venice, Los Angeles...")
places = search_restaurants("Venice, Los Angeles", 5)

print(f"\nFound {len(places)} restaurants in Venice:")
for place in places:
    print(f"- {place.get('displayName', {}).get('text', 'N/A')}")
    print(f"  Address: {place.get('formattedAddress', 'N/A')}")
    print(f"  Rating: {place.get('rating', 'N/A')}")
    print(f"  Price Level: {place.get('priceLevel', 'N/A')}")
    print("-" * 40)

# Get details for the first restaurant
if places:
    first_place_id = places[0].get("id")
    if first_place_id:
        place_name = places[0].get("displayName", {}).get("text", "N/A")
        print(f"\nFetching details and reviews for: {place_name}")
        details = get_place_details(first_place_id)

        if details:
            reviews = details.get("reviews", [])
            print(f"Found {len(reviews)} reviews:")
            for review in reviews[:3]:
                review_text = review.get("text", {}).get("text", "")
                print(f"- {review.get('rating', 'N/A')}⭐: {review_text[:100]}...")
