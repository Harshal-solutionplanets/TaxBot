import streamlit as st
import requests

# Page Configuration
st.set_page_config(page_title="Tax Law Assistant", page_icon="⚖️", layout="wide")

st.title("⚖️ Income Tax Act - Assistant")
st.caption("AI-powered verification engine for Chartered Accountants. All answers are strictly grounded in active updates.")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.title("⚙️ System Management")

# Fetch Backend Status
backend_info_url = "http://127.0.0.1:8000/"
try:
    info_res = requests.get(backend_info_url, timeout=3)
    if info_res.status_code == 200:
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



# Initialize chat session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "source" in message:
            st.caption(f"**Verified Source:** {message['source']}")

# Handle User Input
if user_query := st.chat_input("Ask about recent Income Tax Act changes (e.g., 'What is the new threshold for section 44AD?')..."):
    
    # Display user question
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    # Call FastAPI Backend
    backend_url = "http://127.0.0.1:8000/api/query"
    
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.markdown("🔍 *Searching verified documents, PPTs, and video transcripts...*")
        
        try:
            res = requests.post(backend_url, json={"question": user_query}, timeout=30)
            
            if res.status_code == 200:
                data = res.json()
                answer = data.get("answer")
                source = data.get("source", "No explicit source cited.")
                
                # Render response
                response_placeholder.markdown(answer)
                st.caption(f"**Verified Source:** {source}")
                
                # Save to history
                st.session_state.messages.append({"role": "assistant", "content": answer, "source": source})
            else:
                error_msg = f"⚠️ Backend Error: {res.json().get('detail', 'Unknown error occurrence')}"
                response_placeholder.markdown(error_msg)
                
        except requests.exceptions.ConnectionError:
            response_placeholder.markdown("❌ **Error:** Cannot connect to the FastAPI backend. Ensure it is running on port 8000.")