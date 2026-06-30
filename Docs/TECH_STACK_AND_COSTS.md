# TaxBot — Technical Documentation & Deployment Cost Guide

> **A local-first, hybrid RAG-powered Tax Law AI chatbot** using an open-source LLM, Pinecone vector search, and a dual-server web architecture.

---

## 📐 System Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                          USER (Browser)                          │
└─────────────────────────────┬────────────────────────────────────┘
                              │
              ┌───────────────▼───────────────┐
              │    Streamlit Frontend          │  localhost:8501
              │    (app.py)                   │  (Python Web UI)
              └───────────────┬───────────────┘
                              │ REST API Call (/api/query)
              ┌───────────────▼───────────────┐
              │    FastAPI Backend             │  localhost:8000
              │    (main.py via Uvicorn)       │  (REST API Server)
              └───┬───────────────────────┬───┘
                  │                       │
   ┌──────────────▼───────────┐  ┌────────▼────────────────────┐
   │  Ollama (Local LLM)      │  │  Pinecone Serverless         │
   │  - llama3.1 (LLM)        │  │  (Cloud Vector Database)     │
   │  - nomic-embed-text      │  │  - 8,790+ chunk embeddings   │
   │    (Embeddings)          │  │  - Hybrid dense + BM25 index │
   │  runs on NVIDIA 4060 GPU │  │  - taxbot-hybrid-index       │
   └──────────────────────────┘  └─────────────────────────────┘
```

---

## 🧰 Full Tech Stack

### Frontend
| Component | Technology | Details |
|-----------|-----------|---------|
| UI Framework | **Streamlit** | Python-native web UI; runs on port 8501 |
| HTTP Client | **requests** | Communicates with FastAPI backend |
| Chat Interface | Streamlit Chat Elements | Persistent chat history via `session_state` |

### Backend
| Component | Technology | Details |
|-----------|-----------|---------|
| API Framework | **FastAPI** | High-performance async REST API |
| Server Runtime | **Uvicorn** | ASGI server; runs on port 8000 |
| Data Validation | **Pydantic** | Request/response schema validation |
| Environment Config | **python-dotenv** | Loads API keys from `.env` file |

### RAG (Retrieval-Augmented Generation) Engine
| Component | Technology | Details |
|-----------|-----------|---------|
| Search Strategy | **Hybrid RAG** | Combines semantic search + keyword search |
| Dense Embeddings | **nomic-embed-text** (via Ollama) | 768-dimension vector embeddings |
| Sparse Embeddings | **BM25Encoder** (pinecone-text) | Classic BM25 keyword relevance scoring |
| Hybrid Combination | **Alpha Weighting** | α=0.5 blending of dense + sparse scores |
| Vector Database | **Pinecone Serverless** | Cloud-hosted vector store (dotproduct metric) |
| Index Name | `taxbot-hybrid-index` | Stores 8,790+ document chunks |

### LLM (Language Model)
| Component | Technology | Details |
|-----------|-----------|---------|
| LLM Engine | **Ollama** | Local LLM runtime (no API cost) |
| Chat Model | **llama3.1** (8B) | Open-source Meta model, runs on GPU |
| Embedding Model | **nomic-embed-text** | Local sentence embedding model |
| GPU Acceleration | **NVIDIA GeForce RTX 4060** | CUDA-powered inference |

### Document Ingestion Pipeline
| Component | Technology | Details |
|-----------|-----------|---------|
| PDF Parser | **PyMuPDF (fitz)** | Fast page-by-page text extraction |
| PowerPoint Parser | **python-pptx** | Slide-by-slide text extraction |
| Subtitle Parser | **Custom VTT Parser** | Parses `.cc.vtt` WebVTT captions with timestamps |
| Video Extraction | **MoviePy** | Extracts audio from `.mp4` / `.mov` files |
| Chunking Strategy | **Overlapping windows** | 1000 chars/chunk, 200 char overlap |
| Parallel Ingestion | **ThreadPoolExecutor** (16 workers) | GPU-parallel embedding generation |

### Data Sources Ingested
| Document | Type | Chunks (Approx.) |
|----------|------|-----------------|
| Income Tax Act - 2025 Definitive Guide (322 MB) | PDF | ~5,200 |
| Income Tax Act 1961 (175 MB) | PDF | ~2,400 |
| Income Tax Amendment Rules 2026 | PDF | ~300 |
| The Income Tax Act 2025 14-02-26 | PDF | ~400 |
| DoppelgangerR1_R20 | PDF | ~80 |
| DoppelgangerR21_R51 | PDF | ~80 |
| File1_Sections1_9B | PDF | ~80 |
| File2_Sections10_10C | PDF | ~80 |
| Business Income v1 | PowerPoint (.pptx) | ~50 |
| GMT Recording Masterclass | WebVTT (.cc.vtt) | ~104 |
| **Total** | | **~8,790 chunks** |

---

## 💰 Deployment Cost Analysis

### Current Setup (Local / Development)

| Service | Cost | Notes |
|---------|------|-------|
| Ollama (LLM + Embeddings) | **$0.00/month** | Runs fully local on your PC |
| Pinecone Serverless | **$0.00–$5.00/month** | Included generous free tier; ~$0.0001 per query |
| Streamlit (Frontend) | **$0.00/month** | Runs locally on port 8501 |
| FastAPI (Backend) | **$0.00/month** | Runs locally on port 8000 |
| **Total (Local)** | **$0.00/month** | Only electricity cost |

---

### Deployment Option 1: 100% Free Serverless (Recommended for Minimal Cost)
*Switch from local Ollama to the **Gemini API Free Tier** for the LLM and embeddings.*

| Service | Provider | Free Tier Limit | Cost |
|---------|----------|----------------|------|
| LLM + Embeddings | **Google Gemini API** | 1,500 req/day, 15 req/min, 1.5M tokens/day | **$0.00/month** |
| Vector Database | **Pinecone Serverless** | 2GB storage, starter queries included | **$0.00/month** |
| Backend Hosting | **Render.com** | Free Web Service (sleeps after 15min idle) | **$0.00/month** |
| Frontend Hosting | **Streamlit Community Cloud** | Unlimited public apps | **$0.00/month** |
| **Total** | | | **$0.00/month** |

> **Limitation:** Gemini free tier has rate limits. For a CA firm with many simultaneous users, you may hit 15 requests/minute cap.

**Required `.env` change for cloud deployment:**
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIzaSy...your-key...
PINECONE_API_KEY=pcsk_...your-key...
```

---

### Deployment Option 2: Groq (Ultra-Fast, Free LLM API)
*Use **Groq's free tier** to run Llama 3.1 8B in the cloud at extremely high speeds.*

| Service | Provider | Free Tier | Cost |
|---------|----------|-----------|------|
| LLM | **Groq API** (llama-3.1-8b-instant) | 6,000 tokens/min free | **$0.00/month** |
| Embeddings | **Together AI / Gemini** | Free tier available | **$0.00/month** |
| Vector DB | **Pinecone Serverless** | Free starter | **$0.00/month** |
| Backend | **Render.com** | Free Web Service | **$0.00/month** |
| Frontend | **Streamlit Community Cloud** | Free | **$0.00/month** |
| **Total** | | | **$0.00/month** |

> **Advantage:** Groq runs at 200–300 tokens/second, much faster than local Ollama. No GPU required.

---

### Deployment Option 3: Modal.com (Keep Full Ollama Stack, Pay-Per-Second GPU)
*Host your exact local Ollama + Llama 3.1 + nomic-embed-text stack on a cloud GPU container.*

| Service | Provider | Details | Monthly Cost |
|---------|----------|---------|-------------|
| LLM + Embeddings (Ollama container) | **Modal.com** | A10G GPU, only billed during active requests | ~$0.00–$5.00 |
| Vector DB | **Pinecone Serverless** | Starter tier | $0.00 |
| Backend | **Modal.com** (FastAPI) | Serverless Python container | ~$0.00–$2.00 |
| Frontend | **Streamlit Community Cloud** | Free | $0.00 |
| **Total** | | | **$0.00–$7.00/month** |

> **Note:** Modal provides **$30 free GPU credits every month**. For light-to-medium usage, this is effectively free.

---

### Deployment Option 4: Dedicated VM (Best Performance, Some Cost)
*Run the entire local stack (Ollama + FastAPI + Streamlit) on a cloud virtual machine.*

| Service | Provider | Spec | Monthly Cost |
|---------|----------|------|-------------|
| GPU VM | **RunPod.io** or **Vast.ai** | RTX 3090 (24GB VRAM) | ~$15–30/month |
| Vector DB | **Pinecone Serverless** | Starter | $0.00 |
| Domain + SSL | **Cloudflare** | Free proxy + SSL | $0.00 |
| **Total** | | | **~$15–30/month** |

> **Best for:** A CA firm deploying this as a production-grade private internal tool.

---

## 📊 Cost Comparison Summary

| Option | Cost/Month | LLM Type | GPU Required | Production-Ready |
|--------|-----------|----------|-------------|-----------------|
| **Local Development** | $0 | Ollama (Local) | Your NVIDIA 4060 | ❌ (local only) |
| **Option 1: Gemini + Render** | $0 | Gemini Flash (Cloud) | ❌ No | ✅ Yes |
| **Option 2: Groq + Render** | $0 | Llama 3.1 (Cloud) | ❌ No | ✅ Yes |
| **Option 3: Modal.com** | $0–$7 | Ollama (Serverless GPU) | ✅ Cloud GPU | ✅ Yes |
| **Option 4: Dedicated GPU VM** | $15–30 | Ollama (Dedicated GPU) | ✅ Dedicated GPU | ✅ Best |

---

## 🚀 Recommended Deployment Path

1. **Start with Option 1** (Gemini API + Render + Streamlit Cloud) — zero cost, zero configuration, live in under 30 minutes.
2. **Monitor usage** — if you hit Gemini free tier limits (which only happens with heavy concurrent usage), upgrade to **Option 2** (Groq) which is also free but faster.
3. **Scale up** to **Option 3 or 4** only when the application is being used by 10+ CAs simultaneously.

---

## 📁 Repository Structure

```
TaxBot/
├── .gitignore             # Hides .env, venv, and data/ from git
├── .env                   # ⚠️ NOT committed — API keys stored here
│
├── backend/
│   ├── main.py            # FastAPI REST API server
│   ├── ingestion.py       # Data ingestion pipeline
│   ├── requirements.txt   # Python backend dependencies
│   ├── bm25_model.json    # ⚠️ NOT committed — locally trained BM25 model
│   └── data/              # ⚠️ NOT committed — local document corpus
│       ├── *.pdf          # Tax law PDF books (300MB+ each)
│       ├── *.pptx         # PowerPoint presentations
│       └── *.vtt          # WebVTT subtitle captions from video lectures
│
├── frontend/
│   ├── app.py             # Streamlit web UI
│   └── requirements.txt   # Python frontend dependencies
│
└── Docs/
    ├── TECH_STACK_AND_COSTS.md   # This document
    ├── TaxBot Test Q&A Responses.docx
    └── Taxbot Test Questions.txt
```

---

*Document last updated: June 30, 2026*
