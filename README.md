# RAG Lead Generation — LA Restaurant Market Study

A retrieval-augmented pipeline that finds Los Angeles restaurants worth pitching an
AI-powered menu app to. The app reads a menu at the ingredient level and generates
personalized recommendations for diners based on dietary needs, macros, and
restrictions — a nutritionist inside every menu.

This repo is the **upstream lead-generation tool**, not the menu app itself.

---

## Status

- Pipeline: **operational end-to-end** (discovery → reviews → chunk → embed → upsert → retrieve → pitch).
- Offline mode: **works with zero API calls** (`--mock`).
- Tests: **39 passing**, no network required.
- Strategy: **under revision** — the original "find customer pain in reviews" thesis has
  a signal problem. See [STRATEGY.md](STRATEGY.md) for the evidence and the recommended
  pivot to menu-first scoring.

The previous revision of this README claimed Gemini embeddings and 768 dimensions.
That is no longer true and must not be reintroduced: **Gemini was abandoned** for
opaque prepay billing and quota exhaustion. Embeddings are Hugging Face
`all-MiniLM-L6-v2` at **384 dimensions**; generation is DeepSeek `deepseek-chat`.

---

## Architecture

| Layer | Choice | Notes |
|---|---|---|
| Orchestration | Python 3.10+ | Ubuntu 22.04 VM, 4 GB RAM |
| Discovery | Google Places API (New), Text Search | rectangular `locationRestriction` only |
| Reviews | HasData Google Maps Reviews | `placeId` in, full `snippet` out; **10 credits/call** |
| Embeddings | HF Inference API, `sentence-transformers/all-MiniLM-L6-v2` | 384 dims, ~256-token window |
| Vector store | Pinecone serverless, `rag-lead-idx` | 384 dims, cosine, AWS `us-east-1` |
| Generation | DeepSeek `deepseek-chat` via OpenAI SDK | `base_url="https://api.deepseek.com"` |

### Retrieval unit: one review, not one restaurant

The original design stored one vector per restaurant — roughly 8,000 characters of
concatenated reviews. That is a blurry average of "good food, nice service, some
complaints," and `all-MiniLM-L6-v2` silently truncated most of it at ~256 tokens.

Now **each review is its own vector**:

- id: `{place_id}_{j}`
- metadata: `restaurant_id`, `name`, `address`, `price_level`, `text`, `review_index`, …
- retrieval: top-k review chunks → regroup by `restaurant_id` → generate **one pitch per restaurant**

`metadata["text"]` is mandatory. Without it DeepSeek has no context and the app is
just a restaurant directory.

### Guardrail

Each pitch prompt is scoped to **one restaurant's** reviews. If those reviews contain
no menu/dietary pain signal, the model must respond with exactly:

```
No relevant pain points found.
```

The string is defined once in `rag_leads/prompts.py` and compared literally after
generation.

---

## Layout

```
.
├── fetch_places.py        # discovery preview only (no writes, no HasData spend)
├── ingest_data.py         # WRITER: discover → reviews → chunk → embed → upsert
├── query_lead.py          # READER: retrieve → regroup → pitch (never ingests)
├── fetch_data.py          # Pinecone stats checker (not discovery)
├── setup_pinecone.py      # create/verify index at 384 dims (safe by default)
├── has_data/has_data1.py  # HasData smoke test for one placeId
├── rag_leads/
│   ├── config.py          # env loading, constants, rectangle/credit helpers
│   ├── embeddings.py      # HF client + response-shape coercion
│   ├── places.py          # Places Text Search (New)
│   ├── hasdata.py         # reviews client + credit accounting
│   ├── deepseek.py        # pitch generation
│   ├── store.py           # Pinecone wrapper + mock store
│   ├── pipeline.py        # chunking and regrouping
│   ├── prompts.py         # guardrail prompt
│   ├── mock.py            # offline fixtures + deterministic fakes
│   └── util.py            # retries, normalization, batching
└── tests/                 # 39 tests, no network
```

Writer/reader separation is intentional. Merging `ingest_data.py` and `query_lead.py`
would re-trigger ingestion on every query.

---

## Quick start (offline, no keys)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python fetch_places.py --mock
python ingest_data.py --mock --max-restaurants 3
python query_lead.py --mock
```

The mock corpus contains a complaint restaurant (Verde Kitchen), a **praise**
restaurant about gluten-free accommodation (Celiac & Co.), and a steakhouse with no
dietary vocabulary. The praise restaurant ranking high is not a bug in the demo —
it is the core strategic finding (see STRATEGY.md).

Run the tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

---

## Live run

```bash
cp .env.example .env        # fill in keys
python setup_pinecone.py    # creates only if missing; verifies 384 dims

# 1. Preview discovery (free of HasData spend)
python fetch_places.py --max-results 20

# 2. Estimate and confirm spend
python ingest_data.py --max-restaurants 5 --dry-run
python ingest_data.py --max-restaurants 5 --yes

# 3. Retrieve and pitch
python query_lead.py --top-k 50 --restaurants 3
python query_lead.py --no-llm            # evidence only
```

### Cost controls

- **HasData**: 10 credits per review call, 1,000 free credits/month → **100 calls**.
  `ingest_data.py` prints the estimate and refuses to spend without `--yes`.
  Test on 2–5 restaurants before scaling to 20 (20 restaurants ≈ 200 credits).
- **Pinecone**: one index, 384 dims, cosine. `setup_pinecone.py` never deletes
  automatically; `--recreate` additionally requires `--yes`.
- **Hugging Face**: embeddings are batched 32 at a time.
- **DeepSeek**: ~$0.03/month at this volume.

If a required key is missing, `RAG_MODE=auto` falls back to mock instead of failing.
Set `RAG_MODE=live` to fail fast, or `RAG_MODE=mock` to force offline.

---

## Known limitations

1. **Embeddings do not know praise from complaint.** Cosine similarity matches topic
   vocabulary ("celiac", "gluten-free", "menu"), so a review praising dietary
   accommodation ranks alongside a review complaining about its absence. Demonstrated
   in `tests/test_end_to_end_mock.py`.
2. **The target pain point is rare.** ~10 reviews per restaurant means the specific
   complaint may appear once per hundreds of restaurants. Proving or disproving it at
   scale is expensive in HasData credits.
3. **Customer pain ≠ B2B purchase reason.** Owners buy average check lift, staff time
   saved, allergen risk reduction, and differentiation — not "our customers are confused."

These are product decisions, not engineering bugs. STRATEGY.md lays out the options.

---

## Pitfalls for the next person

- **Do not reintroduce Gemini**, for embeddings or generation.
- **Do not create the index at 768 dims.** MiniLM is 384. The wrong dimension wastes an
  ingest run and requires an explicit rebuild.
- **Every HasData call costs 10 credits.** Smoke-test one `placeId` first.
- **`locationRestriction` must be a rectangle** with explicit `low` and `high`
  latitude/longitude. Circles and bare pairs return HTTP 400.
- **The Google `place_id` (`ChIJ…`) is the same id HasData accepts.** No translation.
- **Long inputs are silently truncated** by MiniLM; that is why chunking is per review.
- **Do not add stray `Pitch:` or `"""` artifacts** to the prompt; they previously
  caused syntax errors.
