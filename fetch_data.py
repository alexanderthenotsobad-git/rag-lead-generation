import os
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = os.getenv("PINECONE_INDEX_NAME")
index = pc.Index(index_name)

stats = index.describe_index_stats()
print(f"Total records in index: {stats.total_vector_count}")
print(f"Namespaces: {stats.namespaces}")

if stats.total_vector_count == 0:
    print("Index is empty. Run ingest_data.py first.")
