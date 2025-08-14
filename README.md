---
title: LangChain + Qdrant RAG Chatbot (Chainlit)
emoji: 🧠
colorFrom: yellow
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# LangChain + Qdrant RAG Chatbot

A self‑contained, open‑source RAG chatbot with:

- **LangChain** + **Chainlit** UI (fast chat UX)
- **Qdrant (embedded local mode)** as the vector DB (scales later to server or cloud)
- **Crawler/ingestor** that follows same‑domain links up to a configurable depth and parses **HTML + PDFs**
- **Embeddings:** `BAAI/bge-small-en-v1.5` by default (CPU‑friendly)
- **LLM:** Groq `llama-3.1-8b-instant` by default; optional Hugging Face serverless inference fallback
- **Citations** on every answer
- Deployable **free** on Hugging Face Spaces (CPU)

> **Quick Start (Local)**
>
> ```bash
> python -m venv .venv && source .venv/bin/activate  # (on Windows: .venv\Scripts\activate)
> pip install -r requirements.txt
> cp .env.example .env
> # Add your GROQ_API_KEY to .env
>
> # 1) Ingest your corpus (edit seeds.txt first)
> python ingest/ingest.py --config config/config.yaml
>
> # 2) Run the chat app
> chainlit run app/app.py -w
> ```
>
> Then open http://localhost:8000

## Hugging Face Spaces (Free CPU)

1. Create a new Space and choose **Docker** as the SDK.  
2. Push this repo to the Space.  
3. In **Settings → Repository secrets**, add `GROQ_API_KEY`.  
4. The app will start automatically on port 7860.

If your source sites block crawlers, run ingestion **locally** and push the `data/qdrant` folder.

## Configuration

All knobs are in `config/config.yaml` or `.env` env vars.

- Crawl depth, page cap, subdomains
- Embedding model
- LLM provider/model (Groq or Hugging Face serverless)
- Retrieval `k`
- Qdrant local path / collection name

---

## Files

- `app/app.py` — Chainlit app
- `ingest/ingest.py` — crawler + parser + chunk + embed + upsert
- `prompts/system_prompt.md` — RAG system prompt
- `config/config.yaml` — main config (also overridable via env)
- `seeds.txt` — seed URLs (one per line)
- `Dockerfile` — for HF Spaces or any Docker host
- `.env.example` — sample env vars
- `requirements.txt`
- `LICENSE` (MIT)

## Notes

- Qdrant runs **embedded** via the Python client (`QdrantClient(path='data/qdrant')`). Switch to a server or Qdrant Cloud by changing `QDRANT_URL`/`QDRANT_API_KEY` later.
- Embedding vectors default to 384‑dim (bge‑small‑en‑v1.5). If you change the embedding model, a new collection will be created automatically.
