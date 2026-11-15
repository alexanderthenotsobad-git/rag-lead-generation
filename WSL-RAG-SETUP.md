# Running the RAG Project in WSL

**Scope:** the **RAG-powered LA Restaurant** project only. This repo is
Python-only — there is no `package.json` and no `npm install` step. (The NVRS
frontend is a separate project.)

The pipeline is **live-only**. It calls Google Places, HasData, Hugging Face,
Pinecone, and DeepSeek. If a required key is missing, configuration fails
closed; there is no offline fallback.

---

## Quick path

```bash
# 1. System packages (once)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ca-certificates curl

# 2. Go to the repo (adjust the path if you cloned elsewhere)
cd ~/rag-la-restaurant/rag-lead-generation

# 3. Create and activate a Linux virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# 5. Configure live keys
cp .env.example .env
chmod 600 .env
nano .env

# 6. Verify configuration and run the unit tests
python -c "from rag_leads.config import load_settings; load_settings(required=['pinecone','places','hasdata','embeddings','llm']); print('config ok')"
pytest -q
```

---

## 1. Confirm you are in WSL2

From **PowerShell** (Windows side):

```powershell
wsl -l -v
```

You want `VERSION 2`.

Inside WSL:

```bash
uname -a                 # Linux ... microsoft-standard-WSL2
which python3            # MUST be /usr/bin/python3, not /mnt/c/...
python3 --version
```

If `which python3` points into `/mnt/c/...`, install the Linux Python from step 2
and use `/usr/bin/python3` explicitly.

---

## 2. Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ca-certificates curl
```

`python3-venv` is required; without it `python3 -m venv` fails with
`ensurepip is not available`.

---

## 3. Put the repo on the Linux filesystem

Run it from `~/...`, not `/mnt/c/...`. The Windows mount is several times slower
for `pip`, Git, and Python imports.

```bash
mkdir -p ~/projects
cp -r /mnt/c/Users/<You>/path/to/rag-lead-generation ~/projects/
cd ~/projects/rag-lead-generation
```

If the project is already in WSL:

```bash
cd /home/alex/rag-la-restaurant/rag-lead-generation
```

Avoid Windows line endings:

```bash
git config --global core.autocrlf false
```

---

## 4. Create the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```

Re-activate in every new shell:

```bash
cd ~/rag-la-restaurant/rag-lead-generation
source .venv/bin/activate
```

Never use `sudo pip`; Ubuntu marks the system Python as externally managed.

---

## 5. Configure live API keys

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

| Variable | Where to get it | Notes |
|---|---|---|
| `HUGGINGFACE_API_TOKEN` | huggingface.co → Settings → Access Tokens | Inference API access; `402` means credits exhausted |
| `PINECONE_API_KEY` | pinecone.io → API Keys | Free serverless tier, AWS `us-east-1` |
| `PINECONE_INDEX_NAME` | leave as `rag-lead-idx` | `setup_pinecone.py` creates it at **384** dims |
| `PINECONE_NAMESPACE` | leave as `restaurants` | Change it to isolate an area run |
| `GOOGLE_PLACES_API_KEY` | Google Cloud Console | Enable **Places API (New)** and billing |
| `HASDATA_API_KEY` | hasdata.com dashboard | **10 credits per review call**; 1,000 free/month |
| `DEEPSEEK_API_KEY` | platform.deepseek.com | OpenAI-compatible |

Never commit `.env`.

---

## 6. Verify fail-closed configuration

```bash
python -c "from rag_leads.config import load_settings; load_settings(required=['pinecone','places','hasdata','embeddings','llm']); print('config ok')"
```

Expected: `config ok`.

Missing keys raise a configuration error before any API call.

Run the unit tests:

```bash
pytest -q
```

These tests do not call external APIs.

---

## 7. Live sanity test — spends credits

Run in order. Do **not** skip the dry run.

```bash
# 7a. Create or verify the Pinecone index. Safe: never deletes.
python setup_pinecone.py
```

Expected: `Dimension: 384 ... Status: created` or `already existed`.
A 768-dim index must not be reused; the script refuses to delete it
automatically.

```bash
# 7b. One Places call, no HasData spend.
python fetch_places.py --max-results 3
```

Expected: up to 3 restaurants with IDs, addresses, ratings, and price levels.
A `403` usually means the API is not enabled, billing is off, or the key is
restricted.

```bash
# 7c. Preview the ingest plan. Spends nothing.
python ingest_data.py --max-restaurants 2 --dry-run
```

Expected: 2 restaurants, `~20 HasData credits`, and `Dry run: no credits spent`.

```bash
# 7d. Ingest 2 restaurants. This SPENDS ~20 credits.
python ingest_data.py --max-restaurants 2 --yes
```

Expected per restaurant: `N reviews -> N vectors upserted`. A `402` from
Hugging Face means inference credits are exhausted.

```bash
# 7e. Verify the index.
python fetch_data.py
```

Expected: `Total records in index:` greater than 0, `Dimension: 384`, and
namespace `restaurants`.

```bash
# 7f. Query without the LLM first.
python query_lead.py --no-llm
```

Expected: retrieved review evidence grouped by restaurant, plus candidate counts.

```bash
# 7g. Full query with classification and pitches.
python query_lead.py --top-k 50 --restaurants 5 --max-classify 5
```

Expected: one pitch per restaurant with a complaint, or
`No relevant pain points found.`

**Budget reminder:** 2 restaurants ≈ 20 credits. The free HasData tier is
1,000 credits/month ≈ 100 review calls. Test on 2–5 restaurants before scaling.

---

## 8. Santa Monica / beach run

Use a dedicated namespace so the area does not mix with central LA:

```bash
export PINECONE_NAMESPACE=santa-monica

python fetch_places.py --area santa-monica --max-results 20 \
  --text-query "healthy restaurant"

python ingest_data.py --area santa-monica --max-restaurants 10 \
  --text-query "healthy restaurant" --dry-run

python ingest_data.py --area santa-monica --max-restaurants 10 \
  --text-query "healthy restaurant" --yes

python query_lead.py --top-k 50 --restaurants 5 --max-classify 5

unset PINECONE_NAMESPACE
```

`query_lead.py` has no geographic filter; the namespace is what isolates the
area. `--area` changes only the discovery rectangle.

---

## 9. Save results

```bash
mkdir -p results
STAMP=$(date +%Y%m%d_%H%M%S)

python query_lead.py --top-k 50 --restaurants 5 --max-classify 5 \
  2> "results/query_${STAMP}.err" \
  | tee "results/query_${STAMP}.log"

python query_lead.py --top-k 50 --restaurants 5 --max-classify 5 --json \
  2> "results/query_${STAMP}.json.err" \
  | awk 'BEGIN{p=0} /^\[/{p=1} p' \
  > "results/query_${STAMP}.json"
```

View:

```bash
ls -lt results | head
less results/query_*.log
jq '.[] | {name, candidate_count, complaints: (.complaint_reviews | length), pitch}' results/query_*.json
```

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `externally-managed-environment` | You are not in the venv. `source .venv/bin/activate`. |
| `No module named venv` / `ensurepip is not available` | `sudo apt install python3-venv` |
| `No module named rag_leads` | Run from the repo root. |
| `which python3` shows `/mnt/c/...` | Use `/usr/bin/python3` to create the venv. |
| SSL / certificate errors | `sudo apt install -y ca-certificates`; check `date`. |
| Clock skew / `certificate is not yet valid` | From PowerShell: `wsl --shutdown`; or `sudo hwclock -s`. |
| DNS failures | `curl -I https://api.deepseek.com`; restart WSL; check VPN/proxy. |
| `401` Pinecone | Wrong or expired key. |
| `402` Hugging Face | Inference credits exhausted; top up. |
| `403` Google Places | Places API (New) not enabled, billing off, or IP restriction. |
| `400` Google Places | Rectangle must have `low`/`high`; circles are rejected. |
| `429` from a provider | Backoff is built in; reduce `--max-restaurants`. |
| Slow installs | Repo is on `/mnt/c`; move it to `~/projects`. |
| `missing required keys` | Fill `.env`; the pipeline fails closed by design. |

---

## 11. Guardrails

- **Never commit `.env`.**
- **Never run `setup_pinecone.py --recreate`** unless you intend to delete the index.
- **Always `--dry-run` before `--yes`.** Every HasData call costs 10 credits.
- **Do not add Gemini.** Embeddings are `all-MiniLM-L6-v2` (384 dims);
  generation is `deepseek-chat`.
- **Run from the repo root** so `.env` and `rag_leads` resolve.
