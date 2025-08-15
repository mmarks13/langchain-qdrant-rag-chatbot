---
title: LangChain Qdrant RAG Chatbot
emoji: 🧠
colorFrom: yellow
colorTo: blue
sdk: docker
pinned: false
license: mit
---

# LangChain + Qdrant RAG Chatbot

A complete RAG (Retrieval-Augmented Generation) chatbot that crawls websites, builds a vector database, and provides cited answers through a clean chat interface.

## Features

- **🕷️ Web Crawling**: Uses Firecrawl to crawl websites and extract content
- **📚 Vector Database**: Qdrant for fast semantic search
- **🤖 LLM**: Hugging Face models for natural language responses
- **💬 Chat Interface**: Chainlit for a smooth chat experience
- **📝 Citations**: Every answer includes source references
- **☁️ Cloud Storage**: S3 for persistent database storage
- **🚀 Easy Deployment**: One-click deploy to Hugging Face Spaces

## Quick Start

### 1. Local Setup

```bash
# Clone and install
git clone your-repo-url
cd langchain-qdrant-rag-chatbot
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file:

```bash
# Required API Keys
FIRECRAWL_API_KEY=your_firecrawl_api_key
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token

# AWS S3 (for database storage)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-west-1
S3_BUCKET_NAME=your-s3-bucket-name
```

### 3. Configure Your Content

Edit `seeds.txt` with the URLs you want to crawl:
```
https://your-site.com/
https://docs.your-site.com/
```

### 4. Run Ingestion (Local)

```bash
# This crawls your sites and builds the vector database
python -m ingest.ingest --config config/config.yaml
```

### 5. Upload Database to S3

```bash
# Upload your database for cloud deployment
python ingest/upload_to_s3.py
```

### 6. Test Locally

```bash
# Run the chat interface locally
chainlit run app/main.py -w  --host 0.0.0.0 --port 8001
```

Visit http://localhost:8000 to test your chatbot.

## Hugging Face Spaces Deployment

### 1. Create a Space

1. Go to [Hugging Face Spaces](https://huggingface.co/new-space)
2. Choose **Docker** as the SDK
3. Create your space

### 2. Push Your Code

```bash
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME
git push space main --force
```

### 3. Configure Environment Variables

In your Space settings, add these **Secrets**:

```
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token
```

And these **Variables**:

```
S3_BUCKET_NAME=your-s3-bucket-name
AWS_DEFAULT_REGION=your-aws-region
```

### 4. Your Space is Live!

The Space will automatically:
- Download your database from S3
- Start the chat interface
- Serve your RAG chatbot at `https://huggingface.co/spaces/YOUR_USERNAME/YOUR_SPACE_NAME`

## Configuration

All settings are in `config/config.yaml`:

- **Crawling**: Adjust depth, page limits, and domains
- **Chunking**: Control how documents are split
- **Embeddings**: Choose embedding models
- **LLM**: Configure Hugging Face model settings
- **Retrieval**: Set how many documents to retrieve

## API Keys Required

1. **Firecrawl API**: Get from [firecrawl.dev](https://firecrawl.dev) - Used for web crawling
2. **Hugging Face Token**: Get from [HF Settings](https://huggingface.co/settings/tokens) - Used for LLM
3. **AWS Credentials**: For S3 database storage

## File Structure

```
├── app/
│   ├── main.py              # Chainlit chat interface
│   ├── rag.py               # RAG pipeline logic
│   └── config_utils.py      # Configuration loading
├── ingest/
│   ├── ingest.py            # Main ingestion script
│   ├── firecrawl_ingest.py  # Firecrawl integration
│   └── upload_to_s3.py      # S3 upload utility
├── config/
│   └── config.yaml          # Main configuration
├── prompts/
│   └── system_prompt.md     # RAG system prompt
├── seeds.txt                # URLs to crawl
├── start.sh                # Space startup script
└── requirements.txt        # Python dependencies
```

## Updating Your Data

To refresh your chatbot with new content:

```bash
# 1. Run ingestion locally (costs money via Firecrawl)
python -m ingest.ingest --config config/config.yaml

# 2. Upload updated database to S3
python ingest/upload_to_s3.py --force

# 3. Restart your Hugging Face Space
```

## Support

- **Firecrawl**: [Documentation](https://docs.firecrawl.dev/)
- **Qdrant**: [Documentation](https://qdrant.tech/documentation/)
- **Chainlit**: [Documentation](https://docs.chainlit.io/)
- **Hugging Face**: [Documentation](https://huggingface.co/docs)