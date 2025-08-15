# ---- Base
FROM python:3.12-slim

# ---- System deps (for lxml, PDFs, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev poppler-utils curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Python deps
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# ---- App
COPY . .
RUN chmod +x /app/start.sh

# Configure environment variables
ENV QDRANT_PATH=/tmp/qdrant
ENV PORT=7860
ENV CHAINLIT_APP_ROOT=/tmp
ENV HF_HOME=/tmp/.cache
ENV HUGGINGFACE_HUB_CACHE=/tmp/.cache/huggingface/hub
ENV TRANSFORMERS_CACHE=/tmp/.cache/huggingface/transformers

EXPOSE 7860
CMD ["/app/start.sh"]