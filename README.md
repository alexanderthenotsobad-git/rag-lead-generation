# RAG Lead Generation for Restaurants

A lightweight RAG (Retrieval-Augmented Generation) application that identifies Los Angeles restaurants most likely to purchase an AI-powered menu app. The system analyzes restaurant reviews using semantic search to find businesses where customers express confusion about menu items, ask about dietary restrictions, or request nutritional information.

## Status: ✅ Working End-to-End

The complete pipeline is operational with mock data:

- Embeddings generated via Gemini (`gemini-embedding-2`, 768 dimensions)
- Stored in Pinecone serverless index with metadata filtering
- Semantic search with pre-filtering by neighborhood and price tier
- B2B pitch generation using Gemini (`gemini-3.6-flash`)

## Architecture

- **Orchestrator**: Python on Ubuntu VM (4GB RAM)
- **Embeddings**: Google Gemini `gemini-embedding-2` (768 dimensions)
- **Vector Database**: Pinecone (serverless, free tier)
- **LLM**: Gemini 3.6 Flash for generating B2B pitches

## How It Works

1. **Ingestion** (`ingest_data.py`): Restaurant review chunks are embedded using Gemini and stored in Pinecone with metadata (neighborhood, price tier, restaurant_id)
2. **Hybrid Search** (`query_lead.py`): Queries filter by metadata first, then perform semantic vector search on the remaining results
3. **Generation**: Gemini synthesizes targeted B2B pitches from retrieved review context

## Setup

```bash
# Clone the repository
git clone git@github.com:alexanderthenotsobad-git/rag-lead-generation.git
cd rag-lead-generation

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install pinecone google-generativeai python-dotenv black

# Create .env file with your API keys
cat > .env << 'EOF'
GOOGLE_API_KEY=your_google_api_key
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=rag-lead-idx
EOF
```
