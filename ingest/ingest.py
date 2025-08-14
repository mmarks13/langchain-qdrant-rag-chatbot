import os, re, time, argparse, hashlib
from urllib.parse import urljoin, urlparse
from collections import deque
from pathlib import Path
from typing import List

from ingest.firecrawl_ingest import crawl_firecrawl_sdk

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from dotenv import load_dotenv
from app.config_utils import load_config
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter




from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore

# -------------------------
# Helpers
# -------------------------

def sanitize_filename(url: str) -> str:
    import hashlib
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    parsed = urlparse(url)
    base = (parsed.netloc + parsed.path).replace("/","_")[:60]
    return f"{base}_{h}"

def is_same_domain(seed_netloc: str, target_netloc: str, include_subdomains: bool) -> bool:
    if include_subdomains:
        return target_netloc == seed_netloc or target_netloc.endswith("." + seed_netloc)
    return target_netloc == seed_netloc

def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script","style","noscript","header","footer","nav","form"]):
        tag.extract()
    text = soup.get_text("\n")
    text = re.sub(r"\n{2,}", "\n\n", text)
    return text.strip()

def fetch(session: requests.Session, url: str, timeout: int):
    r = session.get(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "RAGBot/1.0"})
    r.raise_for_status()
    return r

def _read_seeds(seeds_file: str) -> List[str]:
    return [s.strip()
            for s in Path(seeds_file).read_text(encoding="utf-8").splitlines()
            if s.strip() and not s.strip().startswith("#")]

# -------------------------
# Builtin crawler (no API required)
# -------------------------

def crawl_builtin(cfg: dict) -> List[Document]:
    ing = cfg["ingestion"]
    seeds = _read_seeds(ing.get("seeds_file", "seeds.txt"))

    include_subdomains = bool(ing.get("include_subdomains", True))
    max_depth = int(ing.get("max_depth", 2))
    page_limit = int(ing.get("page_limit", 500))
    timeout = int(ing.get("timeout_sec", 15))

    seen = set()
    docs: List[Document] = []
    q = deque()

    session = requests.Session()

    seed_netlocs = set(urlparse(s).netloc for s in seeds)
    for s in seeds:
        q.append((s, 0))

    pbar = tqdm(total=page_limit, desc="Crawling (builtin)", unit="page")

    while q and len(docs) < page_limit:
        url, depth = q.popleft()
        if url in seen or depth > max_depth:
            continue
        seen.add(url)

        try:
            r = fetch(session, url, timeout)
        except Exception:
            continue

        ctype = r.headers.get("Content-Type", "").split(";")[0].strip().lower()
        netloc = urlparse(url).netloc
        if not any(is_same_domain(seed, netloc, include_subdomains) for seed in seed_netlocs):
            continue

        if ctype == "text/html" or (ctype == "" and url.endswith(('.html','.htm','/'))):
            html = r.text
            text = extract_text_from_html(html)
            title = BeautifulSoup(html, "lxml").title.string.strip() if BeautifulSoup(html, "lxml").title else url
            docs.append(Document(page_content=text, metadata={"source": url, "title": title}))
            pbar.update(1)

            if depth < max_depth:
                soup = BeautifulSoup(html, "lxml")
                for a in soup.find_all("a", href=True):
                    link = urljoin(url, a["href"]).split("#")[0]
                    parsed = urlparse(link)
                    if parsed.scheme in ("http","https") and link not in seen:
                        q.append((link, depth+1))

        elif ctype == "application/pdf" or url.lower().endswith(".pdf"):
            raw_dir = Path("data/raw"); raw_dir.mkdir(parents=True, exist_ok=True)
            fn = raw_dir / f"{sanitize_filename(url)}.pdf"
            with open(fn, "wb") as f:
                f.write(r.content)
            try:
                loader = PyPDFLoader(str(fn))
                pdf_docs = loader.load()
                for d in pdf_docs:
                    d.metadata["source"] = url
                docs.extend(pdf_docs)
                pbar.update(1)
            except Exception:
                continue

        time.sleep(1.0 / max(float(ing.get("rate_limit_per_host_per_sec", 2.0)), 0.1))

    pbar.close()
    return docs

# -------------------------
# Firecrawl via LangChain
# -------------------------

def crawl_firecrawl(cfg: dict) -> List[Document]:
    """
    Use LangChain's FireCrawlLoader for each seed.
    Respects ingestion.mode ('crawl' | 'scrape'), include_subdomains, max_depth, page_limit, timeout_sec.
    """
    ing = cfg["ingestion"]
    seeds = _read_seeds(ing.get("seeds_file", "seeds.txt"))

    api_key = os.getenv("FIRECRAWL_API_KEY")  # loader can also read from env automatically
    mode = str(ing.get("mode", "crawl")).lower()  # 'crawl' or 'scrape'
    include_subdomains = bool(ing.get("include_subdomains", True))
    max_depth = int(ing.get("max_depth", 2))
    page_limit = int(ing.get("page_limit", 500))
    timeout_ms = int(ing.get("timeout_sec", 15)) * 1000

    all_docs: List[Document] = []

    for seed in seeds:
        params = {
            "limit": page_limit,
            "maxDepth": max_depth,
            "includeSubdomains": include_subdomains,
            "timeout": timeout_ms,
            "scrapeOptions": {
                "onlyMainContent": True,
                "formats": ["markdown"],
            },
        }

        loader = FireCrawlLoader(
            url=seed,
            api_key=api_key,   # optional; if None, it reads FIRECRAWL_API_KEY from env
            mode=mode,         # 'crawl' follows links; 'scrape' only this page
            params=params,
        )
        docs = loader.load()   # returns List[Document] with .metadata (title, sourceURL, etc.)
        # Normalize metadata keys we rely on
        for d in docs:
            src = d.metadata.get("sourceURL") or d.metadata.get("url") or d.metadata.get("source") or ""
            ttl = d.metadata.get("title") or src
            d.metadata["source"] = src
            d.metadata["title"] = ttl
        all_docs.extend(docs)

    return all_docs

# -------------------------
# Chunking & Upsert
# -------------------------

def chunk_docs(docs: List[Document], chunk_size: int, chunk_overlap: int) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=["\n\n","\n"," ",""]
    )
    return splitter.split_documents(docs)

def upsert(cfg: dict, docs: List[Document]):
    vs = cfg["vectorstore"]
    em_cfg = cfg["embeddings"]
    embeddings = HuggingFaceEmbeddings(
        model_name=em_cfg.get("model", "BAAI/bge-small-en-v1.5"),
        encode_kwargs={"normalize_embeddings": bool(em_cfg.get("normalize", True))},
    )

    dim = len(embeddings.embed_query("dimension test"))
    distance = (vs.get("distance") or "cosine").lower()
    dist_map = {"cosine": Distance.COSINE, "dot": Distance.DOT, "euclid": Distance.EUCLID}
    dist = dist_map.get(distance, Distance.COSINE)

    provider = (vs.get("provider") or "qdrant_local").lower()
    if provider == "qdrant_server" and vs.get("url"):
        client = QdrantClient(url=vs["url"], api_key=vs.get("api_key"))
    else:
        Path(vs.get("path","data/qdrant")).mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=vs.get("path","data/qdrant"))

    coll = vs.get("collection", "rag_chunks")

    # If you want to preserve existing data, change recreate_collection -> ensure/create if missing.
    try:
        client.recreate_collection(
            collection_name=coll,
            vectors_config=VectorParams(size=dim, distance=dist),
        )
    except Exception:
        pass

    store = QdrantVectorStore(client=client, collection_name=coll, embedding=embeddings)

    batch = int(vs.get("batch_size", 64))
    for i in range(0, len(docs), batch):
        store.add_documents(docs[i:i+batch])

# -------------------------
# Entry point
# -------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest URLs into Qdrant via LangChain.")
    parser.add_argument("--config", default="config/config.yaml", help="Path to config YAML")
    args = parser.parse_args()

    load_dotenv(override=True)
    cfg = load_config(args.config)

    provider = (cfg["ingestion"].get("provider") or os.getenv("INGEST_PROVIDER", "firecrawl")).lower()
    print(f"Ingestion provider: {provider}")
    if provider == "firecrawl":
        print("Ingestion provider: Firecrawl (SDK)")
        docs = crawl_firecrawl_sdk(cfg)
    else:
        print("Ingestion provider: builtin")
        docs = crawl_builtin(cfg)

    if not docs:
        print("No documents crawled. Check seeds or network access.")
        return

    ing = cfg["ingestion"]
    chunks = chunk_docs(docs, ing.get("chunk_size", 1000), ing.get("chunk_overlap", 200))
    print(f"Crawled {len(docs)} docs → {len(chunks)} chunks. Upserting...")

    upsert(cfg, chunks)
    print("Done.")

if __name__ == "__main__":
    main()
