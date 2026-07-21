# TaxBot Project Setup Guide

Welcome to the **TaxBot** project! This guide provides step-by-step instructions to set up the entire project (FastAPI Backend, SQLite/Supabase Database, Pinecone Hybrid Vector Store, and Next.js Frontend) locally on a completely new device.

---

## Prerequisites

Ensure you have the following installed on your new device:
- **Node.js** (v18.x or newer) & **npm** (v9.x or newer)
- **Python** (v3.10.x or newer)
- **Git**
- *(Optional)* **Ollama** (if running models locally)

---

## 1. Repository Structure Overview

```
TaxBot/
├── backend/               # FastAPI backend codebase
│   ├── data/              # Document directories
│   │   ├── pdf_data/      # Store PDF documents here
│   │   ├── pptx_data/     # Store PPTX/PPT presentations here
│   │   └── vtt_data/      # Store VTT video subtitles/transcripts here
│   ├── database.py        # Database integration handlers
│   ├── main.py            # FastAPI main server entry point
│   ├── ingestion.py       # Local hybrid ingestion pipeline script
│   └── requirements.txt   # Python packages
├── frontend-next/         # Next.js React frontend
│   ├── src/               # React source files
│   └── package.json       # Node dependency definition
└── .env                   # Global environment variables configuration file
```

---

## 2. Environment Variables Setup

Create a file named `.env` in the **root** of the `TaxBot` directory. Populate it with the following configuration variables:

```env
# Google Gemini API key for embeddings and text generation
GEMINI_API_KEY=your_gemini_api_key_here

# Pinecone API key for hybrid search indexing
PINECONE_API_KEY=your_pinecone_api_key_here

# Provider selection: 'gemini' (recommended) or 'ollama'
LLM_PROVIDER=gemini

# Local Ollama config (only needed if LLM_PROVIDER=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=llama3.1
OLLAMA_EMBED_MODEL=nomic-embed-text

# Supabase database config (If omitted, database will automatically fall back to local SQLite)
SUPABASE_URL=https://your_supabase_project_ref.supabase.co
SUPABASE_KEY=your_supabase_service_role_key_here
TAXBOT_JWT_SECRET=generate_a_long_random_string_for_auth

# Cost & RAG Controls
SUGGESTION_QUESTIONS=False
RAG_TOP_K=15
MAX_OUTPUT_TOKENS=2048
```

---

## 3. Database Setup (Supabase)

If you are using Supabase (recommended for production/sharing sessions), make sure the following tables exist in your Supabase project schema:

1. **`taxbot_users`**
   - Columns: `id` (UUID, primary key), `taxsutra_id` (Text), `email` (Text), `full_name` (Text), `plan` (Text).
2. **`taxbot_sessions`**
   - Columns: `id` (UUID, primary key), `title` (Text), `user_id` (UUID referencing `taxbot_users.id` on delete cascade), `created_at` (Timestamp).
3. **`taxbot_messages`**
   - Columns: `id` (UUID, primary key), `session_id` (UUID referencing `taxbot_sessions.id` on delete cascade), `role` (Text - 'user' or 'assistant'), `content` (Text), `source` (Text, nullable), `feedback` (Text, nullable), `created_at` (Timestamp).
4. **`ingested_documents`**
   - Columns: `filename` (Text, primary key/unique), `file_type` (Text), `size_mb` (Numeric), `chunk_count` (Integer), `ingested_at` (Timestamp).

*If you do not fill in `SUPABASE_URL` and `SUPABASE_KEY` in the `.env` file, the backend will automatically instantiate and run on a local SQLite database file `backend/taxbot.db`.*

---

## 4. Backend Setup & Ingestion

Open a terminal at the repository root folder (`TaxBot/`):

### 1. Create a Python Virtual Environment
```bash
python -m venv venv
```

### 2. Activate the Virtual Environment
- **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Windows (CMD):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```
- **macOS / Linux:**
  ```bash
  source venv/bin/activate
  ```

### 3. Install Python Dependencies
```bash
pip install -r backend/requirements.txt
```

### 4. Organize and Ingest Data
1. Place your target documents inside the respective folders under `backend/data/`:
   - PDFs in `backend/data/pdf_data/`
   - PPTX/PPT slides in `backend/data/pptx_data/`
   - Subtitle transcript files in `backend/data/vtt_data/`
2. Run the ingestion pipeline locally to chunk, embed, and index files into Pinecone (and log them into Supabase):
   ```bash
   python backend/ingestion.py
   ```

### 5. Run the Backend API Server
```bash
cd backend
uvicorn main:app --reload --port 8000
```
The API documentation is accessible at `http://127.0.0.1:8000/docs`.

---

## 5. Frontend Setup

Open a new terminal window/tab at the repository root folder (`TaxBot/`):

### 1. Navigate to the Frontend Directory
```bash
cd frontend-next
```

### 2. Install Node Packages
```bash
npm install
```

### 3. Start the Next.js Development Server
```bash
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) on your web browser to access the TaxBot app.
Access the administrative panel dashboard at [http://localhost:3000/admin](http://localhost:3000/admin) to manage/sort documents and view analytics.
