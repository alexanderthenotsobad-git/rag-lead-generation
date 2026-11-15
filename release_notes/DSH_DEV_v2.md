# DSH_DEV_v2 — Complaint gating and classification

**Status:** implemented and verified with the unit suite (41 passed). No ingest
runs or live API calls were performed.

**Scope:** the RAG LA Restaurant project. NVRS is a separate project.

---

## 1. What changed

The pipeline now applies three gates before a pitch is generated:

1. **Rating gate** — `1–3` stars are complaint candidates; `4–5` stars are
   treated as praise; missing ratings are retained but only pass when the
   keyword gate also fires.
2. **Keyword gate** — the review must mention an allergen, ingredient, or
   dietary term.
3. **LLM classifier** — the review is labelled `COMPLAINT`, `PRAISE`, or
   `IRRELEVANT`, and a `COMPLAINT` must return an exact supporting quote.

Only `COMPLAINT` reviews feed the pitch prompt. Praise and irrelevant reviews
are filtered before generation, which saves classifier and generation calls.

The allergen pitch prompt itself was not rewritten; only the classifier prompt
and the gating logic are new.

---

## 2. New flow

```text
Pinecone top-k review chunks
        │
        ▼
group_matches()  → one group per restaurant
        │
        ▼
candidate_matches()
  rating <= 3  AND  keyword hit
        │
        ▼
ReviewClassifier.classify()  (max --max-classify per restaurant)
        │
        ├── COMPLAINT + quote ──► build_pitch_prompt() → DeepSeek pitch
        └── PRAISE / IRRELEVANT / no quote ──► No relevant pain points found.
```

Old records that lack the new metadata still work: `is_complaint_candidate()`
recomputes the gates from `review_rating` and `text`.

---

## 3. Files changed

| File | Change |
|---|---|
| `rag_leads/gates.py` | **New.** Rating gate, keyword regex, candidate filter |
| `rag_leads/classify.py` | **New.** Classifier client and `LABEL`/`QUOTE` parser |
| `rag_leads/config.py` | Added `SANTA_MONICA_BOX` and `AREA_BOXES` presets |
| `fetch_places.py` | Added `--area central-la|santa-monica` |
| `rag_leads/prompts.py` | Added `CLASSIFIER_SYSTEM_PROMPT`, `CLASSIFIER_INSTRUCTIONS`, `build_classifier_prompt()` |
| `rag_leads/pipeline.py` | `build_records()` now stores `rating_bucket`, `keyword_hit`, `complaint_candidate` |
| `query_lead.py` | Candidate filtering, classification, `--max-classify`, `--no-classifier`, JSON fields |
| `ingest_data.py` | `--candidates-only` to embed only gate-passing reviews |
| `tests/test_gates.py` | **New.** Gate and metadata tests |
| `tests/test_classification.py` | **New.** Classifier parser tests |

---

## 4. Execution runbook

Run everything from the repo root, inside the virtual environment.

```bash
cd ~/rag-la-restaurant/rag-lead-generation
source .venv/bin/activate
```

### Step 1 — Syntax check

```bash
python -m compileall -q rag_leads query_lead.py ingest_data.py
```

### Step 2 — Unit tests

```bash
pytest -q
```

The existing suite plus the two new test files should pass. If anything fails,
stop before making live calls.

### Step 3 — Live-only check

The pipeline is live-only. There is no offline run. If a key is missing,
configuration fails closed before any API call.

### Step 4 — Live evidence only

```bash
python query_lead.py \
  --query "Customers with a food allergy, intolerance, or celiac disease who could not get clear information about ingredients, allergens, or cross-contamination, or which dishes were safe to eat, and felt the staff were guessing or unsure." \
  --top-k 50 \
  --restaurants 5 \
  --no-llm
```

This shows retrieved evidence and a `Candidates:` count per restaurant, with no
DeepSeek call. Use it to confirm the gates are selecting reasonable reviews
before paying for classification.

### Step 5 — Live classification and pitch

```bash
python query_lead.py \
  --query "Customers with a food allergy, intolerance, or celiac disease who could not get clear information about ingredients, allergens, or cross-contamination, or which dishes were safe to eat, and felt the staff were guessing or unsure." \
  --top-k 50 \
  --restaurants 5 \
  --max-classify 5
```

`--max-classify` caps classifier calls per restaurant. Default is 5; 5
restaurants therefore cost at most 25 classifier calls, and only restaurants
with candidates make any.

### Step 5b — Save the results to a file

The CLI prints to stdout by default. To keep a timestamped record, from the repo
root:

```bash
mkdir -p results
STAMP=$(date +%Y%m%d_%H%M%S)
```

Human-readable log:

```bash
python query_lead.py \
  --query "Customers with a food allergy, intolerance, or celiac disease who could not get clear information about ingredients, allergens, or cross-contamination, or which dishes were safe to eat, and felt the staff were guessing or unsure." \
  --top-k 50 \
  --restaurants 5 \
  --max-classify 5 \
  2> "results/query_${STAMP}.err" \
  | tee "results/query_${STAMP}.log"
```

Machine-readable JSON:

```bash
python query_lead.py \
  --query "Customers with a food allergy, intolerance, or celiac disease who could not get clear information about ingredients, allergens, or cross-contamination, or which dishes were safe to eat, and felt the staff were guessing or unsure." \
  --top-k 50 \
  --restaurants 5 \
  --max-classify 5 \
  --json \
  2> "results/query_${STAMP}.json.err" \
  | awk 'BEGIN{p=0} /^\[/{p=1} p' \
  > "results/query_${STAMP}.json"
```

View what you captured:

```bash
ls -lt results | head
less results/query_*.log
jq '.[] | {name, candidate_count, complaints: (.complaint_reviews | length), pitch}' results/query_*.json
```

Notes:

- `--json` still prints the `Mode / Index / Filter / Query` preamble to stdout.
  The `awk` step drops everything before the first `[`, so the `.json` file
  contains only the results array.
- If the run returns no matches, the `.json` file can be empty; check the
  matching `.err` file.
- `results/` holds review text and pitches. Add it to `.gitignore` if you keep
  the artifacts in the repo.

### Step 6 — Optional ingest change

Default ingest still embeds every review. To embed only gate-passing reviews:

```bash
python ingest_data.py --max-restaurants 5 --dry-run
python ingest_data.py --max-restaurants 5 --yes --candidates-only
```

`--candidates-only` saves Hugging Face calls but removes praise and irrelevant
reviews from the index, which disables the anti-pain path. Do not use it if you
still need praise-based leads. Pinecone cannot store a review without a vector,
so skipping the embedding also skips the record; this is not a metadata-only
filter.

Re-ingesting with the default (without `--candidates-only`) persists the new
gate metadata. Old vectors work through the fallback, but the stored flags make
query-time filtering cheaper and more consistent.

---

### Step 7 — Santa Monica / beach run

`query_lead.py` has no geographic filter. Area is controlled at **discovery and
ingest** time, and isolation is controlled by the **Pinecone namespace**. If you
ingest Santa Monica into the default namespace, results will mix with the
existing central-LA corpus.

The repo now has two presets in `rag_leads/config.py`:

| `--area` | Rectangle (low → high) |
|---|---|
| `central-la` | `34.02,-118.28` → `34.07,-118.22` |
| `santa-monica` | `33.98,-118.52` → `34.05,-118.43` |

Use a dedicated namespace for the area run:

```bash
export PINECONE_NAMESPACE=santa-monica
```

Preview discovery first. This spends no HasData credits:

```bash
python fetch_places.py --area santa-monica --max-results 20 \
  --text-query "healthy restaurant"
```

Try `"vegan restaurant"` or `"gluten free restaurant"` as alternate discovery
queries; one query per preview.

Ingest. Ten restaurants is about 100 HasData credits, so dry-run first:

```bash
python ingest_data.py --area santa-monica --max-restaurants 10 \
  --text-query "healthy restaurant" --dry-run

python ingest_data.py --area santa-monica --max-restaurants 10 \
  --text-query "healthy restaurant" --yes
```

Run the same allergen query against the Santa Monica namespace:

```bash
python query_lead.py \
  --query "Customers with a food allergy, intolerance, or celiac disease who could not get clear information about ingredients, allergens, or cross-contamination, or which dishes were safe to eat, and felt the staff were guessing or unsure." \
  --top-k 50 \
  --restaurants 5 \
  --max-classify 5
```

Save the results using Step 5b; the exported namespace applies to those
commands too.

Verify what is in the namespace:

```bash
python fetch_data.py
```

It prints every namespace and its vector count.

Return to the default corpus when done:

```bash
unset PINECONE_NAMESPACE
```

Notes:

- `--area` changes only the discovery rectangle. It does **not** add an `area`
  field to review metadata. The namespace is what keeps Santa Monica results
  separate from central LA.
- Price levels are filtered at query time. Pass the same `--price-level` values
  to ingest and query. For fast-casual, add
  `--price-level INEXPENSIVE --price-level MODERATE` to both commands.
- `ingest_data.py` upserts by `{place_id}_{j}`, so re-running the same area is
  idempotent. Different discovery queries may surface different places.
- If you skip the namespace export, both areas land in the default namespace
  and the query cannot separate them.

## 5. Calibration protocol

The defaults (`COMPLAINT_MAX_RATING = 3`, broad keyword regex) are starting
points, not tuned values.

1. Produce an evidence dump:

   ```bash
   python query_lead.py --query "<your query>" --top-k 100 --restaurants 10 \
     --no-llm --json > run_no_llm.json
   ```

2. Hand-label 50 reviews from the `reviews` arrays as `COMPLAINT`, `PRAISE`, or
   `IRRELEVANT`. Keep the restaurant ID and review text.

3. Compare thresholds. `COMPLAINT_MAX_RATING` lives in `rag_leads/gates.py`.
   Try `2` (strict), `3` (default), and a version with the rating gate disabled
   (treat every keyword hit as a candidate). Compute:

   - precision: labelled complaints ÷ classifier complaints,
   - recall: classifier complaints ÷ hand-labelled complaints,
   - cost per complaint: classifier calls ÷ complaints found.

4. Adjust `KEYWORD_PATTERN` in `rag_leads/gates.py` only after the threshold is
   settled. Change one variable at a time.

5. Re-run the same 50 reviews through `ReviewClassifier` and compare. Do not
   judge a threshold by one restaurant.

The classifier parser is deliberately conservative: a `COMPLAINT` without a
`QUOTE`, or an unrecognised label, becomes `IRRELEVANT`. That lowers recall but
protects the pitch from unsupported claims.

---

## 6. Cost controls

- Rating and keyword gates are local and free.
- One classifier call per candidate, capped by `--max-classify`.
- One pitch call per restaurant that has at least one `COMPLAINT`.
- Restaurants with no candidates cost zero LLM calls.
- `--no-classifier` skips the precision layer and pitches directly from cheap
  candidates; use it only for debugging, not for production leads.

---

## 7. Rollback

The change is additive. To revert:

```bash
git diff
git checkout -- query_lead.py ingest_data.py rag_leads/pipeline.py
rm rag_leads/gates.py rag_leads/classify.py
rm tests/test_gates.py tests/test_classification.py
```

`rag_leads/prompts.py` is intentionally not reverted: it also contains the
current allergen pitch prompt. If you need to remove only the classifier
prompt, delete the `CLASSIFIER_*` block and `build_classifier_prompt()` manually.

Existing Pinecone records are unaffected. New metadata fields are ignored by
the old code.

---

## 8. Known limitations

- **High-star complaints are excluded.** A 5-star review that contains a real
  complaint (“amazing, but they couldn’t confirm my allergy”) fails the rating
  gate. This is the deliberate precision/recall tradeoff; lower
  `COMPLAINT_MAX_RATING` or add a “buried complaint” rule only after measuring.
- **Missing ratings pass on keyword alone.** Sources without a rating field are
  treated as unknown, not praise.
- **The keyword regex is broad.** It is a recall gate, not a classifier. The
  LLM label is the precision layer.
- **Definitions are allergen-specific.** The classifier drops vegan-only or
  menu-complexity complaints as `IRRELEVANT` unless you edit
  `CLASSIFIER_INSTRUCTIONS` and `KEYWORD_PATTERN` together.
- **Classifier format drift.** The parser expects `LABEL:` and `QUOTE:` lines.
  A model that returns prose will be downgraded to `IRRELEVANT`, not guessed.
- **Re-ingest is needed for stored flags.** Old records fall back to computing
  gates from `text` and `review_rating`, which is slower but correct.
- **One classifier call per candidate.** With a large candidate pool, raise
  `--max-classify` only after checking the cost.
- **Keep rating filtering in code for now.** A Pinecone filter such as
  `{"review_rating": {"$lte": 3}}` is valid; filtering in
  `candidate_matches()` keeps the gate behavior explicit and testable.

---

## 9. What not to change

- Do not weaken `NO_SIGNAL`. `query_lead.py` detects refusal with
  `pitch.startswith(NO_SIGNAL)`, and the prompt instructs the model to return
  that exact string.
- Do not remove the quote requirement. It is the guardrail against invented
  complaints.
- Do not enable `--candidates-only` while the anti-pain pitch is still under
  consideration.
