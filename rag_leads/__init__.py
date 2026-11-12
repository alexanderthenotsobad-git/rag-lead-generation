"""RAG lead generation for Los Angeles restaurants.

Discovers candidate restaurants, chunks review text one review per vector,
embeds with Hugging Face ``all-MiniLM-L6-v2`` (384 dims), stores in Pinecone,
and generates per-restaurant B2B pitches with DeepSeek.
"""

__version__ = "2.0.0"
