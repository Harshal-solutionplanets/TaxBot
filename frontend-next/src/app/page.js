"use client"

import { useState, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import ChatArea from '@/components/ChatArea';

export default function Home() {
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [theme, setTheme] = useState('light');
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  
  // Theme Toggle Effect
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };// Lock body scroll when sidebar is open (Mobile)
  useEffect(() => {
    if (typeof window === "undefined") return;
  
    if (isDrawerOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
  
    return () => {
      document.body.style.overflow = "";
    };
  }, [isDrawerOpen]);
  
  // Close drawer automatically on desktop
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 768) {
        setIsDrawerOpen(false);
      }
    };
  
    window.addEventListener("resize", handleResize);
  
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  return (
    <div className="app-container">
      <Sidebar 
        activeSessionId={activeSessionId} 
        setActiveSessionId={setActiveSessionId} 
        theme={theme}
        toggleTheme={toggleTheme}
        isDrawerOpen={isDrawerOpen}
        setIsDrawerOpen={setIsDrawerOpen}
      />
      <ChatArea 
        activeSessionId={activeSessionId} 
        setActiveSessionId={setActiveSessionId} 
        isDrawerOpen={isDrawerOpen}
        setIsDrawerOpen={setIsDrawerOpen}
        theme={theme}
        toggleTheme={toggleTheme}
      />
    </div>
  );
}
