import sqlite3
import os
import uuid
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv(dotenv_path="../.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
supabase = None

# A static UUID representing the local development user
LOCAL_USER_UUID = "00000000-0000-0000-0000-000000000000"

if USE_SUPABASE:
    try:
        from supabase import create_client, Client
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"Initialized Supabase client targeting URL: {SUPABASE_URL}")
    except Exception as e:
        print(f"[ERROR] Failed to initialize Supabase client: {e}")
        USE_SUPABASE = False

DB_PATH = os.path.join(os.path.dirname(__file__), "taxbot.db")

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_local_user_exists():
    """Ensures a default local developer user exists in Supabase so local sessions work."""
    if USE_SUPABASE and supabase:
        try:
            res = supabase.table("taxbot_users").select("id").eq("id", LOCAL_USER_UUID).execute()
            if not res.data:
                supabase.table("taxbot_users").insert({
                    "id": LOCAL_USER_UUID,
                    "taxsutra_id": "local_user",
                    "email": "local_user@taxsutra.com",
                    "full_name": "Local Development User",
                    "plan": "basic"
                }).execute()
                print("Default local development user initialized in Supabase.")
        except Exception as e:
            print(f"[WARNING] Could not ensure local user in Supabase: {e}")

def init_db():
    """Initializes database tables if they do not exist (SQLite) or verifies user exists (Supabase)."""
    if not USE_SUPABASE:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT,
                feedback TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
            )
        """)
        
        # Migration: Check if feedback column exists, if not add it
        try:
            cursor.execute("SELECT feedback FROM messages LIMIT 1")
        except sqlite3.OperationalError:
            print("Migrating database: adding feedback column to messages table...")
            cursor.execute("ALTER TABLE messages ADD COLUMN feedback TEXT")
            
        conn.commit()
        conn.close()
        print(f"Local SQLite database initialized successfully at: {DB_PATH}")
    else:
        ensure_local_user_exists()
        print("Using Supabase connection for data operations.")

def get_db_status() -> dict:
    """Returns database connection diagnostics."""
    if USE_SUPABASE and supabase:
        try:
            # Query a minimal row to check connection
            supabase.table("taxbot_users").select("id").limit(1).execute()
            return {"status": "connected", "type": "supabase", "url": SUPABASE_URL}
        except Exception as e:
            return {"status": "error", "type": "supabase", "url": SUPABASE_URL, "error": str(e)}
    else:
        return {"status": "connected", "type": "sqlite", "path": "taxbot.db"}

# --- CRUD Helpers for Sessions ---

def create_session(user_id: str, title: str) -> str:
    """Creates a new session and returns its ID."""
    if USE_SUPABASE and supabase:
        db_user_id = LOCAL_USER_UUID if user_id == "local_user" else user_id
        res = supabase.table("taxbot_sessions").insert({
            "title": title,
            "user_id": db_user_id
        }).execute()
        return res.data[0]["id"]
    else:
        session_id = str(uuid.uuid4())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (id, user_id, title) VALUES (?, ?, ?)",
            (session_id, user_id, title)
        )
        conn.commit()
        conn.close()
        return session_id

def get_sessions(user_id: str) -> list[dict]:
    """Retrieves all sessions for a given user, sorted by creation date descending."""
    if USE_SUPABASE and supabase:
        db_user_id = LOCAL_USER_UUID if user_id == "local_user" else user_id
        res = supabase.table("taxbot_sessions") \
            .select("id, title, created_at") \
            .eq("user_id", db_user_id) \
            .order("created_at", desc=True) \
            .execute()
        return res.data
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def delete_session(session_id: str):
    """Deletes a session and all its cascading messages."""
    if USE_SUPABASE and supabase:
        supabase.table("taxbot_sessions").delete().eq("id", session_id).execute()
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

def update_session_title(session_id: str, title: str):
    """Updates the title of a session."""
    if USE_SUPABASE and supabase:
        supabase.table("taxbot_sessions").update({"title": title}).eq("id", session_id).execute()
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
        conn.commit()
        conn.close()

# --- CRUD Helpers for Messages ---

def add_message(session_id: str, role: str, content: str, source: str = None) -> str:
    """Adds a message to an active chat session and returns its ID."""
    if USE_SUPABASE and supabase:
        # Check database constraints - role must be 'user' or 'assistant'
        db_role = 'user' if role == 'user' else 'assistant'
        res = supabase.table("taxbot_messages").insert({
            "session_id": session_id,
            "role": db_role,
            "content": content,
            "source": source
        }).execute()
        return res.data[0]["id"]
    else:
        message_id = str(uuid.uuid4())
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (id, session_id, role, content, source) VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, role, content, source)
        )
        conn.commit()
        conn.close()
        return message_id

def update_message_feedback(message_id: str, feedback: str):
    """Updates user feedback (e.g. 'up', 'down', or NULL) for a message."""
    if USE_SUPABASE and supabase:
        supabase.table("taxbot_messages").update({"feedback": feedback}).eq("id", message_id).execute()
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET feedback = ? WHERE id = ?",
            (feedback, message_id)
        )
        conn.commit()
        conn.close()

def get_session_messages(session_id: str) -> list[dict]:
    """Retrieves all messages for a session, sorted chronologically."""
    if USE_SUPABASE and supabase:
        res = supabase.table("taxbot_messages") \
            .select("id, role, content, source, feedback, created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=False) \
            .execute()
        return res.data
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, role, content, source, feedback FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

# --- Admin Chat Data Retrieval Helpers ---

def admin_get_all_chat_sessions() -> list[dict]:
    """Retrieves all chat sessions from SQLite or Supabase with message counts."""
    if USE_SUPABASE and supabase:
        try:
            # Query sessions
            sessions_res = supabase.table("taxbot_sessions") \
                .select("id, user_id, title, created_at") \
                .order("created_at", desc=True) \
                .execute()
            sessions = sessions_res.data
            
            for s in sessions:
                # Query count of messages
                count_res = supabase.table("taxbot_messages") \
                    .select("id", count="exact") \
                    .eq("session_id", s["id"]) \
                    .execute()
                s["message_count"] = count_res.count if count_res.count is not None else 0
                
                # Query last message timestamp
                last_msg_res = supabase.table("taxbot_messages") \
                    .select("created_at") \
                    .eq("session_id", s["id"]) \
                    .order("created_at", desc=True) \
                    .limit(1) \
                    .execute()
                s["last_message_at"] = last_msg_res.data[0]["created_at"] if last_msg_res.data else s["created_at"]
            
            return sessions
        except Exception as e:
            print(f"[ERROR] Supabase admin list sessions failed: {e}")
            return []
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                s.id, s.user_id, s.title, s.created_at,
                COUNT(m.id) as message_count,
                MAX(m.created_at) as last_message_at
            FROM sessions s
            LEFT JOIN messages m ON m.session_id = s.id
            GROUP BY s.id
            ORDER BY s.created_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def admin_get_chat_session_details(session_id: str) -> dict:
    """Retrieves metadata and full transcript messages for a session."""
    if USE_SUPABASE and supabase:
        try:
            sess_res = supabase.table("taxbot_sessions").select("id, user_id, title, created_at").eq("id", session_id).execute()
            if not sess_res.data:
                return None
            msg_res = supabase.table("taxbot_messages") \
                .select("id, role, content, source, feedback, created_at") \
                .eq("session_id", session_id) \
                .order("created_at", desc=False) \
                .execute()
            return {
                "session": sess_res.data[0],
                "messages": msg_res.data
            }
        except Exception as e:
            print(f"[ERROR] Supabase admin get session details failed: {e}")
            return None
    else:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, user_id, title, created_at FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        if not session:
            conn.close()
            return None
        cursor.execute("SELECT id, role, content, source, feedback, created_at FROM messages WHERE session_id = ? ORDER BY created_at ASC", (session_id,))
        messages = cursor.fetchall()
        conn.close()
        return {
            "session": dict(session),
            "messages": [dict(m) for m in messages]
        }
