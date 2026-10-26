import os
import requests
from dotenv import load_dotenv
from pinecone import Pinecone
from google import genai
from huggingface_hub import InferenceClient

load_dotenv()


HF_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
client = InferenceClient(token=HF_TOKEN)


def get_embedding(text):
    """Generate embedding using Hugging Face Inference API."""
    response = client.feature_extraction(
        text, model="sentence-transformers/all-MiniLM-L6-v2"
    )
    return response  # Already a list of floats


# --- 2. Connect to Pinecone ---
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)

print(f"Connected to Pinecone index: {index_name}")


# --- 3. Fetch real data from Google Places ---
def fetch_restaurants(location, max_results=20):
    """Fetch restaurants from Google Places API."""
    API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.location,places.id",
    }
    payload = {"textQuery": f"restaurants in {location}", "maxResultCount": max_results}

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json().get("places", [])


# Upsert in batch
# --- 4. Ingest real data ---
print("\n--- Fetching restaurants from Google Places ---")
places = fetch_restaurants("Los Angeles, CA", 10)

print(f"Fetched {len(places)} restaurants. Generating embeddings and upserting...")

records = []
for i, place in enumerate(places):
    name = place.get("displayName", {}).get("text", "")
    address = place.get("formattedAddress", "")
    text = f"{name}. Located at {address}."

    embedding = get_embedding(text)

    # Convert numpy array to Python list
    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()

    record = {
        "id": place.get("id", f"place_{i}"),
        "values": embedding,
        "metadata": {
            "name": name,
            "address": address,
            "rating": place.get("rating", "N/A"),
            "price_level": place.get("priceLevel", "N/A"),
            "place_id": place.get("id", ""),
        },
    }
    records.append(record)
    print(f"  Embedded: {name}")

print(f"\nUpserting {len(records)} records to Pinecone...")
index.upsert(vectors=records, namespace="restaurants")

print(f"✅ Successfully upserted {len(records)} records")
