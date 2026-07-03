import sqlite3
import os
import uuid
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "taxbot.db")

def get_db_connection():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes database tables if they do not exist."""
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
    print(f"Database initialized successfully at: {DB_PATH}")

# --- CRUD Helpers for Sessions ---

def create_session(user_id: str, title: str) -> str:
    """Creates a new session and returns its ID."""
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def update_session_title(session_id: str, title: str):
    """Updates the title of a session."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET title = ? WHERE id = ?", (title, session_id))
    conn.commit()
    conn.close()

# --- CRUD Helpers for Messages ---

def add_message(session_id: str, role: str, content: str, source: str = None) -> str:
    """Adds a message to an active chat session and returns its ID."""
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, role, content, source, feedback FROM messages WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
