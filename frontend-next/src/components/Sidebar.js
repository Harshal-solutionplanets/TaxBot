import { useState, useEffect } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function Sidebar({ activeSessionId, setActiveSessionId, theme, toggleTheme, isDrawerOpen, setIsDrawerOpen }) {
  const [sessions, setSessions] = useState([]);
  const [backendStatus, setBackendStatus] = useState(null);

  // Fetch backend status
  useEffect(() => {
    fetch(`${API_URL}/`)
      .then(res => res.json())
      .then(data => setBackendStatus(data))
      .catch(() => setBackendStatus(null));
  }, []);

  // Fetch sessions
  const fetchSessions = () => {
    fetch(`${API_URL}/api/sessions`)
      .then(res => res.json())
      .then(data => setSessions(data))
      .catch(err => console.error("Failed to fetch sessions", err));
  };

  useEffect(() => {
    fetchSessions();
  }, [activeSessionId]);

  const deleteSession = async (id, e) => {
    e.stopPropagation();
    try {
      await fetch(`${API_URL}/api/sessions/${id}`, { method: 'DELETE' });
      if (activeSessionId === id) {
        setActiveSessionId(null);
      }
      fetchSessions();
    } catch (err) {
      console.error("Failed to delete session", err);
    }
  };

  const handleSelectSession = (id) => {
    setActiveSessionId(id);
    if (setIsDrawerOpen) setIsDrawerOpen(false);
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
    if (setIsDrawerOpen) setIsDrawerOpen(false);
  };

  return (
    <>
      <div className={`sidebar ${isDrawerOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h2 className="sidebar-title">⚙️ TaxBot</h2>
          <button onClick={toggleTheme} className="theme-toggle" aria-label="Toggle Theme">
            {theme === 'light' ? '🌙 Dark' : '☀️ Light'}
          </button>
        </div>

        <button className="new-chat-btn" onClick={handleNewChat}>
          ➕ New Chat
        </button>

        <div className="sessions-list">
          {sessions.map(sess => (
            <div 
              key={sess.id} 
              className={`session-item ${activeSessionId === sess.id ? 'active' : ''}`}
              onClick={() => handleSelectSession(sess.id)}
            >
              <span className="session-title">
                {activeSessionId === sess.id ? '👉' : '💬'} {sess.title}
              </span>
              <button className="delete-btn" onClick={(e) => deleteSession(sess.id, e)} title="Delete chat">
                🗑️
              </button>
            </div>
          ))}
        </div>

        <div className="backend-status">
          {backendStatus ? (
            <>
              <div><span className="status-indicator online"></span>Backend: Online</div>
              <div style={{ marginTop: '5px' }}><strong>LLM:</strong> {backendStatus.provider}</div>
              <div><strong>Pinecone:</strong> {backendStatus.index_connected ? '🟢 Connected' : '🔴 Disconnected'}</div>
            </>
          ) : (
            <div><span className="status-indicator offline"></span>Backend: Offline 🔴</div>
          )}
        </div>
      </div>
      
      {/* Mobile Overlay */}
      {isDrawerOpen && (
        <div 
          className="drawer-overlay" 
          onClick={() => setIsDrawerOpen(false)}
          aria-label="Close menu"
        />
      )}
    </>
  );
}
