import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import MarkdownRenderer from './MarkdownRenderer';

interface Message {
  type: 'human' | 'ai';
  content: string;
}

interface ChatResponse {
  response: string;
  sources: string[];
}

const FloatingChatbot: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [email, setEmail] = useState<string>('');
  const [isEmailConfirmed, setIsEmailConfirmed] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8010';

  // Load email from localStorage on mount
  useEffect(() => {
    const storedEmail = localStorage.getItem('dietguard_user_email');
    if (storedEmail) {
      setEmail(storedEmail);
      setIsEmailConfirmed(true);
      loadChatHistory(storedEmail);
    }
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadChatHistory = async (userEmail: string) => {
    try {
      const response = await axios.get(`${API_URL}/api/chat/history/${userEmail}`);
      if (response.data.messages && response.data.messages.length > 0) {
        setMessages(response.data.messages);
      }
    } catch (err) {
      console.error('Error loading chat history:', err);
    }
  };

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim() && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      localStorage.setItem('dietguard_user_email', email);
      setError(null);
      setIsEmailConfirmed(true);
      loadChatHistory(email);
      setIsOpen(true); // Open chatbot after email is provided
    } else {
      setError('Please enter a valid email address');
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!inputMessage.trim()) return;

    const userMessage: Message = {
      type: 'human',
      content: inputMessage
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.post<ChatResponse>(`${API_URL}/api/chat`, {
        email: email,
        message: inputMessage
      });

      const aiMessage: Message = {
        type: 'ai',
        content: response.data.response
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (err: any) {
      console.error('Error sending message:', err);
      setError(err.response?.data?.detail || 'Failed to send message. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = async () => {
    if (!email) return;

    if (window.confirm('Are you sure you want to clear your chat history?')) {
      try {
        await axios.delete(`${API_URL}/api/chat/history/${email}`);
        setMessages([]);
        // Optional: clear email from local storage to force re-login if desired behavior
        // localStorage.removeItem('dietguard_user_email');
        // setEmail('');
        // setIsEmailConfirmed(false);
      } catch (err) {
        console.error('Error clearing history:', err);
        setError('Failed to clear history');
      }
    }
  };

  const toggleOpen = () => {
    setIsOpen(!isOpen);
  };

  // Show email modal if no email is stored
  if (!isEmailConfirmed) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
          <h3 className="text-2xl font-bold text-gray-800 mb-4">Welcome to Medical Assistant</h3>
          <p className="text-gray-600 mb-6">Please enter your email to start chatting with our medical and nutrition specialist.</p>
          <form onSubmit={handleEmailSubmit}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent mb-4"
              required
              autoFocus
            />
            {error && <p className="text-red-500 text-sm mb-4">{error}</p>}
            <button
              type="submit"
              className="w-full px-4 py-3 bg-gradient-to-r from-blue-500 to-green-500 text-white rounded-lg hover:shadow-lg transition-all font-semibold"
            >
              Start Chat
            </button>
          </form>
        </div>
      </div>
    );
  }

  if (!isOpen) {
    return (
      <button
        onClick={toggleOpen}
        className="fixed bottom-6 right-6 w-16 h-16 bg-gradient-to-r from-blue-500 to-green-500 rounded-full shadow-2xl hover:shadow-3xl transition-all duration-300 flex items-center justify-center text-white hover:scale-110 z-50"
        aria-label="Open Medical Chatbot"
      >
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
      </button>
    );
  }

  return (
    <div
      className={`fixed bottom-6 right-6 bg-white rounded-2xl shadow-2xl flex flex-col z-50 transition-all duration-300 ${isExpanded ? 'w-[600px] h-[700px]' : 'w-96 h-[500px]'
        }`}
      style={{ maxWidth: 'calc(100vw - 48px)', maxHeight: 'calc(100vh - 48px)' }}
    >
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-500 to-green-500 text-white p-4 rounded-t-2xl flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-white bg-opacity-20 rounded-full flex items-center justify-center">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h3 className="font-semibold">Dr. Sarah Mitchell</h3>
            <p className="text-xs opacity-90">Medical & Nutrition Specialist</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition-colors"
            title={isExpanded ? 'Minimize' : 'Expand'}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {isExpanded ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              )}
            </svg>
          </button>
          <button
            onClick={toggleOpen}
            className="p-2 hover:bg-white hover:bg-opacity-20 rounded-lg transition-colors"
            title="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="bg-blue-50 border-l-4 border-blue-500 p-3 text-xs text-blue-800">
        <strong>Note:</strong> I specialize in medical topics, nutrition, and healthy meal planning only.
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <p className="mb-4">👋 Hello! I'm Dr. Sarah Mitchell.</p>
            <p className="text-sm">Ask me about medical conditions, nutrition, or healthy meal planning!</p>
          </div>
        )}

        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.type === 'human' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${msg.type === 'human'
                ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
                : 'bg-gray-100 text-gray-800'
                }`}
            >
              {msg.type === 'human' ? (
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              ) : (
                <MarkdownRenderer content={msg.content} className="text-sm" />
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-3">
              <div className="flex gap-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border-l-4 border-red-500 p-3 text-sm text-red-800">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t p-4">
        <div className="flex gap-2 mb-2">
          <button
            onClick={handleClearHistory}
            className="text-xs text-gray-500 hover:text-red-600 transition-colors"
            disabled={messages.length === 0}
          >
            Clear History
          </button>
        </div>
        <form onSubmit={handleSendMessage} className="flex gap-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            placeholder="Ask about medical topics, nutrition, or meal plans..."
            className="flex-1 px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !inputMessage.trim()}
            className="px-6 py-3 bg-gradient-to-r from-blue-500 to-green-500 text-white rounded-xl hover:shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </form>
      </div>
    </div>
  );
};

export default FloatingChatbot;
