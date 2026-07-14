import streamlit as st
import requests

# Page Configuration
st.set_page_config(page_title="Tax Law Assistant", page_icon="⚖️", layout="wide")

st.title("⚖️ Income Tax Act - Assistant")
st.caption("AI-powered verification engine for Chartered Accountants. All answers are strictly grounded in active updates.")

# --- SESSION STATE INITIALIZATION ---
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Helper: Load messages for a session
def load_session(session_id):
    st.session_state.active_session_id = session_id
    if session_id:
        try:
            res = requests.get(f"http://127.0.0.1:8000/api/sessions/{session_id}/messages")
            if res.status_code == 200:
                st.session_state.messages = res.json()
            else:
                st.session_state.messages = []
        except Exception:
            st.session_state.messages = []
    else:
        st.session_state.messages = []

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("⚙️ System Management")

# Fetch Backend Status
backend_info_url = "http://127.0.0.1:8000/"
backend_online = False
try:
    info_res = requests.get(backend_info_url, timeout=3)
    if info_res.status_code == 200:
        backend_online = True
        status_data = info_res.json()
        provider = status_data.get("provider", "Unknown").upper()
        index_connected = "🟢 Connected" if status_data.get("index_connected", False) else "🔴 Disconnected"
        bm25_loaded = "🟢 Loaded" if status_data.get("bm25_loaded", False) else "🔴 Unloaded"
        
        st.sidebar.success("Backend: Online")
        st.sidebar.markdown(f"**LLM Provider:** `{provider}`")
        st.sidebar.markdown(f"**Pinecone Index:** {index_connected}")
        st.sidebar.markdown(f"**BM25 Model:** {bm25_loaded}")
    else:
        st.sidebar.error("Backend: Error")
except requests.exceptions.ConnectionError:
    st.sidebar.error("Backend: Offline 🔴")

st.sidebar.markdown("---")
st.sidebar.subheader("💬 Conversations")

# New Chat Button
if st.sidebar.button("➕ New Chat", use_container_width=True):
    load_session(None)
    st.rerun()

# Load and list sessions in sidebar
if backend_online:
    try:
        sess_res = requests.get("http://127.0.0.1:8000/api/sessions")
        if sess_res.status_code == 200:
            sessions = sess_res.json()
            for sess in sessions:
                col1, col2 = st.sidebar.columns([0.8, 0.2])
                
                # Highlight active session
                btn_label = f"💬 {sess['title']}"
                if sess['id'] == st.session_state.active_session_id:
                    btn_label = f"👉 {sess['title']}"
                
                if col1.button(btn_label, key=f"sess_{sess['id']}", use_container_width=True):
                    load_session(sess['id'])
                    st.rerun()
                    
                if col2.button("🗑️", key=f"del_{sess['id']}", use_container_width=True):
                    requests.delete(f"http://127.0.0.1:8000/api/sessions/{sess['id']}")
                    if st.session_state.active_session_id == sess['id']:
                        load_session(None)
                    st.rerun()
    except Exception as e:
        st.sidebar.error(f"Failed to load chat logs: {e}")

# --- MAIN CHAT UI ---

# Display message history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("source") and message.get("source") != "None":
            st.caption(f"**Verified Source:** {message['source']}")

# Handle User Input
if user_query := st.chat_input("Ask about recent Income Tax Act changes (e.g., 'What is the new threshold for section 44AD?')..."):
    
    # Display user question immediately
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Call FastAPI Backend
    backend_url = "http://127.0.0.1:8000/api/query"
    payload = {
        "question": user_query,
        "session_id": st.session_state.active_session_id
    }
    
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.markdown("🔍 *Searching verified tax documents, PPTs, and transcripts...*")
        
        try:
            res = requests.post(backend_url, json=payload, timeout=30)
            
            if res.status_code == 200:
                data = res.json()
                answer = data.get("answer")
                source = data.get("source", "No explicit source cited.")
                returned_session_id = data.get("session_id")
                
                # Render response
                response_placeholder.markdown(answer)
                if source and source != "None":
                    st.caption(f"**Verified Source:** {source}")
                
                # Save assistant response to state
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer, 
                    "source": source
                })
                
                # If this was a new session, lock it in and rerun to refresh the sidebar list
                if st.session_state.active_session_id != returned_session_id:
                    st.session_state.active_session_id = returned_session_id
                    st.rerun()
            else:
                error_msg = f"⚠️ Backend Error: {res.json().get('detail', 'Unknown error occurrence')}"
                response_placeholder.markdown(error_msg)
                
        except requests.exceptions.ConnectionError:
            response_placeholder.markdown("❌ **Error:** Cannot connect to the FastAPI backend. Ensure it is running on port 8000.")