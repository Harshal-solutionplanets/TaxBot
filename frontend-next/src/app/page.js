"use client"

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import ChatArea from '@/components/ChatArea';

export default function Home() {
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [theme, setTheme] = useState('light');
  
  // Theme Toggle Effect
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <div className="app-container">
      <Sidebar 
        activeSessionId={activeSessionId} 
        setActiveSessionId={setActiveSessionId} 
        theme={theme}
        toggleTheme={toggleTheme}
      />
      <ChatArea 
        activeSessionId={activeSessionId} 
        setActiveSessionId={setActiveSessionId} 
      />
    </div>
  );
}
