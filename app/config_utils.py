import os, yaml
from dotenv import load_dotenv

def load_config(path: str):
    load_dotenv(override=True)
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    def env_bool(name, default):
        val = os.getenv(name)
        if val is None: return default
        return str(val).lower() in ("1","true","yes","on")

    def env_num(name, default, cast=float):
        val = os.getenv(name)
        if val is None: return default
        try:
            return cast(val)
        except Exception:
            return default

    def env(name, default):
        return os.getenv(name, str(default))

    # overlays
    ing = cfg.get("ingestion", {})
    ing["include_subdomains"] = env_bool("INGEST_INCLUDE_SUBDOMAINS", ing.get("include_subdomains", True))
    ing["max_depth"] = env_num("INGEST_MAX_DEPTH", ing.get("max_depth", 2), int)
    ing["page_limit"] = env_num("INGEST_PAGE_LIMIT", ing.get("page_limit", 500), int)
    ing["rate_limit_per_host_per_sec"] = env_num("INGEST_RATE_LIMIT", ing.get("rate_limit_per_host_per_sec", 2.0), float)
    ing["timeout_sec"] = env_num("INGEST_TIMEOUT", ing.get("timeout_sec", 15), int)
    ing["chunk_size"] = env_num("CHUNK_SIZE", ing.get("chunk_size", 1000), int)
    ing["chunk_overlap"] = env_num("CHUNK_OVERLAP", ing.get("chunk_overlap", 200), int)
    cfg["ingestion"] = ing

    vs = cfg.get("vectorstore", {})
    vs["provider"] = env("VECTORSTORE_PROVIDER", vs.get("provider", "qdrant_local"))
    vs["path"] = env("QDRANT_PATH", vs.get("path", "data/qdrant"))
    vs["url"] = os.getenv("QDRANT_URL", vs.get("url"))
    vs["api_key"] = os.getenv("QDRANT_API_KEY", vs.get("api_key"))
    vs["collection"] = env("QDRANT_COLLECTION", vs.get("collection", "rag_chunks"))
    vs["distance"] = env("QDRANT_DISTANCE", vs.get("distance", "cosine"))
    vs["batch_size"] = env_num("QDRANT_BATCH_SIZE", vs.get("batch_size", 64), int)
    cfg["vectorstore"] = vs

    em = cfg.get("embeddings", {})
    em["model"] = env("EMBED_MODEL", em.get("model", "BAAI/bge-small-en-v1.5"))
    em["normalize"] = env_bool("EMBED_NORMALIZE", em.get("normalize", True))
    cfg["embeddings"] = em

    llm = cfg.get("llm", {})
    llm["provider"] = env("LLM_PROVIDER", llm.get("provider", "groq"))
    llm["model"] = env("LLM_MODEL", llm.get("model", "llama-3.1-8b-instant"))
    llm["temperature"] = env_num("LLM_TEMPERATURE", llm.get("temperature", 0.2), float)
    llm["max_output_tokens"] = env_num("LLM_MAX_TOKENS", llm.get("max_output_tokens", 1024), int)
    cfg["llm"] = llm

    ret = cfg.get("retrieval", {})
    ret["k"] = env_num("RETRIEVAL_K", ret.get("k", 4), int)
    cfg["retrieval"] = ret

    return cfg
