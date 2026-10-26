import os
from dotenv import load_dotenv
from pinecone import Pinecone
from huggingface_hub import InferenceClient
from openai import OpenAI

load_dotenv()

# --- 1. Configure Huggingface for embeddings ---
HF_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
hf_client = InferenceClient(token=HF_TOKEN)


def get_embedding(text):
    """Generate embedding using Hugging Face Inference API."""
    response = hf_client.feature_extraction(
        text, model="sentence-transformers/all-MiniLM-L6-v2"
    )
    return response


# --- 2. Configure DeepSeek for LLM generation ---
def generate_llm_response(prompt):
    """Generate response using DeepSeek's chat model."""
    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com"
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {
                "role": "system",
                "content": "You are a B2B sales analyst for an AI-powered restaurant menu app.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return response.choices[0].message.content


# --- 3. Connect to Pinecone ---
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)

print(f"Connected to Pinecone index: {index_name}")

# --- 4. Perform a Lead Generation Query ---
filter_conditions = {
    "price_level": {"$in": ["PRICE_LEVEL_MODERATE", "PRICE_LEVEL_EXPENSIVE"]}
}
print(f"Applying metadata filter: {filter_conditions}")

query_text = "restaurant with complex menu and dietary questions"
query_vector = get_embedding(query_text)

# Convert numpy array to Python list
if hasattr(query_vector, "tolist"):
    query_vector = query_vector.tolist()

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

# --- 5. Generate B2B Pitch with DeepSeek ---
if not results["matches"]:
    print("No relevant restaurants found.")
else:
    prompt = f"""
Based on the following customer reviews and context, write a one-paragraph pitch
to the restaurant owner on why our app would solve their problem.

Context from reviews:
{context_text}

Pitch:
"""
    response_text = generate_llm_response(prompt)
    print("\n--- Generated B2B Pitch ---")
    print(response_text)
