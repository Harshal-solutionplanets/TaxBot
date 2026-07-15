import os
import shutil
import json
import hashlib
import time
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import google.generativeai as genai
import requests
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
from database import (
    init_db,
    create_session,
    get_sessions,
    delete_session,
    add_message,
    get_session_messages,
    update_session_title,
    update_message_feedback,
    get_db_status,
    admin_get_all_chat_sessions,
    admin_get_chat_session_details
)

# Load environment variables
load_dotenv(dotenv_path="../.env")

# Initialize FastAPI
app = FastAPI(title="TaxBot API")

# --- Answer Cache ---
answer_cache = {}
CACHE_TTL_SECONDS = 24 * 60 * 60

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    user_id: str = "local_user"

class SessionCreateRequest(BaseModel):
    title: str = "New Chat"
    user_id: str = "local_user"

# Configs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3.1")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
SUGGESTION_QUESTIONS = os.getenv("SUGGESTION_QUESTIONS", "False").lower() in ("true", "1", "yes")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "10"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
if LLM_PROVIDER == "gemini":
    # Using the Ollama-generated index for Gemini because Gemini Free Tier 
    # cannot embed 9,000+ chunks (hits 100/min and 1,500/day limits).
    INDEX_NAME = "taxbot-hybrid-index"
    BM25_MODEL_PATH = "./bm25_ollama.json"
else:
    INDEX_NAME = "taxbot-hybrid-index"
    BM25_MODEL_PATH = "./bm25_ollama.json"

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
    if LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            print("[ERROR] Gemini API Key missing for query embedding.")
            return []
        try:
            res = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_query",
                output_dimensionality=768
            )
            return res["embedding"]
        except Exception as e:
            print(f"[ERROR] Gemini embedding failed: {e}")
            return []
    else:
        try:
            res = requests.post(f"{OLLAMA_BASE_URL}/api/embeddings", json={
                "model": OLLAMA_EMBED_MODEL,
                "prompt": text
            })
            res.raise_for_status()
            return res.json()["embedding"]
        except Exception as e:
            print(f"[ERROR] Local embedding failed: {e}")
            return []

# Helper: Hybrid Score Combination
def perform_hybrid_query(query_text: str, alpha: float = 0.5, top_k: int = 5):
    """Executes a hybrid search query on Pinecone using dense and sparse vectors."""
    if not index:
        raise ValueError("Pinecone index connection is not available.")
    
    # 1. Dense Vector
    dense_vec = get_dense_embedding(query_text)
    if not dense_vec:
        print("[WARNING] Failed to generate dense embedding (API limit reached?). Falling back to sparse-only search.")
        dense_vec = [0.0] * 768
    
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
            model_name="gemini-2.0-flash-lite",
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

# --- Session Management Endpoints ---

@app.get("/api/sessions")
def list_sessions(user_id: str = "local_user"):
    try:
        return get_sessions(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sessions")
def new_session(request: SessionCreateRequest):
    try:
        session_id = create_session(request.user_id, request.title)
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}/messages")
def load_messages(session_id: str):
    try:
        return get_session_messages(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
def remove_session(session_id: str):
    try:
        delete_session(session_id)
        return {"status": "success", "message": "Session deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Query Route ---

# Helper: Generation (Streamed)
def generate_grounded_response_stream(question: str, context_chunks: list[dict], session_id: str):
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
    unique_citations = list(dict.fromkeys(citations))
    source_str = ", ".join(unique_citations) if unique_citations else "No specific document retrieved."

    # Yield metadata first (always the first chunk)
    yield json.dumps({
        "event": "metadata",
        "session_id": session_id,
        "source": source_str
    }) + "\n"

    accumulated_answer = ""

    if LLM_PROVIDER == "ollama":
        try:
            res = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json={
                "model": OLLAMA_LLM_MODEL,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": user_prompt}
                ],
                "options": {"temperature": 0.0},
                "stream": True
            }, stream=True)
            res.raise_for_status()
            for line in res.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    text = chunk.get("message", {}).get("content", "")
                    if text:
                        accumulated_answer += text
                        yield json.dumps({"event": "content", "text": text}) + "\n"
        except Exception as e:
            err_msg = f"Ollama inference failed: {e}. Ensure Ollama is running."
            yield json.dumps({"event": "content", "text": err_msg}) + "\n"
            accumulated_answer = err_msg
    else:
        if not GEMINI_API_KEY:
            err_msg = "GEMINI_API_KEY is missing in configuration."
            yield json.dumps({"event": "content", "text": err_msg}) + "\n"
            accumulated_answer = err_msg
        else:
            try:
                # Configure model parameters
                generation_config = {
                    "temperature": 0.0,
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                }
                
                model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash-lite",
                    system_instruction=system_instruction,
                    generation_config=generation_config
                )
                response = model.generate_content(user_prompt, stream=True)
                for chunk in response:
                    try:
                        text = chunk.text
                    except ValueError:
                        text = ""
                        
                    if text:
                        accumulated_answer += text
                        yield json.dumps({"event": "content", "text": text}) + "\n"
            except Exception as e:
                err_msg = f"Gemini inference failed: {e}"
                yield json.dumps({"event": "content", "text": err_msg}) + "\n"
                accumulated_answer = err_msg

    # Save final response to database
    try:
        add_message(session_id, "assistant", accumulated_answer, source_str)
    except Exception as e:
        print(f"[WARNING] Failed to save assistant message: {e}")

    # Add to cache
    question_key = hashlib.md5(question.strip().lower().encode()).hexdigest()
    answer_cache[question_key] = {
        "answer": accumulated_answer,
        "source": source_str,
        "timestamp": time.time()
    }

    yield json.dumps({"event": "done"}) + "\n"


# --- Query Route (Streamed) ---

@app.post("/api/query")
async def process_tax_query(request: QueryRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
        
    # Reload BM25 dynamically if it wasn't loaded at startup
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

    # Establish or verify active session
    session_id = request.session_id
    if not session_id or session_id.strip() == "":
        try:
            title = request.question.strip()[:30] + ("..." if len(request.question) > 30 else "")
            session_id = create_session(request.user_id, title)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create session: {e}")

    # Save user message to database
    try:
        add_message(session_id, "user", request.question)
    except Exception as e:
        print(f"[WARNING] Failed to save user message: {e}")

    # Check Answer Cache first
    question_key = hashlib.md5(request.question.strip().lower().encode()).hexdigest()
    if question_key in answer_cache:
        cached_data = answer_cache[question_key]
        if time.time() - cached_data["timestamp"] < CACHE_TTL_SECONDS:
            # Save assistant message directly
            try:
                add_message(session_id, "assistant", cached_data["answer"], cached_data["source"])
            except Exception as e:
                print(f"[WARNING] Failed to save assistant message: {e}")
                
            def cached_generator():
                yield json.dumps({
                    "event": "metadata",
                    "session_id": session_id,
                    "source": cached_data["source"]
                }) + "\n"
                
                # Stream it in small chunks to simulate generation so UI looks natural
                ans = cached_data["answer"]
                chunk_size = 50
                for i in range(0, len(ans), chunk_size):
                    yield json.dumps({"event": "content", "text": ans[i:i+chunk_size]}) + "\n"
                    time.sleep(0.02)
                    
                yield json.dumps({"event": "done"}) + "\n"
                
            return StreamingResponse(cached_generator(), media_type="text/event-stream")
        else:
            del answer_cache[question_key]

    try:
        # Search hybrid index
        if index:
            search_results = perform_hybrid_query(request.question, alpha=0.5, top_k=RAG_TOP_K)
            matches = search_results.get("matches", [])
        else:
            matches = []

        if not matches:
            ans = "⚠️ The database index is currently offline or empty. Please place your PDFs, PPTs, or Videos into the `backend/data` directory and run the `ingestion.py` script to populate the vector search database."
            src = "None"
            
            # Save assistant error response
            try:
                add_message(session_id, "assistant", ans, src)
            except Exception as e:
                print(f"[WARNING] Failed to save assistant message: {e}")
                
            def static_generator():
                yield json.dumps({
                    "event": "metadata",
                    "session_id": session_id,
                    "source": src
                }) + "\n"
                yield json.dumps({"event": "content", "text": ans}) + "\n"
                yield json.dumps({"event": "done"}) + "\n"
                
            return StreamingResponse(static_generator(), media_type="text/event-stream")

        # Stream grounded response
        return StreamingResponse(
            generate_grounded_response_stream(request.question, matches, session_id),
            media_type="text/event-stream"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Feedback & Follow-up Endpoint definitions ---

class FollowupsRequest(BaseModel):
    conversation_history: list[dict]

@app.get("/api/config")
def get_app_config():
    """Returns client-facing feature flags so the frontend can adapt."""
    return {
        "suggestion_questions": SUGGESTION_QUESTIONS,
        "llm_provider": LLM_PROVIDER,
    }

@app.post("/api/query/suggest-followups")
def suggest_followups(request: FollowupsRequest):
    # Cost gate: skip Gemini call entirely when suggestions are disabled
    if not SUGGESTION_QUESTIONS:
        return []
    if not GEMINI_API_KEY:
        return []
        
    try:
        history_str = ""
        for msg in request.conversation_history[-3:]:
            history_str += f"{msg['role']}: {msg['content']}\n"
            
        prompt = (
            f"Based on the following recent conversation history between a CA and a Tax Assistant, "
            f"suggest exactly 3 short, relevant follow-up questions the CA might ask next. "
            f"Focus strictly on Indian Income Tax law. Return them as a JSON list of strings.\n\n"
            f"History:\n{history_str}\n"
            f"Output format: [\"question 1\", \"question 2\", \"question 3\"]"
        )
        
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        res = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        questions = json.loads(res.text)
        if isinstance(questions, list) and len(questions) >= 3:
            return questions[:3]
    except Exception as e:
        print(f"[WARNING] Failed to generate smart followups: {e}")
        
    return []

class FeedbackRequest(BaseModel):
    feedback: str  # 'up', 'down', or 'none'

@app.post("/api/messages/{message_id}/feedback")
def log_message_feedback(message_id: str, request: FeedbackRequest):
    try:
        update_message_feedback(message_id, request.feedback)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Admin Panel Endpoints ---

@app.get("/api/admin/files")
def list_data_files():
    """Returns a list of all files in the data directory with metadata."""
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    
    files = []
    supported_ext = {".pdf", ".pptx", ".ppt", ".vtt"}
    for filename in os.listdir(data_dir):
        file_path = os.path.join(data_dir, filename)
        if os.path.isfile(file_path):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in supported_ext:
                continue
            stat = os.stat(file_path)
            from datetime import datetime
            files.append({
                "filename": filename,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "type": ext.replace(".", "").upper(),
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
    
    # Sort by upload time descending
    files.sort(key=lambda x: x["uploaded_at"], reverse=True)
    return files

@app.post("/api/admin/upload")
async def admin_upload_files(files: list[UploadFile] = File(...)):
    """Upload one or more files to the data directory."""
    data_dir = "./data"
    os.makedirs(data_dir, exist_ok=True)
    
    uploaded = []
    errors = []
    supported_ext = {".pdf", ".pptx", ".ppt", ".vtt"}
    
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in supported_ext:
            errors.append(f"Unsupported file type: {file.filename} ({ext})")
            continue
            
        file_path = os.path.join(data_dir, file.filename)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            uploaded.append(file.filename)
        except Exception as e:
            errors.append(f"Failed to save {file.filename}: {str(e)}")
    
    return {
        "status": "success" if uploaded else "error",
        "uploaded": uploaded,
        "errors": errors
    }

@app.delete("/api/admin/files/{filename}")
def admin_delete_file(filename: str):
    """Delete a file from the data directory."""
    file_path = os.path.join("./data", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")
    try:
        os.remove(file_path)
        return {"status": "success", "message": f"Deleted '{filename}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/admin/ingest")
async def admin_trigger_ingestion():
    """
    Runs the full ingestion pipeline and streams progress updates via SSE.
    Each line is a JSON object with event type and data.
    """
    import threading
    import queue
    import time
    
    progress_queue = queue.Queue()
    
    def run_ingestion():
        try:
            from ingestion import DocumentIngestionPipeline
            
            progress_queue.put(json.dumps({"event": "progress", "step": "init", "message": "Initializing ingestion pipeline...", "percent": 5}))
            pipeline = DocumentIngestionPipeline()
            
            # --- Phase 1: Parse files ---
            progress_queue.put(json.dumps({"event": "progress", "step": "parse", "message": "Scanning data directory...", "percent": 10}))
            
            data_dir = "./data"
            all_files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
            supported_files = [f for f in all_files if os.path.splitext(f)[1].lower() in {".pdf", ".pptx", ".ppt", ".vtt"}]
            total_files = len(supported_files)
            
            if total_files == 0:
                progress_queue.put(json.dumps({"event": "error", "message": "No supported files found in data directory."}))
                progress_queue.put(None)
                return
            
            progress_queue.put(json.dumps({"event": "progress", "step": "parse", "message": f"Found {total_files} files to process...", "percent": 15}))
            
            # Parse all files
            all_raw_chunks = []
            vtt_bases = set()
            
            for i, filename in enumerate(supported_files):
                file_path = os.path.join(data_dir, filename)
                ext = os.path.splitext(filename)[1].lower()
                file_percent = 15 + int((i / total_files) * 25)
                progress_queue.put(json.dumps({"event": "progress", "step": "parse", "message": f"Parsing: {filename}", "percent": file_percent}))
                
                if ext == ".pdf":
                    all_raw_chunks.extend(pipeline.parse_pdf(file_path))
                elif ext in [".pptx", ".ppt"]:
                    all_raw_chunks.extend(pipeline.parse_ppt(file_path))
                elif ext == ".vtt":
                    vtt_bases.add(filename.split(".")[0])
                    all_raw_chunks.extend(pipeline.parse_vtt(file_path))
            
            if not all_raw_chunks:
                progress_queue.put(json.dumps({"event": "error", "message": "No text content extracted from files."}))
                progress_queue.put(None)
                return
            
            # --- Phase 2: Chunk ---
            progress_queue.put(json.dumps({"event": "progress", "step": "chunk", "message": f"Splitting {len(all_raw_chunks)} pages into embedding chunks...", "percent": 42}))
            refined_chunks = pipeline.split_into_embeddings_chunks(all_raw_chunks)
            total_chunks = len(refined_chunks)
            progress_queue.put(json.dumps({"event": "progress", "step": "chunk", "message": f"Generated {total_chunks} chunks.", "percent": 48}))
            
            # --- Phase 3: BM25 ---
            progress_queue.put(json.dumps({"event": "progress", "step": "bm25", "message": "Training BM25 keyword model...", "percent": 52}))
            corpus_texts = [c["text"] for c in refined_chunks]
            pipeline.fit_bm25(corpus_texts)
            progress_queue.put(json.dumps({"event": "progress", "step": "bm25", "message": "BM25 model trained and saved.", "percent": 58}))
            
            # --- Phase 4: Pinecone ---
            progress_queue.put(json.dumps({"event": "progress", "step": "pinecone", "message": "Connecting to Pinecone...", "percent": 60}))
            if not pipeline.init_pinecone_index():
                progress_queue.put(json.dumps({"event": "error", "message": "Failed to connect to Pinecone. Check API key."}))
                progress_queue.put(None)
                return
            
            # --- Phase 5: Embed + Upload ---
            progress_queue.put(json.dumps({"event": "progress", "step": "upload", "message": f"Embedding and uploading {total_chunks} chunks to Pinecone...", "percent": 62}))
            
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import re as re_mod
            
            vectors_to_upsert = []
            completed_count = 0
            
            def worker(idx, chunk):
                text = chunk["text"]
                metadata = chunk["metadata"]
                if not text.strip():
                    return None
                metadata["text"] = text
                try:
                    dense_vector = pipeline.get_dense_embedding(text)
                    sparse_vector = pipeline.get_sparse_embedding(text)
                    chunk_id = f"chunk_{metadata['source']}_{idx}"
                    chunk_id = re_mod.sub(r'[^a-zA-Z0-9_\-\.#]', '_', chunk_id)
                    vector_data = {
                        "id": chunk_id,
                        "values": dense_vector,
                        "metadata": metadata
                    }
                    if sparse_vector.get("indices") and sparse_vector.get("values"):
                        vector_data["sparse_values"] = sparse_vector
                    return vector_data
                except Exception as e:
                    return None
            
            with ThreadPoolExecutor(max_workers=16) as executor:
                futures = {executor.submit(worker, idx, chunk): idx for idx, chunk in enumerate(refined_chunks)}
                for future in as_completed(futures):
                    vector_data = future.result()
                    completed_count += 1
                    
                    if completed_count % 20 == 0 or completed_count == total_chunks:
                        upload_percent = 62 + int((completed_count / total_chunks) * 33)
                        progress_queue.put(json.dumps({
                            "event": "progress",
                            "step": "upload",
                            "message": f"Processed {completed_count}/{total_chunks} chunks...",
                            "percent": min(upload_percent, 95)
                        }))
                    
                    if vector_data:
                        vectors_to_upsert.append(vector_data)
                        if len(vectors_to_upsert) >= 50:
                            try:
                                pipeline.index.upsert(vectors=vectors_to_upsert)
                            except Exception as e:
                                progress_queue.put(json.dumps({"event": "warning", "message": f"Batch upload error: {e}"}))
                            vectors_to_upsert = []
            
            # Final batch
            if vectors_to_upsert:
                try:
                    pipeline.index.upsert(vectors=vectors_to_upsert)
                except Exception as e:
                    progress_queue.put(json.dumps({"event": "warning", "message": f"Final batch error: {e}"}))
            
            progress_queue.put(json.dumps({
                "event": "complete",
                "message": f"Ingestion complete! {total_chunks} chunks from {total_files} files uploaded to Pinecone.",
                "percent": 100
            }))
            
        except Exception as e:
            progress_queue.put(json.dumps({"event": "error", "message": f"Ingestion failed: {str(e)}"}))
        finally:
            progress_queue.put(None)  # Signal end of stream
    
    def generate():
        # Start ingestion in a background thread
        thread = threading.Thread(target=run_ingestion, daemon=True)
        thread.start()
        while True:
            try:
                # Wait for progress messages, timeout after 15s to send keep-alive
                msg = progress_queue.get(timeout=15)
                if msg is None:
                    break
                yield msg + "\n"
            except queue.Empty:
                # Render load balancer times out idle connections at 100s. 
                # Send valid JSON keep-alive with padding to defeat Gunicorn buffering.
                yield json.dumps({"event": "keepalive"}) + " " * 1024 + "\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/admin/db-status")
def admin_db_status():
    """Returns database connection diagnostics."""
    return get_db_status()

@app.get("/api/admin/chat-sessions")
def admin_list_chat_sessions():
    """Returns all chat sessions across all users with message count and last activity."""
    return admin_get_all_chat_sessions()

@app.get("/api/admin/chat-sessions/{session_id}/messages")
def admin_get_session_messages(session_id: str):
    """Returns all messages for a specific session."""
    data = admin_get_chat_session_details(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    return data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
