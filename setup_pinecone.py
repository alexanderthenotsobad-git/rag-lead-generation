from dotenv import load_dotenv

load_dotenv()

from pinecone import Pinecone, ServerlessSpec
import os

# Initialize Pinecone
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

index_name = "rag-lead-idx"

# Check if index already exists
if pc.has_index(index_name):
    print(f"Index '{index_name}' already exists. Deleting it...")
    pc.delete_index(index_name)

# Create the index with correct specs for Gemini embeddings
print(f"Creating index '{index_name}'...")
pc.create_index(
    name=index_name,
    vector_type="dense",  # We're using dense vectors from Gemini
    dimension=768,  # Matches Gemini text-embedding-004
    metric="cosine",  # Best for semantic similarity
    spec=ServerlessSpec(
        cloud="aws", region="us-east-1"  # Free tier only supports us-east-1
    ),
    deletion_protection="disabled",
)

print(f"✅ Index '{index_name}' created successfully!")
print(f"   Vector Type: dense")
print(f"   Dimension: 768")
print(f"   Metric: cosine")
print(f"   Cloud: AWS us-east-1")

# Verify the index exists
index_info = pc.describe_index(index_name)
print(f"\nIndex status: {index_info.status['state']}")
print(f"Index host: {index_info.host}")
