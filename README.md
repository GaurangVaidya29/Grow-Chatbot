# Groww Mutual Fund FAQ Assistant

A facts-only RAG prototype for answering factual questions about a small, approved set of HDFC mutual fund pages. The product does not provide investment advice.

## Current status

Phases 1 through 8 are implemented: project structure, exact-five-page scraping, trusted document loading, structure-aware chunking, MiniLM embeddings, persistent ChromaDB indexing, guarded retrieval/answer logic, and the Stitch export browser UI.

## Prerequisites

- Python 3.11 or 3.12 is recommended for broad compatibility with the planned ML dependencies.
- A virtual environment.

On managed Windows devices, Application Control may block native ML DLLs inside a OneDrive-hosted virtual environment. Use an organization-approved Python environment outside the synced workspace; do not bypass the device policy.

## Setup

```text
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-local.txt
copy .env.example .env
```

Add a valid `GROQ_API_KEY` to `.env` to enable factual answer generation. Groq is the only runtime LLM provider; without a valid key, factual generation fails closed with a service error. Never commit `.env`.

## Validate Phase 1

```text
python ingest.py --stage config
pytest
```

Expected configuration output includes the embedding model, Chroma collection, and the number of verified data directories. Later stages currently exit with a clear “not implemented” message.

## Run Phase 2 scraping

```text
python ingest.py --stage scrape
```

The scraper requests only the five exact URLs in `config/sources.yaml`. It does not follow or request links found inside those pages. Raw HTML is written to `data/raw/`; cleaned, structured JSON is written to `data/extracted/`.

## Run loading, chunking, and indexing

```text
python ingest.py --stage load
python ingest.py --stage chunk
python ingest.py --stage index
```

The loading stage validates that all five documents match the trusted source registry. The chunk stage excludes performance/returns sections and writes deterministic JSONL chunks. The index stage uses `sentence-transformers/all-MiniLM-L6-v2` and activates a versioned ChromaDB collection only after count and sample-record validation pass.

## Run guarded retrieval

```text
python query.py --question "What is the expense ratio of HDFC Large Cap Fund Direct Growth?"
```

The pipeline checks sensitive data and restricted intents before embedding the question, resolves the scheme and requested fact, creates the query embedding locally with Hugging Face `sentence-transformers/all-MiniLM-L6-v2`, and filters ChromaDB results by scheme, fact type, trusted source, and score. Supported factual evidence is sent only to Groq for answer generation; every response contains one approved citation and its ingestion date, while unsupported or unsafe questions use deterministic templates without an LLM call.

## Preview the Stitch export UI

```text
python -m http.server 8088 --bind 127.0.0.1 --directory public
```

Open `http://127.0.0.1:8088/` to preview the layout. The static server does not provide `/api/query`; interactive factual answers require the Vercel API or a compatible local API. The active UI uses the supplied Stitch layout in `public/index.html` (also available at `public/stitch.html`) and the live API behavior in `public/stitch.js`. The page loads Tailwind from its CDN. The earlier `app/ui.py` is retained only as a legacy local prototype.

## Deploy on Vercel

Vercel serves `public/index.html` at `/` and uses the serverless handler in `api/query.py`. The exported read-only vector index contains the same 59 normalized MiniLM embeddings as the active local Chroma collection, while query embeddings are generated through Hugging Face Inference and factual answers through Groq.

Add these Environment Variables in Vercel for Production, Preview, and Development:

```text
LLM_PROVIDER=groq
LLM_MODEL=qwen/qwen3.8-27b
GROQ_API_KEY=<your Groq key>
HF_TOKEN=<your Hugging Face token with inference permission>
HF_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Use the following project settings:

```text
Framework Preset: Other
Root Directory: .
Build Command: leave empty
Output Directory: leave empty
Install Command: leave empty (Vercel installs requirements.txt)
Python: 3.12 (from .python-version)
```

After changing environment variables, redeploy. To refresh the deployed vector data after a new ingestion/index build, run `python scripts/export_vercel_index.py`, commit `data/vercel/index.json`, and redeploy.

## Product constraints

- Facts only; no investment advice.
- Only approved public sources.
- No recursive crawling.
- No collection or storage of PAN, Aadhaar, account numbers, OTPs, email addresses, or phone numbers.
- Every eventual response must include exactly one approved citation and no more than three sentences.

