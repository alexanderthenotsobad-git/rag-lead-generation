import os
import time
from dotenv import load_dotenv
from pinecone import Pinecone
from google import genai

load_dotenv()

# --- 1. Configure Google Gemini for embeddings ---
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def get_embedding(text):
    """Generate embedding using Gemini's embedding model."""
    result = client.models.embed_content(
        model="models/gemini-embedding-2",  # Changed this
        contents=text,
        config={"output_dimensionality": 768},
    )
    return result.embeddings[0].values


# --- 2. Connect to Pinecone ---
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)

print(f"Connected to Pinecone index: {index_name}")

# --- 3. Simulate Data Ingestion (Replace with your real data) ---
documents = [
    {
        "text": "This place has amazing vegan options and the staff is very knowledgeable about macros. Perfect for gym-goers.",
        "metadata": {
            "restaurant_id": "001",
            "neighborhood": "Venice",
            "price_tier": "$$",
        },
    },
    {
        "text": "The menu is incredibly complex with many culinary terms. The waiter had to explain every dish to us.",
        "metadata": {
            "restaurant_id": "002",
            "neighborhood": "Downtown",
            "price_tier": "$$$",
        },
    },
    {
        "text": "Fast food burgers and fries. Nothing special for health-conscious customers.",
        "metadata": {
            "restaurant_id": "003",
            "neighborhood": "Hollywood",
            "price_tier": "$",
        },
    },
]

print("\n--- Starting Ingestion ---")

# --- 4. Generate embeddings and upsert ---
records = []
for i, doc in enumerate(documents):
    # Generate embedding
    embedding = get_embedding(doc["text"])

    # Create record for Pinecone (v9+ format)
    record = {
        "id": f"doc_{i+1}",  # Correct - use 'id' not '_id'
        "values": embedding,
        "metadata": doc["metadata"],
    }
    records.append(record)
    print(f"Generated embedding for doc {i+1}")

# Upsert in batch
print(f"\nUpserting {len(records)} records to Pinecone...")
index.upsert(vectors=records, namespace="restaurants")

print(f"✅ Successfully upserted {len(records)} records to namespace 'restaurants'")
