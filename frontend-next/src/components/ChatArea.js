import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';

const API_URL = 'http://127.0.0.1:8000';

export default function ChatArea({ activeSessionId, setActiveSessionId, isDrawerOpen, setIsDrawerOpen, theme, toggleTheme }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [followups, setFollowups] = useState([]);
  const messagesEndRef = useRef(null);

  // Scroll to bottom on new message or loading change
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  // Load session messages
  useEffect(() => {
    if (activeSessionId) {
      fetch(`${API_URL}/api/sessions/${activeSessionId}/messages`)
        .then(res => res.json())
        .then(data => setMessages(data))
        .catch(err => {
          console.error("Failed to load messages", err);
          setMessages([]);
        });
    } else {
      setMessages([]);
    }
  }, [activeSessionId]);

  // Generate smart follow-up suggestions dynamically
  useEffect(() => {
    if (messages.length > 0 && messages[messages.length - 1].role === 'assistant' && !isLoading) {
      const historyPayload = messages.map(m => ({ role: m.role, content: m.content }));
      fetch(`${API_URL}/api/query/suggest-followups`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ conversation_history: historyPayload })
      })
        .then(res => res.json())
        .then(data => setFollowups(data))
        .catch(err => console.error("Failed to fetch followups", err));
    } else {
      setFollowups([]);
    }
  }, [messages, isLoading]);

  const triggerQuery = async (userMessage) => {
    if (!userMessage.trim() || isLoading) return;

    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/api/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          question: userMessage,
          session_id: activeSessionId
        })
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      setIsLoading(false);

      // Add a placeholder message for streaming content
      const assistantMessageId = 'temp-' + Date.now();
      setMessages(prev => [...prev, {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        source: ''
      }]);

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let currentContent = '';
      let currentSource = '';
      let currentSessionId = activeSessionId;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Save the last incomplete line
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);
            if (data.event === 'metadata') {
              currentSource = data.source;
              if (data.session_id && data.session_id !== currentSessionId) {
                currentSessionId = data.session_id;
                setActiveSessionId(data.session_id);
              }
              setMessages(prev => prev.map(msg => 
                msg.id === assistantMessageId 
                  ? { ...msg, source: currentSource }
                  : msg
              ));
            } else if (data.event === 'content') {
              currentContent += data.text;
              setMessages(prev => prev.map(msg => 
                msg.id === assistantMessageId 
                  ? { ...msg, content: currentContent }
                  : msg
              ));
            }
          } catch (err) {
            console.error("Failed to parse JSON stream line", err);
          }
        }
      }

      // Fetch official messages from backend to swap out temp IDs
      if (currentSessionId) {
        const fetchRes = await fetch(`${API_URL}/api/sessions/${currentSessionId}/messages`);
        const finalMessages = await fetchRes.json();
        setMessages(finalMessages);
      }

    } catch (err) {
      console.error(err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '⚠️ Backend Error: Failed to fetch response. Make sure the backend is running.'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const userMessage = input.trim();
    setInput('');
    triggerQuery(userMessage);
  };

  const handleFollowupClick = (question) => {
    triggerQuery(question);
  };

  const handleFeedback = async (messageId, status) => {
    if (!messageId || String(messageId).startsWith('temp-')) return;
    try {
      const res = await fetch(`${API_URL}/api/messages/${messageId}/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ feedback: status })
      });
      if (res.ok) {
        setMessages(prev => prev.map(msg => 
          msg.id === messageId 
            ? { ...msg, feedback: status }
            : msg
        ));
      }
    } catch (err) {
      console.error("Failed to submit feedback", err);
    }
  };

  const exportToMarkdown = () => {
    if (messages.length === 0) return;
    let mdContent = `# TaxBot Conversation Export\nGenerated on: ${new Date().toLocaleString()}\n\n---\n\n`;
    messages.forEach((msg) => {
      const roleName = msg.role === 'user' ? 'User (CA)' : 'Assistant (TaxBot)';
      mdContent += `### **${roleName}**\n\n${msg.content}\n\n`;
      if (msg.source && msg.source !== 'None') {
        mdContent += `*Sources: ${msg.source}*\n\n`;
      }
      mdContent += `---\n\n`;
    });

    const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `TaxBot_Chat_${activeSessionId || 'export'}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="chat-area">
      <div className="chat-header">
        <div className="chat-header-content">
          <button 
            className="hamburger-btn" 
            onClick={() => setIsDrawerOpen(true)}
            aria-label="Open Menu"
          >
            ☰
          </button>
          
          <div className="chat-title-container">
            <h2 className="desktop-title">⚖️ Income Tax Act - Assistant</h2>
            <h2 className="mobile-title">TaxBot</h2>
            <p className="desktop-subtitle">AI-powered verification engine for Chartered Accountants. All answers are strictly grounded in active updates.</p>
          </div>
          
          <div className="chat-header-actions">
            <button onClick={toggleTheme} className="theme-toggle mobile-theme-toggle" aria-label="Toggle Theme">
              {theme === 'light' ? '🌙' : '☀️'}
            </button>
            {messages.length > 0 && (
              <button className="export-btn" onClick={exportToMarkdown}>
                📤 <span className="hide-on-mobile">Export Markdown</span>
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="messages-container">
        {messages.length === 0 && !isLoading && (
          <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '2rem' }}>
            No messages yet. Ask a tax question to start!
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={idx} className={`message-wrapper ${msg.role}`}>
            <div className="message-bubble">
              {msg.role === 'assistant' ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
            {msg.source && msg.source !== 'None' && (
              <div className="message-source">
                <strong>Verified Source:</strong> {msg.source}
              </div>
            )}
            
            {msg.role === 'assistant' && msg.id && !String(msg.id).startsWith('temp-') && (
              <div className="feedback-buttons" style={{ display: 'flex', gap: '5px', marginTop: '6px', alignSelf: 'flex-start' }}>
                <button 
                  onClick={() => handleFeedback(msg.id, msg.feedback === 'up' ? 'none' : 'up')}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    opacity: msg.feedback === 'up' ? 1.0 : 0.4,
                    filter: msg.feedback === 'up' ? 'grayscale(0%)' : 'grayscale(100%)',
                    transition: 'opacity 0.2s'
                  }}
                  title="Thumbs up"
                >
                  👍
                </button>
                <button 
                  onClick={() => handleFeedback(msg.id, msg.feedback === 'down' ? 'none' : 'down')}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    opacity: msg.feedback === 'down' ? 1.0 : 0.4,
                    filter: msg.feedback === 'down' ? 'grayscale(0%)' : 'grayscale(100%)',
                    transition: 'opacity 0.2s'
                  }}
                  title="Thumbs down"
                >
                  👎
                </button>
              </div>
            )}
          </div>
        ))}
        
        {isLoading && (
          <div className="message-wrapper assistant">
            <div className="message-bubble typing-indicator">
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
              <div className="typing-dot"></div>
            </div>
          </div>
        )}

        {followups.length > 0 && (
          <div className="followups-container" style={{ marginTop: '1rem', animation: 'fadeIn 0.5s' }}>
            <p className="followups-label" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>💡 Suggested Questions:</p>
            <div className="followups-list" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {followups.map((q, idx) => (
                <button 
                  key={idx} 
                  className="followup-pill" 
                  onClick={() => handleFollowupClick(q)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '16px',
                    border: '1px solid var(--border-color)',
                    background: 'var(--sidebar-bg)',
                    color: 'var(--text-primary)',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    transition: 'all 0.2s'
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <form onSubmit={handleSubmit} className="input-form">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about recent Income Tax Act changes..."
            disabled={isLoading}
          />
          <button type="submit" className="send-btn" disabled={!input.trim() || isLoading} aria-label="Send">
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
          </button>
        </form>
      </div>
    </div>
  );
}
