# ingest/firecrawl_ingest.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

from langchain_core.documents import Document

# Firecrawl SDK (v2.16.5)
from firecrawl import FirecrawlApp, ScrapeOptions


def _ensure_api_key() -> str:
    load_dotenv(override=False)
    key = os.getenv("FIRECRAWL_API_KEY")
    if not key:
        raise RuntimeError(
            "FIRECRAWL_API_KEY is not set. Add it to your .env or export it in your shell."
        )
    return key


def _read_seeds(seeds_file: str) -> list[str]:
    p = Path(seeds_file)
    if not p.exists():
        raise FileNotFoundError(f"Seeds file not found: {seeds_file}")
    seeds = [
        line.strip()
        for line in p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not seeds:
        raise ValueError(f"No seeds found in {seeds_file}")
    return seeds


def crawl_firecrawl_sdk(cfg: Dict[str, Any]) -> List[Document]:
    """
    Crawl sites using Firecrawl Cloud via the official SDK (sync mode).
    Returns a list of LangChain `Document`s with markdown content + metadata.
    """
    api_key = _ensure_api_key()
    app = FirecrawlApp(api_key=api_key)

    ing = cfg.get("ingestion", {})
    print(ing)
    seeds_file = ing.get("seeds_file", "seeds.txt")
    include_subdomains = bool(ing.get("include_subdomains", True))
    max_depth = int(ing.get("max_depth", 2))
    page_limit = int(ing.get("page_limit", 500))

    # derive delay from your per-host rate
    rate = float(ing.get("rate_limit_per_host_per_sec", 2.0))
    delay_sec = (1.0 / rate) if rate > 0 else None

    # Firecrawl expects an **integer** number of seconds.
    # Only pass delay if it's >= 1s; else omit (sub-second intervals unsupported).
    delay_param = int(delay_sec) if (delay_sec is not None and delay_sec >= 1.0) else None

    # Firecrawl scrape timeout is in milliseconds
    timeout_ms = int(float(ing.get("timeout_sec", 15)) * 1000)

    seeds = _read_seeds(seeds_file)

    # ScrapeOptions live inside crawler options for each page
    scrape_opts = ScrapeOptions(
        formats=["markdown"],   # lean output for RAG
        timeout=timeout_ms,     # ms
        # parse_pdf=True,       # default is true; uncomment to be explicit
        # only_main_content=True
    )
    kwargs = dict(
        limit=page_limit,
        max_depth=max_depth,
        allow_subdomains=include_subdomains,
        scrape_options=scrape_opts,
    )

    if delay_param is not None:
        kwargs["delay"] = delay_param  # integer seconds
    print(kwargs)
    all_docs: List[Document] = []

    for seed in seeds:
        # SDK v2.16.5: supply crawler options as keyword args (NO "params" dict).
        # Supported keys include: limit, max_depth, allow_subdomains, delay, scrape_options, …
        # (Ref: Firecrawl docs: Crawl options)
        result = app.crawl_url(seed, **kwargs)

        # result is a CrawlStatusResponse (pydantic model) in v2.x
        data = getattr(result, "data", None)
        if data is None and isinstance(result, dict):
            data = result.get("data", [])
        if data is None:
            data = []

        for item in data:
            # item is FirecrawlDocument (pydantic) in v2.x
            if hasattr(item, "markdown"):
                md = item.markdown or ""
                meta = dict(item.metadata or {})
            else:
                # fallback if ever dict-shaped
                md = (item or {}).get("markdown", "") or ""
                meta = dict((item or {}).get("metadata", {}) or {})

            src = meta.get("sourceURL") or meta.get("url") or seed
            title = meta.get("title") or src
            if not md.strip():
                continue

            all_docs.append(
                Document(
                    page_content=md,
                    metadata={
                        "source": src,
                        "title": title,
                        "seed": seed,
                        "firecrawl": True,
                    },
                )
            )

    return all_docs
