import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';

const ProjectView = () => {
  const { id: projectId } = useParams();
  const [files, setFiles] = useState([]);
  const [activeFile, setActiveFile] = useState(null);
  
  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearch, setShowSearch] = useState(false);

  // Chat state
  const [chatInput, setChatInput] = useState('');
  const [chatHistory, setChatHistory] = useState([
    { role: 'assistant', text: 'Hello! I am your AI coding assistant. Select a file or code snippet, or just ask me a question.' }
  ]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const chatEndRef = useRef(null);
  
  // Editor Ref
  const editorRef = useRef(null);

  useEffect(() => {
    fetchFiles();
  }, [projectId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const fetchFiles = async () => {
    try {
      const res = await api.get(`/files/project/${projectId}/files`);
      setFiles(res.data);
      if (res.data.length > 0 && !activeFile) {
        setActiveFile(res.data[0]);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      await api.post(`/files/upload/${projectId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      fetchFiles();
    } catch (err) {
      console.error('Upload failed', err);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    
    setIsSearching(true);
    setShowSearch(true);
    try {
      const res = await api.post('/search', { query: searchQuery, project_id: projectId });
      setSearchResults(res.data.results);
    } catch (err) {
      console.error('Search failed', err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleEditorDidMount = (editor, monaco) => {
    editorRef.current = editor;
  };

  const getSelectedCode = () => {
    if (!editorRef.current) return '';
    const selection = editorRef.current.getSelection();
    return editorRef.current.getModel().getValueInRange(selection);
  };

  const handleChatSubmit = async (e, action = 'general') => {
    if (e) e.preventDefault();
    const query = chatInput.trim();
    if (!query && action === 'general') return;

    const selectedCode = getSelectedCode();
    
    let userMsg = query;
    if (action !== 'general') {
        userMsg = `Action: ${action.replace('_', ' ')} on selected code.`;
    }

    const newHistory = [...chatHistory, { role: 'user', text: userMsg }];
    setChatHistory(newHistory);
    setChatInput('');
    setIsChatLoading(true);

    try {
      const payload = {
        action,
        code: selectedCode || activeFile?.content || "",
        query,
        project_id: projectId
      };
      const res = await api.post('/chat', payload);
      setChatHistory([...newHistory, { role: 'assistant', text: res.data.response }]);
    } catch (err) {
      console.error(err);
      setChatHistory([...newHistory, { role: 'assistant', text: 'Sorry, I encountered an error.' }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  return (
    <div className="flex h-full -m-6"> {/* Negative margin to offset DashboardLayout padding */}
      {/* File Explorer - Left Sidebar */}
      <div className="w-64 bg-gray-900 border-r border-gray-700 flex flex-col h-full">
        <div className="p-4 border-b border-gray-700">
          <label className="w-full flex justify-center items-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-gray-800 hover:bg-gray-700 cursor-pointer transition-colors">
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Upload File
            <input type="file" className="hidden" onChange={handleFileUpload} />
          </label>
        </div>
        <div className="flex-1 overflow-y-auto">
          <h3 className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Explorer</h3>
          <ul className="space-y-1">
            {files.map(f => (
              <li key={f.id}>
                <button
                  onClick={() => { setActiveFile(f); setShowSearch(false); }}
                  className={`w-full text-left px-4 py-1.5 text-sm truncate transition-colors ${
                    activeFile?.id === f.id && !showSearch
                      ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-500' 
                      : 'text-gray-400 hover:text-white hover:bg-gray-800 border-l-2 border-transparent'
                  }`}
                >
                  <span className="mr-2">📄</span>
                  {f.filename}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Main Area - Editor & Search Results */}
      <div className="flex-1 flex flex-col bg-[#1e1e1e] h-full overflow-hidden">
        {/* Top Search Bar */}
        <div className="h-14 border-b border-gray-800 bg-gray-900 flex items-center px-4">
          <form onSubmit={handleSearch} className="w-full max-w-2xl relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <svg className="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Semantic search across your codebase..."
              className="block w-full pl-10 pr-3 py-2 border border-gray-700 rounded-md leading-5 bg-gray-800 text-gray-300 placeholder-gray-500 focus:outline-none focus:bg-gray-700 focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-colors"
            />
          </form>
        </div>

        <div className="flex-1 overflow-hidden relative">
          {showSearch ? (
            <div className="absolute inset-0 bg-gray-900 overflow-y-auto p-6 z-10">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold text-white">Search Results</h2>
                <button onClick={() => setShowSearch(false)} className="text-gray-400 hover:text-white">
                  Close ✕
                </button>
              </div>
              
              {isSearching ? (
                <div className="animate-pulse space-y-4">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="bg-gray-800 p-4 rounded-lg">
                      <div className="h-4 bg-gray-700 rounded w-1/4 mb-4"></div>
                      <div className="h-20 bg-gray-700 rounded w-full"></div>
                    </div>
                  ))}
                </div>
              ) : searchResults.length > 0 ? (
                <div className="space-y-6">
                  {searchResults.map((result, idx) => (
                    <div key={idx} className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
                      <div className="bg-gray-900 px-4 py-2 border-b border-gray-700 flex justify-between">
                        <span className="text-sm font-medium text-blue-400">{result.metadata.filename}</span>
                        <span className="text-xs text-gray-500">Score: {result.score.toFixed(4)}</span>
                      </div>
                      <div className="p-4 overflow-x-auto text-sm text-gray-300 font-mono">
                        <pre><code>{result.content}</code></pre>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-gray-400">No results found.</p>
              )}
            </div>
          ) : (
            activeFile ? (
              <Editor
                height="100%"
                theme="vs-dark"
                path={activeFile.filename}
                defaultLanguage={activeFile.filename.split('.').pop() === 'js' ? 'javascript' : activeFile.filename.split('.').pop() === 'py' ? 'python' : 'plaintext'}
                value={activeFile.content}
                onMount={handleEditorDidMount}
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  fontSize: 14,
                  wordWrap: 'on',
                  padding: { top: 16 }
                }}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Select a file from the explorer to view its contents
              </div>
            )
          )}
        </div>
      </div>

      {/* AI Chat Interface - Right Sidebar */}
      <div className="w-80 bg-gray-900 border-l border-gray-700 flex flex-col h-full">
        <div className="h-14 border-b border-gray-800 flex items-center px-4 bg-gray-900">
          <h2 className="text-sm font-semibold text-white flex items-center">
            <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
            AI Assistant
          </h2>
        </div>

        {/* AI Action Buttons */}
        <div className="p-2 border-b border-gray-800 grid grid-cols-2 gap-2 bg-gray-800/50">
          <button onClick={(e) => handleChatSubmit(e, 'explain')} className="text-xs py-1.5 px-2 bg-gray-700 hover:bg-gray-600 rounded text-gray-200 transition-colors">
            Explain Code
          </button>
          <button onClick={(e) => handleChatSubmit(e, 'detect_bugs')} className="text-xs py-1.5 px-2 bg-gray-700 hover:bg-red-900/50 hover:text-red-300 rounded text-gray-200 transition-colors">
            Find Bugs
          </button>
          <button onClick={(e) => handleChatSubmit(e, 'optimize')} className="text-xs py-1.5 px-2 bg-gray-700 hover:bg-green-900/50 hover:text-green-300 rounded text-gray-200 transition-colors col-span-2">
            Optimize Performance
          </button>
        </div>

        {/* Chat History */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {chatHistory.map((msg, idx) => (
            <motion.div 
              key={idx}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <span className="text-[10px] text-gray-500 mb-1 uppercase tracking-wider">{msg.role}</span>
              <div 
                className={`max-w-[95%] rounded-2xl px-4 py-3 text-sm ${
                  msg.role === 'user' 
                    ? 'bg-blue-600 text-white rounded-tr-none' 
                    : 'bg-gray-800 text-gray-200 rounded-tl-none border border-gray-700'
                }`}
              >
                {msg.role === 'user' ? (
                  msg.text
                ) : (
                  <div className="prose prose-invert prose-sm max-w-none prose-pre:bg-gray-900 prose-pre:border prose-pre:border-gray-700">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
            </motion.div>
          ))}
          {isChatLoading && (
            <div className="flex items-start">
               <div className="bg-gray-800 border border-gray-700 rounded-2xl rounded-tl-none px-4 py-3 flex space-x-1">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
               </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Chat Input */}
        <div className="p-3 bg-gray-900 border-t border-gray-700">
          <form onSubmit={(e) => handleChatSubmit(e, 'general')} className="flex relative">
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder="Ask anything..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-3 pr-10 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            />
            <button 
              type="submit"
              disabled={isChatLoading || !chatInput.trim()}
              className="absolute right-2 top-2 p-1 text-blue-500 hover:text-blue-400 disabled:text-gray-600"
            >
              <svg className="w-5 h-5 transform rotate-90" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
              </svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default ProjectView;
