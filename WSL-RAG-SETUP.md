# Running the RAG Project in WSL

**Scope:** this document is for the **RAG-powered LA Restaurant** project only.
This repo is Python-only — there is **no `package.json` here and no `npm install` step**.
(The NVRS frontend is a separate project; do not run its tooling in this folder.)

**What you need:** WSL2 + Ubuntu, Python 3.10–3.12 (3.14 works but some wheels lag),
Git, and API keys for the five services.

---

## Quick path (copy-paste)

```bash
# 1. System packages (once)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ca-certificates curl

# 2. Go to the repo (adjust the path if you cloned elsewhere)
cd ~/projects/rag-lead-generation

# 3. Create and activate a Linux virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt

# 5. Configure keys
cp .env.example .env
chmod 600 .env
nano .env

# 6. Offline sanity test (no keys needed, no credits spent)
pytest -q
python fetch_places.py --mock
python query_lead.py --mock
```

Expected: `39 passed`, three mock restaurants, one real pitch and two
`No relevant pain points found.` refusals.

---

## 1. Confirm you are in WSL2

From **PowerShell** (Windows side):

```powershell
wsl -l -v
```

You want `VERSION 2`. If you only have WSL1, upgrade:

```powershell
wsl --set-default-version 2
```

Inside WSL, confirm you are on Linux and not accidentally using a Windows Python:

```bash
uname -a                 # should say Linux ... microsoft-standard-WSL2
which python3            # MUST be /usr/bin/python3, not /mnt/c/...
python3 --version
```

If `which python3` points into `/mnt/c/...`, install the Linux Python from step 2 and
use `/usr/bin/python3` explicitly.

---

## 2. Install system packages

Ubuntu 22.04 / 24.04:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git ca-certificates curl
```

`python3-venv` is the one people forget; without it `python3 -m venv` fails with
`ensurepip is not available`.

Verify:

```bash
python3 --version
git --version
```

---

## 3. Put the repo on the Linux filesystem

Run it from your WSL home (`~/...`), **not** from `/mnt/c/...`. The Windows mount is
several times slower for `pip`, Git, and Python imports.

If the project is currently on the Windows side:

```bash
mkdir -p ~/projects
cp -r /mnt/c/Users/<You>/path/to/rag-lead-generation ~/projects/
cd ~/projects/rag-lead-generation
```

If it is already in WSL (e.g. `/home/alex/rag-la-restaurant/rag-lead-generation`), just:

```bash
cd /home/alex/rag-la-restaurant/rag-lead-generation
```

Avoid Windows line endings in the repo:

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

You should see the prompt prefix `(.venv)`. Re-activate it in every new shell:

```bash
cd ~/projects/rag-lead-generation
source .venv/bin/activate
```

> **Why a venv:** Ubuntu marks the system Python as externally managed; installing
> into it fails with `externally-managed-environment`. Never use `sudo pip`.

---

## 5. Configure API keys

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Fill in:

| Variable | Where to get it | Notes |
|---|---|---|
| `HUGGINGFACE_API_TOKEN` | huggingface.co → Settings → Access Tokens | Needs Inference API access. Free tier can return `402` when depleted. |
| `PINECONE_API_KEY` | pinecone.io → API Keys | Free serverless tier, AWS `us-east-1`. |
| `PINECONE_INDEX_NAME` | leave as `rag-lead-idx` | `setup_pinecone.py` creates it at **384** dims. |
| `PINECONE_NAMESPACE` | leave as `restaurants` | Must match between ingest and query. |
| `GOOGLE_PLACES_API_KEY` | Google Cloud Console | Enable **Places API (New)** and billing on the project. |
| `HASDATA_API_KEY` | hasdata.com dashboard | **10 credits per review call**; 1,000 free/month. |
| `DEEPSEEK_API_KEY` | platform.deepseek.com | OpenAI-compatible; no separate SDK needed. |
| `RAG_MODE` | `auto` | `auto` falls back to mock if a required key is missing. |

Never commit `.env` (it is already in `.gitignore`).

---

## 6. Offline sanity test — no keys, no credits

This proves the code, environment, and tests are healthy:

```bash
pytest -q
```

Expected: `39 passed`.

```bash
python fetch_places.py --mock
```

Expected: `Found 3 restaurant(s)` — Verde Kitchen, Celiac & Co., Taylor's Steak House.

```bash
python query_lead.py --mock
```

Expected:

- Verde Kitchen gets a pitch.
- Celiac & Co. gets `No relevant pain points found.` (praise about gluten-free food is
  not a complaint).
- Taylor's Steak House gets `No relevant pain points found.`

```bash
python fetch_data.py --mock
```

Expected: `Total records in index: 7` and `Dimension: 384 (expected 384)`.

If all four pass, the environment is correct and you have not spent anything.

---

## 7. Live sanity test — uses keys, spends credits

Run these in order. Do **not** skip the dry run.

```bash
# 7a. Create or verify the Pinecone index. Safe: never deletes.
python setup_pinecone.py
```

Expected: `Dimension: 384 ... Status: created` or `already existed`.
If it says the index has dimension 768, **stop** and read the message. Only
`--recreate --yes` is destructive.

```bash
# 7b. One Places call, no HasData spend.
python fetch_places.py --max-results 3
```

Expected: up to 3 restaurants with IDs, addresses, ratings, and price levels.
A `400` here usually means the API is not enabled, billing is off, or the key is restricted.

```bash
# 7c. Preview the ingest plan. Spends nothing.
python ingest_data.py --max-restaurants 2 --dry-run
```

Expected: 2 restaurants, `~20 HasData credits`, and `Dry run: no credits spent`.

```bash
# 7d. Ingest 2 restaurants. This SPENDS ~20 credits.
python ingest_data.py --max-restaurants 2 --yes
```

Expected per restaurant: `N reviews -> N vectors upserted`. This also calls
Hugging Face for embeddings; a `402` means the HF inference credits are exhausted.

```bash
# 7e. Verify the index.
python fetch_data.py
```

Expected: `Total records in index:` greater than 0, `Dimension: 384`, namespace
`restaurants`.

```bash
# 7f. Query without the LLM first (cheaper, easier to debug).
python query_lead.py --no-llm
```

Expected: retrieved review evidence grouped by restaurant.

```bash
# 7g. Full query with DeepSeek pitches.
python query_lead.py
```

Expected: one pitch per top restaurant, or `No relevant pain points found.`

**Budget reminder:** 2 restaurants ≈ 20 credits. The free HasData tier is
1,000 credits/month ≈ 100 review calls. Test on 2–5 restaurants before scaling.

---

## 8. Troubleshooting

| Symptom | Fix |
|---|---|
| `externally-managed-environment` | You are not in the venv. `source .venv/bin/activate`. |
| `No module named venv` / `ensurepip is not available` | `sudo apt install python3-venv` |
| `No module named rag_leads` | Run scripts from the repo root (`cd` to the folder containing `ingest_data.py`). |
| `which python3` shows `/mnt/c/...` | Use `/usr/bin/python3` to create the venv, or install Linux Python. |
| SSL / certificate errors | `sudo apt install -y ca-certificates`; check `date` (WSL clock can drift). |
| `certificate is not yet valid` / clock skew | From PowerShell: `wsl --shutdown`, reopen; or `sudo hwclock -s`. |
| DNS / cannot resolve `api.deepseek.com` | `curl -I https://api.deepseek.com`; restart WSL; check VPN/proxy. |
| `401` Pinecone | Wrong/expired `PINECONE_API_KEY`. |
| `402` Hugging Face | Inference credits exhausted; top up or switch mode to mock. |
| `403` Google Places | Places API (New) not enabled, billing off, or key restricted. |
| `400` Google Places | Rectangle must be `low`/`high` lat/lng; circles are rejected. |
| `429` from a provider | Temporary; the client retries with backoff. Reduce `--max-restaurants`. |
| Very slow installs | The repo is on `/mnt/c`; move it to `~/projects`. |
| `ModuleNotFoundError: pinecone` | `pip install -r requirements.txt` inside the venv. |

Logs: run with `python -u ...` if output appears buffered.

---

## 9. Daily commands

```bash
cd ~/projects/rag-lead-generation
source .venv/bin/activate

# tests
pytest -q

# offline demo
python query_lead.py --mock

# safe discovery preview
python fetch_places.py --max-results 5

# ingest (dry run first!)
python ingest_data.py --max-restaurants 5 --dry-run
python ingest_data.py --max-restaurants 5 --yes

# inspect and query
python fetch_data.py
python query_lead.py --no-llm
python query_lead.py
```

---

## 10. Guardrails

- **Never commit `.env`.** Keys stay local.
- **Never run `setup_pinecone.py --recreate`** unless you intend to delete the index.
- **Always `--dry-run` before `--yes`.** Every HasData call costs 10 credits.
- **Do not add Gemini.** Embeddings are Hugging Face `all-MiniLM-L6-v2` (384 dims);
  generation is DeepSeek `deepseek-chat`.
- **Run from the repo root** so `.env` and the `rag_leads` package resolve.
