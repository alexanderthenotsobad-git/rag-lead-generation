import os
from dotenv import load_dotenv
from pinecone import Pinecone
from google import genai

load_dotenv()

# --- 1. Configure Google Gemini ---
client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def get_embedding(text):
    """Generate embedding using Gemini's embedding model."""
    result = client.models.embed_content(
        model="models/gemini-embedding-2",
        contents=text,
        config={"output_dimensionality": 768},
    )
    return result.embeddings[0].values


# --- 2. Connect to Pinecone ---
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)

print(f"Connected to Pinecone index: {index_name}")

# --- 3. Perform a Lead Generation Query ---
# Pre-filter by metadata: only $$$ restaurants in certain areas
filter_conditions = {
    "$and": [
        {"neighborhood": {"$in": ["Venice", "Downtown"]}},
        {"price_tier": {"$in": ["$$", "$$$"]}},
    ]
}
print(f"Applying metadata filter: {filter_conditions}")

# Semantic query
query_text = "customers frustrated by complex menu terms and expensive ingredients"
query_vector = get_embedding(query_text)

# Search Pinecone
results = index.query(
    vector=query_vector,
    top_k=3,
    filter=filter_conditions,
    namespace="restaurants",
    include_metadata=True,
)

print("\n--- Pinecone Search Results ---")
context_text = ""
for i, match in enumerate(results["matches"]):
    print(f"Rank {i+1}: Score={match['score']:.4f}")
    print(f"  Text: {match['metadata'].get('text', 'N/A')}")
    print(f"  Metadata: {match['metadata']}")
    context_text += f"{match['metadata'].get('text', '')}\n"

# --- 4. Generate B2B Pitch with Gemini LLM ---
if not results["matches"]:
    print("No relevant restaurants found.")
else:
    prompt = f"""
You are a B2B sales analyst for an AI-powered restaurant menu app.
Based on the following customer reviews and context, write a one-paragraph pitch
to the restaurant owner on why our app would solve their problem.

Context from reviews:
{context_text}

Pitch:
"""
    response = client.models.generate_content(
        model="models/gemini-3.6-flash", contents=prompt
    )
    print("\n--- Generated B2B Pitch ---")
    print(response.text)
