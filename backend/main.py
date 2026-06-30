import os
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder

# Load environment variables
load_dotenv(dotenv_path="../.env")

app = FastAPI(title="Tax Open-Book Bot Backend")

class QueryRequest(BaseModel):
    question: str

# Configs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
INDEX_NAME = "taxbot-hybrid-index"
BM25_MODEL_PATH = "./bm25_model.json"

# Initialize global clients
pc = None
index = None
bm25 = None

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

if PINECONE_API_KEY:
    try:
        pc = Pinecone(api_key=PINECONE_API_KEY)
        if INDEX_NAME in pc.list_indexes().names():
            index = pc.Index(INDEX_NAME)
            print(f"Connected to Pinecone index: '{INDEX_NAME}'")
        else:
            print(f"[WARNING] Pinecone index '{INDEX_NAME}' not found. Run ingestion.py first.")
    except Exception as e:
        print(f"[WARNING] Pinecone connection error: {e}")

# Try to load BM25 encoder
if os.path.exists(BM25_MODEL_PATH):
    try:
        bm25 = BM25Encoder()
        bm25.load(BM25_MODEL_PATH)
        print("Loaded BM25 model successfully.")
    except Exception as e:
        print(f"[WARNING] Failed to load BM25 encoder: {e}")

# Helper: Dense Embedding
def get_dense_embedding(text: str) -> list[float]:
    if LLM_PROVIDER == "ollama":
        res = requests.post(f"{OLLAMA_BASE_URL}/api/embeddings", json={
            "model": OLLAMA_EMBED_MODEL,
            "prompt": text
        })
        res.raise_for_status()
        return res.json()["embedding"]
    else:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing in configuration.")
        res = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query"
        )
        return res["embedding"]

# Helper: Hybrid Score Combination
def perform_hybrid_query(query_text: str, alpha: float = 0.5, top_k: int = 5):
    """Executes a hybrid search query on Pinecone using dense and sparse vectors."""
    if not index:
        raise ValueError("Pinecone index connection is not available.")
    
    # 1. Dense Vector
    dense_vec = get_dense_embedding(query_text)
    
    # 2. Sparse Vector
    if not bm25:
        # Fallback to pure dense search if BM25 encoder isn't trained
        print("[WARNING] BM25 model not found. Defaulting to dense-only query.")
        return index.query(vector=dense_vec, top_k=top_k, include_metadata=True)
        
    sparse_vec = bm25.encode_queries(query_text)
    
    # Fallback to dense-only search if query sparse vector has no active indices/values (e.g. only stopwords)
    if not sparse_vec.get("indices") or not sparse_vec.get("values"):
        print("[WARNING] Sparse query vector is empty. Defaulting to dense-only query.")
        return index.query(vector=dense_vec, top_k=top_k, include_metadata=True)
    
    # Apply alpha weighting (linear combination)
    weighted_dense = [x * alpha for x in dense_vec]
    weighted_sparse = {
        "indices": sparse_vec["indices"],
        "values": [x * (1.0 - alpha) for x in sparse_vec["values"]]
    }
    
    # Perform Search
    return index.query(
        vector=weighted_dense,
        sparse_vector=weighted_sparse,
        top_k=top_k,
        include_metadata=True
    )

# Helper: Generation
def generate_grounded_response(question: str, context_chunks: list[dict]) -> dict:
    # Format context
    context_str = ""
    citations = []
    
    for i, match in enumerate(context_chunks):
        meta = match.get("metadata", {})
        text = meta.get("text", "")
        source = meta.get("source", "Unknown document")
        file_type = meta.get("file_type", "")
        
        # Format citation source tag
        if file_type == "pdf":
            citation = f"{source} (Page {meta.get('page', '?')})"
        elif file_type == "ppt":
            citation = f"{source} (Slide {meta.get('slide', '?')})"
        elif file_type == "video":
            citation = f"{source} (Timestamp {meta.get('timestamp', '00:00')})"
        else:
            citation = source
            
        citations.append(citation)
        context_str += f"\n--- Source [{i+1}]: {citation} ---\n{text}\n"

    system_instruction = (
        "You are an expert Tax Law Assistant operating under strict 'Open-Book' guidelines.\n"
        "Your task is to answer the user's question using ONLY the provided Source passages.\n\n"
        "CRITICAL RULES:\n"
        "1. If the provided Source passages do not contain information related to the question, you must respond: "
        "'I cannot find the answer to this question in the provided tax documents.' Do not attempt to answer using general outside knowledge.\n"
        "2. For every fact or rate you mention, you MUST explicitly cite which Source [X] it came from (e.g., 'According to [Source 1], ...').\n"
        "3. Keep your tone objective, professional, and directly grounded. Do not extrapolate or speculate.\n"
        "4. If there are conflicting rates or sections across sources, list both and note the discrepancy.\n"
        "5. The provided context includes text, tables, and transcript timestamps. Reference them exactly."
    )
    
    user_prompt = f"Context passages:\n{context_str}\n\nUser Question: {question}"

    if LLM_PROVIDER == "ollama":
        try:
            res = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json={
                "model": OLLAMA_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "options": {"temperature": 0.0},
                "stream": False
            })
            res.raise_for_status()
            answer = res.json()["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama inference failed: {e}. Ensure Ollama is running and has pulled model '{OLLAMA_LLM_MODEL}'")
    else:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is missing in configuration.")
        
        # Configure model parameters
        generation_config = {
            "temperature": 0.0,
            "max_output_tokens": 1024,
        }
        
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=system_instruction,
            generation_config=generation_config
        )
        response = model.generate_content(user_prompt)
        answer = response.text

    # Unique citations list
    unique_citations = list(dict.fromkeys(citations))
    
    # Return grounded result
    return {
        "answer": answer,
        "source": ", ".join(unique_citations) if unique_citations else "No specific document retrieved."
    }

@app.get("/")
def read_root():
    return {
        "status": "Backend is running smoothly",
        "provider": LLM_PROVIDER,
        "index_connected": index is not None,
        "bm25_loaded": bm25 is not None
    }

@app.post("/api/query")
async def process_tax_query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
        
    # Reload BM25 dynamically if it wasn't loaded at startup (e.g. after first ingestion)
    global bm25, index
    if not bm25 and os.path.exists(BM25_MODEL_PATH):
        try:
            bm25 = BM25Encoder()
            bm25.load(BM25_MODEL_PATH)
        except Exception as e:
            print(f"[WARNING] BM25 load retry failed: {e}")
            
    if not index and pc:
        try:
            if INDEX_NAME in pc.list_indexes().names():
                index = pc.Index(INDEX_NAME)
        except Exception as e:
            print(f"[WARNING] Pinecone index connect retry failed: {e}")

    try:
        # 1. Search hybrid index
        if index:
            search_results = perform_hybrid_query(request.question, alpha=0.5, top_k=20)
            matches = search_results.get("matches", [])
        else:
            matches = []

        if not matches:
            # Fallback if database is empty or Pinecone connection isn't set up
            return {
                "answer": "⚠️ The database index is currently offline or empty. Please place your PDFs, PPTs, or Videos into the `backend/data` directory and run the `ingestion.py` script to populate the vector search database.",
                "source": "None"
            }

        # 2. Formulate open book query
        result = generate_grounded_response(request.question, matches)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

@app.post("/api/ingest")
async def trigger_ingestion():
    try:
        from ingestion import DocumentIngestionPipeline
        pipeline = DocumentIngestionPipeline()
        pipeline.process_all_files()
        return {"status": "success", "message": "All documents ingested successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)