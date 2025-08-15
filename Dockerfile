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

# Create Chainlit directories in /tmp and link them to /app
# This must be done during build when we have write permissions
RUN mkdir -p /tmp/.files /tmp/.chainlit && \
    ln -s /tmp/.files /app/.files && \
    ln -s /tmp/.chainlit /app/.chainlit && \
    chmod 755 /tmp/.files /tmp/.chainlit

# Chainlit reads .env if present, but on Spaces use Secrets/Variables UI.
ENV QDRANT_PATH=/tmp/qdrant
ENV PORT=7860

EXPOSE 7860
CMD ["/app/start.sh"]