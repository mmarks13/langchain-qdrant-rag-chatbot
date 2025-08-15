import os, sys, asyncio
import chainlit as cl

from dotenv import load_dotenv
load_dotenv(override=True)


# Ensure repo root is importable when Chainlit runs this as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config_utils import load_config
from app.rag import (
    build_embeddings, get_qdrant_client, ensure_collection, qdrant_store,
    build_llm, build_rag_chain, format_docs_for_context
)
from langchain_core.prompts import ChatPromptTemplate
from pathlib import Path

# Use relative paths since we run from /app
CFG_PATH = os.getenv("APP_CONFIG", "config/config.yaml")

# ---- Single in-process resource cache (prevents embedded Qdrant lock) ----
_RESOURCE: dict = {}

def _init_resources():
    print("[init] 🔧 Initializing resources...")

    # Double-check environment loading
    hf_token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
    if hf_token:
        print(f"[init] ✅ HF Token loaded: {hf_token[:10]}...")
    else:
        print("[init] ❌ No HuggingFace token found!")

    cfg = load_config(CFG_PATH)
    print(f"[init] 📁 Config loaded from: {CFG_PATH}")

    # Embeddings (initialize once)
    print("[init] 🔤 Loading embeddings...")
    embeddings = build_embeddings(
        cfg["embeddings"]["model"],
        cfg["embeddings"].get("normalize", True)
    )

    # Qdrant embedded or server — initialize once
    print("[init] 🗄️  Connecting to Qdrant...")
    client = get_qdrant_client(cfg["vectorstore"])
    dim = len(embeddings.embed_query("probe"))
    ensure_collection(
        client,
        cfg["vectorstore"]["collection"],
        dim,
        cfg["vectorstore"].get("distance", "cosine")
    )
    store = qdrant_store(client, cfg["vectorstore"]["collection"], embeddings)

    # LLM and RAG chain
    print("[init] 🤖 Building LLM...")
    system_prompt = Path("prompts/system_prompt.md").read_text(encoding="utf-8")
    llm = build_llm(cfg["llm"])
    chain, retriever = build_rag_chain(embeddings, store, system_prompt, k=cfg["retrieval"]["k"])

    print("[init] ✅ All resources initialized successfully!")

    return {
        "cfg": cfg,
        "embeddings": embeddings,
        "client": client,
        "store": store,
        "llm": llm,
        "chain": chain,
        "retriever": retriever,
        "system_prompt": system_prompt,
    }

@cl.on_chat_start
async def start():
    print("[start] 🚀 Starting chat session...")

    # Reuse single resources per process (avoid multiple embedded clients)
    if not _RESOURCE:
        _RESOURCE.update(_init_resources())

    cfg = _RESOURCE["cfg"]
    model = cfg["llm"]["model"]
    await cl.Message(content=f"Loaded `{CFG_PATH}`\nUsing {cfg['llm']['provider']} → {model}").send()

    # Attach handles for this session
    for k in ("cfg","embeddings","store","llm","chain","retriever","system_prompt"):
        cl.user_session.set(k, _RESOURCE[k])

    await cl.Message(content="Ready. Ask me anything about your indexed docs.").send()

@cl.on_message
async def main(message: cl.Message):
    print(f"[message] 💬 Processing: {message.content[:50]}...")

    llm = cl.user_session.get("llm")
    retriever = cl.user_session.get("retriever")
    system_prompt = cl.user_session.get("system_prompt")

    if not (llm and retriever and system_prompt):
        await cl.Message(content="App not initialized.").send()
        return

    # Retrieve & build prompt
    print("[message] 🔍 Retrieving relevant documents...")
    docs = retriever.invoke(message.content)
    context, refs = format_docs_for_context(docs)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Question: {question}\n\nCONTEXT:\n{context}\n\nReturn a concise answer with in-text citations e.g. [1], [2] ..."),
    ])
    prompt_value = prompt.format(question=message.content, context=context)

    print("[message] 🤖 Generating response...")

    # Stream ONLY text, not the whole chunk object
    msg = cl.Message(content="")
    async def _stream():
        async for chunk in llm.astream(prompt_value):
            text = getattr(chunk, "content", None)
            if not text:
                text = getattr(chunk, "delta", None) or (chunk if isinstance(chunk, str) else "")
            if text:
                await msg.stream_token(text)

    try:
        await _stream()
    except Exception as e:
        await msg.stream_token(f"\n(Streaming error: {e})\n")
        resp = llm.invoke(prompt_value)
        await msg.stream_token(getattr(resp, "content", str(resp)))

    await msg.send()
    if refs:
        await cl.Message(content=f"\n\n{refs}").send()