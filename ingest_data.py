import os
import time
import requests
from dotenv import load_dotenv
from pinecone import Pinecone
from huggingface_hub import InferenceClient

load_dotenv()

# --- 1. Configure Hugging Face ---
HF_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")  # fix: should be HUGGINGFACE_API_TOKEN
client = InferenceClient(token=HF_TOKEN)

HASDATA_API_KEY = os.getenv("HASDATA_API_KEY")
if not HASDATA_API_KEY:
    raise ValueError("HASDATA_API_KEY not found in .env")


def get_embedding(text):
    """Generate embedding using Hugging Face Inference API."""
    response = client.feature_extraction(
        text, model="sentence-transformers/all-MiniLM-L6-v2"
    )
    return response


# --- 2. Connect to Pinecone ---
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)
print(f"Connected to Pinecone index: {index_name}")


# --- 3. Fetch candidate restaurants from Google Places ---
def fetch_restaurants(max_results=20):
    """Fetch mid-priced restaurants near zip 90018 from Google Places."""
    API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.id",
    }
    payload = {
        "textQuery": "fine dining",
        "maxResultCount": max_results,
        "locationRestriction": {
            "rectangle": {
                "low": {"latitude": 34.0000, "longitude": -118.3400},
                "high": {"latitude": 34.0600, "longitude": -118.2900},
            }
        },
        "priceLevels": ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"],
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json().get("places", [])


# --- 4. Fetch reviews from HasData ---
def fetch_reviews(place_id):
    """Fetch Google Maps reviews for a place via HasData."""
    url = "https://api.hasdata.com/scrape/google-maps/reviews"
    headers = {"x-api-key": HASDATA_API_KEY}
    params = {"placeId": place_id}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code != 200:
        print(f"  HasData error {response.status_code}: {response.text[:200]}")
        return []

    data = response.json()
    reviews = data.get("reviews", [])
    if not reviews:
        return []

    # Return the full snippet from each review as a list
    return [r.get("snippet", "") for r in reviews if r.get("snippet")]


# --- 5. Ingest ---
print("\n--- Fetching candidate restaurants from Google Places ---")
places = fetch_restaurants(3)
print(f"Fetched {len(places)} restaurants. Fetching reviews and upserting...\n")

records = []
for i, place in enumerate(places):
    name = place.get("displayName", {}).get("text", "")
    address = place.get("formattedAddress", "")
    place_id = place.get("id", "")

    print(f"[{i+1}/{len(places)}] {name}")

    reviews = fetch_reviews(place_id)
    if not reviews:
        print("  No reviews. Skipping.")
        continue

    for j, review_text in enumerate(reviews):
        embedding = get_embedding(review_text)
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        print(f"    [{j}] {review_text[:80]}...")

        records.append(
            {
                "id": f"{place_id}_{j}",
                "values": embedding,
                "metadata": {
                    "restaurant_id": place_id,
                    "name": name,
                    "address": address,
                    "rating": place.get("rating", "N/A"),
                    "price_level": place.get("priceLevel", "N/A"),
                    "review_index": j,
                    "text": review_text,
                },
            }
        )

    print(f"  ✅ {len(reviews)} reviews embedded")
    time.sleep(1)

print(f"\nUpserting {len(records)} records to Pinecone...")
index.upsert(vectors=records, namespace="restaurants")
print(f"✅ Successfully upserted {len(records)} records")
