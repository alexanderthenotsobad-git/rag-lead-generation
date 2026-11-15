# RAG Lead Generation — LA Restaurant Market

A live retrieval-augmented pipeline that finds Los Angeles restaurants worth
pitching an AI-powered menu consultant to. The consultant reads a menu at the
ingredient level and answers diners' allergy, dietary, and macro questions in
natural language.

This repo is the **upstream lead-generation tool**, not the menu app itself.

---

## Status

- Pipeline: **live end-to-end** — discovery → reviews → chunk → embed → upsert
  → retrieve → classify → pitch.
- Data: real Google Places and HasData results in Pinecone.
- Tests: `pytest -q` covers the gates, classifier parser, chunking, grouping,
  prompt guardrail, and index safety.
- Strategy: under revision; the review signal is weaker than expected. See
  [STRATEGY.md](STRATEGY.md).

The embedding model is Hugging Face `all-MiniLM-L6-v2` at **384 dimensions**.
Generation is DeepSeek `deepseek-chat`. Gemini is intentionally absent.

---

## Architecture

| Layer | Choice | Notes |
|---|---|---|
| Orchestration | Python 3.10+ | Ubuntu/WSL, 4 GB RAM is enough |
| Discovery | Google Places API (New), Text Search | rectangular `locationRestriction` only |
| Reviews | HasData Google Maps Reviews | `placeId` in, full `snippet` out; **10 credits/call** |
| Embeddings | HF Inference API, `sentence-transformers/all-MiniLM-L6-v2` | 384 dims, ~256-token window |
| Vector store | Pinecone serverless, `rag-lead-idx` | 384 dims, cosine, AWS `us-east-1` |
| Generation | DeepSeek `deepseek-chat` via OpenAI SDK | `base_url="https://api.deepseek.com"` |

### Retrieval unit: one review, not one restaurant

Each review is its own vector:

- id: `{place_id}_{j}`
- metadata: `restaurant_id`, `name`, `address`, `price_level`, `text`,
  `review_index`, `review_rating`, `rating_bucket`, `keyword_hit`,
  `complaint_candidate`
- retrieval: top-k review chunks → regroup by `restaurant_id` → classify →
  generate **one pitch per restaurant**

`metadata["text"]` is mandatory. Without it DeepSeek has no context.

### Three gates before generation

1. **Rating gate** — 1–3 stars are complaint candidates; 4–5 stars are praise;
   missing ratings pass only when the keyword gate also fires.
2. **Keyword gate** — the review must mention an allergen, ingredient, or
   dietary term.
3. **LLM classifier** — `COMPLAINT`, `PRAISE`, or `IRRELEVANT`, with a required
   quote. Only `COMPLAINT` reviews feed the pitch prompt.

### Guardrail

Each pitch prompt is scoped to **one restaurant's** complaint reviews. If no
complaint survives classification, the pipeline returns exactly:

```
No relevant pain points found.
```

The string is defined once in `rag_leads/prompts.py` and compared literally.

---

## Layout

```
.
├── fetch_places.py        # discovery preview (no writes, no HasData spend)
├── ingest_data.py         # WRITER: discover → reviews → chunk → embed → upsert
├── query_lead.py          # READER: retrieve → classify → pitch
├── fetch_data.py          # Pinecone stats checker (not discovery)
├── setup_pinecone.py      # create/verify index at 384 dims (safe by default)
├── has_data/has_data1.py  # HasData smoke test for one placeId
├── rag_leads/
│   ├── config.py          # env loading, constants, area presets
│   ├── embeddings.py      # HF client + response-shape coercion
│   ├── places.py          # Places Text Search (New)
│   ├── hasdata.py         # reviews client + credit accounting
│   ├── deepseek.py        # pitch generation
│   ├── classify.py        # COMPLAINT / PRAISE / IRRELEVANT classifier
│   ├── gates.py           # rating + keyword gates
│   ├── store.py           # Pinecone wrapper
│   ├── pipeline.py        # chunking and regrouping
│   ├── prompts.py         # guardrail and classifier prompts
│   └── util.py            # retries, normalization, batching
└── tests/
```

Writer/reader separation is intentional. Merging `ingest_data.py` and
`query_lead.py` would re-trigger ingestion on every query.

---

## Setup

See [WSL-RAG-SETUP.md](WSL-RAG-SETUP.md) for the full WSL walkthrough.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env
nano .env          # fill in the five keys
```

Required keys: `PINECONE_API_KEY`, `HUGGINGFACE_API_TOKEN`,
`GOOGLE_PLACES_API_KEY`, `HASDATA_API_KEY`, `DEEPSEEK_API_KEY`.

If a key is missing, the pipeline fails closed. There is no offline fallback.

---

## Live run

```bash
python setup_pinecone.py          # creates only if missing; verifies 384 dims

# 1. Preview discovery (no HasData spend)
python fetch_places.py --max-results 20 --text-query "healthy restaurant"

# 2. Estimate and confirm spend
python ingest_data.py --max-restaurants 5 --dry-run
python ingest_data.py --max-restaurants 5 --yes

# 3. Retrieve, classify, pitch
python query_lead.py --top-k 50 --restaurants 3 --max-classify 5
python query_lead.py --no-llm            # evidence only
python query_lead.py --json              # machine-readable
```

For a Santa Monica run, use the area preset and a dedicated namespace:

```bash
export PINECONE_NAMESPACE=santa-monica
python fetch_places.py --area santa-monica --text-query "healthy restaurant"
python ingest_data.py --area santa-monica --max-restaurants 10 \
  --text-query "healthy restaurant" --dry-run
python ingest_data.py --area santa-monica --max-restaurants 10 \
  --text-query "healthy restaurant" --yes
python query_lead.py --top-k 50 --restaurants 5 --max-classify 5
```

`query_lead.py` has no geographic filter; the namespace is what isolates an
area. `--area` changes only the discovery rectangle.

### Save results

```bash
mkdir -p results
STAMP=$(date +%Y%m%d_%H%M%S)
python query_lead.py --top-k 50 --restaurants 5 --max-classify 5 \
  2> "results/query_${STAMP}.err" | tee "results/query_${STAMP}.log"
```

For JSON, strip the CLI preamble:

```bash
python query_lead.py --top-k 50 --restaurants 5 --max-classify 5 --json \
  2> "results/query_${STAMP}.json.err" \
  | awk 'BEGIN{p=0} /^\[/{p=1} p' > "results/query_${STAMP}.json"
```

---

## Cost controls

- **HasData**: 10 credits per review call, 1,000 free credits/month → 100 calls.
  `ingest_data.py` prints the estimate and refuses to spend without `--yes`.
- **Pinecone**: one index, 384 dims, cosine. `setup_pinecone.py` never deletes
  automatically; `--recreate` additionally requires `--yes`.
- **Hugging Face**: embeddings are batched 32 at a time.
- **DeepSeek**: one classifier call per candidate (`--max-classify`) and one
  pitch call per restaurant that has a complaint.

---

## Known limitations

1. **Embeddings do not know praise from complaint.** Cosine similarity matches
   topic vocabulary, so a review praising dietary accommodation ranks alongside
   a complaint. The classifier is the precision layer.
2. **The target pain point is rare.** ~10 reviews per restaurant means the
   specific complaint may appear once per hundreds of restaurants.
3. **Customer pain is not a purchase reason.** Owners buy check lift, staff
   time, allergen risk reduction, and differentiation. See STRATEGY.md.

---

## Pitfalls

- **Do not reintroduce Gemini**, for embeddings or generation.
- **Do not create the index at 768 dims.** MiniLM is 384.
- **Every HasData call costs 10 credits.** Smoke-test one `placeId` first.
- **`locationRestriction` must be a rectangle** with explicit `low` and `high`.
  Circles and bare pairs return HTTP 400.
- **The Google `place_id` (`ChIJ…`) is the same id HasData accepts.**
- **Long inputs are silently truncated** by MiniLM; that is why chunking is per
  review.
- **Do not add stray `Pitch:` or `"""` artifacts** to the prompt.
