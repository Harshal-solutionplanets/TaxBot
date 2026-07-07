"use client"

import { useState, useEffect, useRef } from 'react';

const API_URL = 'http://127.0.0.1:8000';

export default function AdminPanel() {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [logs, setLogs] = useState([]);
  const [uploadResult, setUploadResult] = useState(null);
  const fileInputRef = useRef(null);
  const logsEndRef = useRef(null);

  // Fetch file list
  const fetchFiles = () => {
    fetch(`${API_URL}/api/admin/files`)
      .then(res => res.json())
      .then(data => setFiles(data))
      .catch(err => console.error("Failed to fetch files", err));
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Upload files
  const handleUpload = async () => {
    const input = fileInputRef.current;
    if (!input || !input.files || input.files.length === 0) return;

    setUploading(true);
    setUploadResult(null);

    const formData = new FormData();
    for (const file of input.files) {
      formData.append('files', file);
    }

    try {
      const res = await fetch(`${API_URL}/api/admin/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      setUploadResult(data);
      fetchFiles();
      input.value = '';
    } catch (err) {
      setUploadResult({ status: 'error', errors: ['Network error: ' + err.message] });
    } finally {
      setUploading(false);
    }
  };

  // Delete a file
  const handleDelete = async (filename) => {
    if (!confirm(`Delete "${filename}" from the data directory?`)) return;
    try {
      await fetch(`${API_URL}/api/admin/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      fetchFiles();
    } catch (err) {
      console.error("Failed to delete file", err);
    }
  };

  // Trigger ingestion with progress streaming
  const handleIngest = async () => {
    if (ingesting) return;
    setIngesting(true);
    setProgressPercent(0);
    setProgressMessage('Starting ingestion pipeline...');
    setLogs([]);

    try {
      const response = await fetch(`${API_URL}/api/admin/ingest`, { method: 'POST' });
      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const data = JSON.parse(line);

            if (data.event === 'progress') {
              setProgressPercent(data.percent);
              setProgressMessage(data.message);
              setLogs(prev => [...prev, { type: 'info', text: data.message }]);
            } else if (data.event === 'complete') {
              setProgressPercent(100);
              setProgressMessage(data.message);
              setLogs(prev => [...prev, { type: 'success', text: data.message }]);
            } else if (data.event === 'error') {
              setProgressMessage(data.message);
              setLogs(prev => [...prev, { type: 'error', text: data.message }]);
            } else if (data.event === 'warning') {
              setLogs(prev => [...prev, { type: 'warning', text: data.message }]);
            }
          } catch (err) {
            console.error("Failed to parse progress line", err);
          }
        }
      }
    } catch (err) {
      setProgressMessage(`Error: ${err.message}`);
      setLogs(prev => [...prev, { type: 'error', text: err.message }]);
    } finally {
      setIngesting(false);
      fetchFiles();
    }
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--bg-color)', color: 'var(--text-primary)', padding: '40px' }}>
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
        
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.8rem' }}>🔧 TaxBot Admin Panel</h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '5px' }}>Manage knowledge base documents and trigger ingestion</p>
          </div>
          <a href="/" style={{ color: 'var(--accent-color)', textDecoration: 'none' }}>← Back to Chat</a>
        </div>

        {/* Upload Section */}
        <div style={{
          backgroundColor: 'var(--sidebar-bg)',
          borderRadius: '12px',
          padding: '24px',
          marginBottom: '24px',
          border: '1px solid var(--border-color)'
        }}>
          <h2 style={{ margin: '0 0 16px 0', fontSize: '1.2rem' }}>📤 Upload Documents</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '16px' }}>
            Supported formats: <strong>PDF</strong>, <strong>PPTX</strong>, <strong>VTT</strong>
          </p>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
            <input
              type="file"
              ref={fileInputRef}
              multiple
              accept=".pdf,.pptx,.ppt,.vtt"
              style={{
                flex: 1,
                padding: '10px',
                borderRadius: '8px',
                border: '1px solid var(--border-color)',
                backgroundColor: 'var(--bg-color)',
                color: 'var(--text-primary)',
                minWidth: '200px'
              }}
            />
            <button
              onClick={handleUpload}
              disabled={uploading}
              style={{
                padding: '10px 24px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: 'var(--accent-color)',
                color: 'white',
                fontWeight: '600',
                cursor: uploading ? 'not-allowed' : 'pointer',
                opacity: uploading ? 0.6 : 1
              }}
            >
              {uploading ? 'Uploading...' : 'Upload Files'}
            </button>
          </div>
          {uploadResult && (
            <div style={{ marginTop: '12px', fontSize: '0.9rem' }}>
              {uploadResult.uploaded?.length > 0 && (
                <p style={{ color: 'var(--success)' }}>✅ Uploaded: {uploadResult.uploaded.join(', ')}</p>
              )}
              {uploadResult.errors?.length > 0 && (
                uploadResult.errors.map((err, i) => (
                  <p key={i} style={{ color: 'var(--error)' }}>❌ {err}</p>
                ))
              )}
            </div>
          )}
        </div>

        {/* Ingestion Section */}
        <div style={{
          backgroundColor: 'var(--sidebar-bg)',
          borderRadius: '12px',
          padding: '24px',
          marginBottom: '24px',
          border: '1px solid var(--border-color)'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ margin: 0, fontSize: '1.2rem' }}>⚙️ Run Ingestion Pipeline</h2>
            <button
              onClick={handleIngest}
              disabled={ingesting}
              style={{
                padding: '10px 24px',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: ingesting ? '#6b7280' : '#10b981',
                color: 'white',
                fontWeight: '600',
                cursor: ingesting ? 'not-allowed' : 'pointer'
              }}
            >
              {ingesting ? '⏳ Ingesting...' : '🚀 Start Ingestion'}
            </button>
          </div>
          
          {/* Progress Bar */}
          {(ingesting || progressPercent > 0) && (
            <div style={{ marginBottom: '12px' }}>
              <div style={{
                width: '100%',
                height: '24px',
                backgroundColor: 'var(--border-color)',
                borderRadius: '12px',
                overflow: 'hidden',
                position: 'relative'
              }}>
                <div style={{
                  width: `${progressPercent}%`,
                  height: '100%',
                  backgroundColor: progressPercent >= 100 ? '#10b981' : '#3b82f6',
                  borderRadius: '12px',
                  transition: 'width 0.5s ease-in-out',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{ color: 'white', fontSize: '0.75rem', fontWeight: '600' }}>
                    {progressPercent}%
                  </span>
                </div>
              </div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '8px' }}>
                {progressMessage}
              </p>
            </div>
          )}

          {/* Ingestion Logs */}
          {logs.length > 0 && (
            <div style={{
              backgroundColor: 'var(--bg-color)',
              borderRadius: '8px',
              padding: '12px',
              maxHeight: '200px',
              overflowY: 'auto',
              fontFamily: 'monospace',
              fontSize: '0.8rem',
              border: '1px solid var(--border-color)'
            }}>
              {logs.map((log, i) => (
                <div key={i} style={{
                  color: log.type === 'error' ? 'var(--error)' :
                         log.type === 'success' ? 'var(--success)' :
                         log.type === 'warning' ? '#f59e0b' :
                         'var(--text-secondary)',
                  marginBottom: '4px'
                }}>
                  {log.type === 'error' ? '❌' : log.type === 'success' ? '✅' : log.type === 'warning' ? '⚠️' : '📌'} {log.text}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          )}
        </div>

        {/* File List */}
        <div style={{
          backgroundColor: 'var(--sidebar-bg)',
          borderRadius: '12px',
          padding: '24px',
          border: '1px solid var(--border-color)'
        }}>
          <h2 style={{ margin: '0 0 16px 0', fontSize: '1.2rem' }}>
            📚 Knowledge Base ({files.length} files)
          </h2>

          {files.length === 0 ? (
            <p style={{ color: 'var(--text-secondary)' }}>No documents in the knowledge base yet. Upload some files above.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border-color)', textAlign: 'left' }}>
                  <th style={{ padding: '10px 8px', color: 'var(--text-secondary)', fontWeight: '500', fontSize: '0.85rem' }}>File Name</th>
                  <th style={{ padding: '10px 8px', color: 'var(--text-secondary)', fontWeight: '500', fontSize: '0.85rem' }}>Type</th>
                  <th style={{ padding: '10px 8px', color: 'var(--text-secondary)', fontWeight: '500', fontSize: '0.85rem' }}>Size</th>
                  <th style={{ padding: '10px 8px', color: 'var(--text-secondary)', fontWeight: '500', fontSize: '0.85rem' }}>Uploaded</th>
                  <th style={{ padding: '10px 8px', color: 'var(--text-secondary)', fontWeight: '500', fontSize: '0.85rem' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td style={{ padding: '12px 8px', fontSize: '0.9rem' }}>{file.filename}</td>
                    <td style={{ padding: '12px 8px' }}>
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '0.75rem',
                        fontWeight: '600',
                        backgroundColor: file.type === 'PDF' ? '#dbeafe' : file.type === 'VTT' ? '#d1fae5' : '#fef3c7',
                        color: file.type === 'PDF' ? '#1e40af' : file.type === 'VTT' ? '#065f46' : '#92400e'
                      }}>
                        {file.type}
                      </span>
                    </td>
                    <td style={{ padding: '12px 8px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{file.size_mb} MB</td>
                    <td style={{ padding: '12px 8px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {new Date(file.uploaded_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '12px 8px' }}>
                      <button
                        onClick={() => handleDelete(file.filename)}
                        style={{
                          background: 'none',
                          border: '1px solid var(--error)',
                          color: 'var(--error)',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          cursor: 'pointer',
                          fontSize: '0.8rem'
                        }}
                      >
                        🗑️ Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
