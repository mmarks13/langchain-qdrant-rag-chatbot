from typing import List, Tuple
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.documents import Document

from langchain_groq import ChatGroq
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

from pathlib import Path
import os, textwrap

def build_embeddings(model_name: str, normalize: bool = True):
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": normalize},
    )

def _distance(dist: str):
    m = (dist or "cosine").lower()
    if m == "cosine":
        return Distance.COSINE
    if m in ("dot", "ip", "inner"):
        return Distance.DOT
    return Distance.EUCLID

def get_qdrant_client(vs_cfg: dict) -> QdrantClient:
    provider = (vs_cfg.get("provider") or "qdrant_local").lower()
    if provider == "qdrant_server" and vs_cfg.get("url"):
        return QdrantClient(url=vs_cfg["url"], api_key=vs_cfg.get("api_key"))
    # Local embedded (persists to disk if path is provided)
    path = vs_cfg.get("path") or "data/qdrant"
    Path(path).mkdir(parents=True, exist_ok=True)
    # QdrantClient uses ":memory:" or a filesystem path for embedded mode
    return QdrantClient(path=path)

def ensure_collection(client: QdrantClient, collection: str, vector_size: int, distance: str):
    try:
        collections = client.get_collections()
        names = [c.name for c in collections.collections]
        if collection in names:
            return
    except Exception:
        pass
    client.recreate_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=_distance(distance)),
    )

def qdrant_store(client: QdrantClient, collection: str, embeddings) -> QdrantVectorStore:
    return QdrantVectorStore(
        client=client,
        collection_name=collection,
        embedding=embeddings,
    )

def build_llm(llm_cfg: dict):
    provider = (llm_cfg.get("provider") or "groq").lower()
    model = llm_cfg.get("model") or "llama-3.1-8b-instant"
    temperature = float(llm_cfg.get("temperature", 0.2))
    max_tokens = int(llm_cfg.get("max_output_tokens", 1024))

    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEndpoint
        endpoint = HuggingFaceEndpoint(
            repo_id=model,               # <- use the same LLM_MODEL value
            task="text-generation",
            max_new_tokens=max_tokens,
            temperature=temperature,
        )
        from langchain_huggingface import ChatHuggingFace
        return ChatHuggingFace(llm=endpoint)

    from langchain_groq import ChatGroq
    return ChatGroq(model=model, temperature=temperature, max_tokens=max_tokens)

def format_docs_for_context(docs: List[Document]) -> Tuple[str, str]:
    """Return (context_text, references_md) with visible, clickable sources."""
    context_lines = []
    refs = ["**Sources**"]
    for i, d in enumerate(docs):
        url = d.metadata.get("source") or d.metadata.get("url") or ""
        title = d.metadata.get("title") or (url if url else f"Doc {i+1}")
        snippet = d.page_content.strip().replace("\n", " ")
        if len(snippet) > 800:
            snippet = snippet[:800] + "..."
        # Show numbered context blocks for the LLM to cite
        context_lines.append(f"[{i+1}] {title}\nURL: {url}\n---\n{snippet}")
        # Show human-friendly visible sources list
        if url:
            refs.append(f"{i+1}. [{title}]({url})")
        else:
            refs.append(f"{i+1}. {title}")
    return "\n\n".join(context_lines), "\n".join(refs)


def build_rag_chain(embeddings, vector_store: QdrantVectorStore, system_prompt: str, k: int = 4):
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {question}\n\nCONTEXT:\n{context}\n\nReturn a concise answer with citations as footnotes [1], [2] ..."),
    ])

    retriever = vector_store.as_retriever(search_kwargs={"k": k})

    def _prepare_inputs(x):
        docs = retriever.invoke(x["question"])  # List[Document]
        context, refs = format_docs_for_context(docs)
        return {"question": x["question"], "context": context, "_refs": refs}

    chain = (
        RunnableParallel(question=RunnablePassthrough())
        | _prepare_inputs
        | (prompt | RunnablePassthrough.assign() )
    )
    # The prompt returns a dict with prompt + _refs; pipe through LLM and then append refs.
    def _call_llm(d):
        llm = d.get("_llm")  # injected later
        msg = d["__root__"] if "__root__" in d else d  # support LCEL compose
        out = llm.invoke(msg)
        return str(out.content) + "\n\n" + d.get("_refs", "")

    # We return a function to be bound with an LLM later
    return chain, retriever
