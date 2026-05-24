import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import api from '../services/api';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';

// --- Icon Components ---
const GithubIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
  </svg>
);

const TrashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
  </svg>
);

const Spinner = ({ small }) => (
  <span className={`${small ? 'w-3 h-3' : 'w-5 h-5'} border-2 border-white/30 border-t-white rounded-full animate-spin inline-block`}></span>
);

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

  // File delete state
  const [confirmDeleteFileId, setConfirmDeleteFileId] = useState(null);
  const [deletingFileId, setDeletingFileId] = useState(null);

  // GitHub import state
  const [isGithubModalOpen, setIsGithubModalOpen] = useState(false);
  const [githubUrl, setGithubUrl] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

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

  const handleDeleteFile = async (fileId) => {
    setDeletingFileId(fileId);
    try {
      await api.delete(`/files/project/${projectId}/file/${fileId}`);
      const updatedFiles = files.filter(f => f.id !== fileId);
      setFiles(updatedFiles);
      if (activeFile?.id === fileId) {
        setActiveFile(updatedFiles.length > 0 ? updatedFiles[0] : null);
      }
    } catch (err) {
      console.error('Delete file failed', err);
    } finally {
      setDeletingFileId(null);
      setConfirmDeleteFileId(null);
    }
  };

  const handleGithubImport = async (e) => {
    e.preventDefault();
    if (!githubUrl.trim()) return;
    setIsImporting(true);
    setImportResult(null);
    try {
      const res = await api.post(`/files/upload/github/${projectId}`, { repo_url: githubUrl.trim() });
      setImportResult({ success: true, data: res.data });
      fetchFiles();
    } catch (err) {
      const detail = err.response?.data?.detail || 'Import failed. Please check the URL and try again.';
      setImportResult({ success: false, message: detail });
    } finally {
      setIsImporting(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    
    setIsSearching(true);
    setShowSearch(true);
    try {
      const res = await api.post('/search', { query: searchQuery, project_id: projectId, top_k: 8 });
      setSearchResults(res.data.results);
    } catch (err) {
      console.error('Search failed', err);
    } finally {
      setIsSearching(false);
    }
  };

  const handleJumpToFile = (result) => {
    const filename = result.metadata?.filename;
    if (!filename) return;
    const file = files.find(f => f.filename === filename);
    if (file) {
      setActiveFile(file);
      setShowSearch(false);
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

  const getLanguage = (filename) => {
    const ext = filename?.split('.').pop()?.toLowerCase();
    const langMap = { js: 'javascript', jsx: 'javascript', ts: 'typescript', tsx: 'typescript', py: 'python', rs: 'rust', go: 'go', java: 'java', cs: 'csharp', cpp: 'cpp', c: 'c', rb: 'ruby', php: 'php', md: 'markdown', json: 'json', yaml: 'yaml', yml: 'yaml' };
    return langMap[ext] || 'plaintext';
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
    <div className="flex h-full -m-6">
      {/* File Explorer - Left Sidebar */}
      <div className="w-64 bg-gray-900 border-r border-gray-700 flex flex-col h-full">
        <div className="p-3 border-b border-gray-700 flex flex-col gap-2">
          {/* Upload File Button */}
          <label className="w-full flex justify-center items-center py-2 px-3 border border-transparent text-sm font-medium rounded-md text-white bg-gray-800 hover:bg-gray-700 cursor-pointer transition-colors">
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Upload File
            <input type="file" className="hidden" onChange={handleFileUpload} />
          </label>

          {/* Import GitHub Repo Button */}
          <button
            onClick={() => { setIsGithubModalOpen(true); setImportResult(null); setGithubUrl(''); }}
            className="w-full flex justify-center items-center py-2 px-3 border border-transparent text-sm font-medium rounded-md text-white bg-gray-800 hover:bg-purple-800/60 hover:border-purple-700 cursor-pointer transition-colors gap-2"
          >
            <GithubIcon />
            Import GitHub Repo
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <h3 className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">Explorer</h3>
          <ul className="space-y-0.5">
            {files.map(f => (
              <li key={f.id} className="group relative">
                <button
                  onClick={() => { setActiveFile(f); setShowSearch(false); }}
                  className={`w-full text-left px-4 py-1.5 pr-8 text-sm truncate transition-colors ${
                    activeFile?.id === f.id && !showSearch
                      ? 'bg-blue-600/20 text-blue-400 border-l-2 border-blue-500' 
                      : 'text-gray-400 hover:text-white hover:bg-gray-800 border-l-2 border-transparent'
                  }`}
                >
                  <span className="mr-2">📄</span>
                  {f.filename}
                </button>
                {/* Delete file button */}
                <button
                  onClick={() => setConfirmDeleteFileId(f.id)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded text-gray-700 hover:text-red-400 hover:bg-red-400/10 opacity-0 group-hover:opacity-100 transition-all"
                  title="Delete file"
                >
                  {deletingFileId === f.id ? <Spinner small /> : <TrashIcon />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Main Area - Editor & Search Results */}
      <div className="flex-1 flex flex-col bg-[#1e1e1e] h-full overflow-hidden">
        {/* Top Search Bar */}
        <div className="h-14 border-b border-gray-800 bg-gray-900 flex items-center px-4 gap-3">
          <form onSubmit={handleSearch} className="w-full max-w-2xl relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              {isSearching ? (
                <span className="w-4 h-4 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
              ) : (
                <svg className="h-4 w-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              )}
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search across your codebase… e.g. 'authentication middleware'"
              className="block w-full pl-10 pr-8 py-2 border border-gray-700 rounded-md leading-5 bg-gray-800 text-gray-300 placeholder-gray-600 focus:outline-none focus:bg-gray-700 focus:border-blue-500 focus:ring-blue-500 sm:text-sm transition-colors"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => { setSearchQuery(''); setShowSearch(false); }}
                className="absolute inset-y-0 right-2 flex items-center text-gray-500 hover:text-gray-300"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            )}
          </form>
          <span className="text-xs text-gray-600 whitespace-nowrap hidden lg:block">Press Enter to search</span>
        </div>

        <div className="flex-1 overflow-hidden relative">
          {showSearch ? (
            <div className="absolute inset-0 bg-gray-900 overflow-y-auto p-6 z-10">
              <div className="flex justify-between items-center mb-2">
                <div>
                  <h2 className="text-xl font-semibold text-white">Search Results</h2>
                  {!isSearching && searchResults.length > 0 && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      {searchResults.length} results · Hybrid retrieval (Vector + BM25)
                    </p>
                  )}
                </div>
                <button
                  onClick={() => setShowSearch(false)}
                  className="text-gray-500 hover:text-white transition-colors p-1 hover:bg-gray-800 rounded-md"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>
              </div>

              {isSearching ? (
                <div className="space-y-4 mt-6">
                  {[1, 2, 3].map(i => (
                    <div key={i} className="bg-gray-800 border border-gray-700 rounded-xl p-4 animate-pulse">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="h-3 bg-gray-700 rounded w-1/3"></div>
                        <div className="h-3 bg-gray-700 rounded w-16 ml-auto"></div>
                      </div>
                      <div className="h-24 bg-gray-700/50 rounded-lg w-full mb-3"></div>
                      <div className="h-2 bg-gray-700 rounded w-full"></div>
                    </div>
                  ))}
                </div>
              ) : searchResults.length > 0 ? (
                <div className="space-y-4 mt-4">
                  {searchResults.map((result, idx) => {
                    const meta = result.metadata || {};
                    const vScore = result.vector_score ?? 0;
                    const bScore = result.bm25_score ?? 0;
                    const total = vScore + bScore || 1;
                    const vPct = Math.round((vScore / total) * 100);
                    const bPct = 100 - vPct;
                    const dominant = vScore >= bScore ? 'semantic' : 'keyword';
                    const fnName = meta.function_name || meta.class_name || null;
                    const chunkType = meta.chunk_type || null;
                    const lang = meta.language || null;

                    return (
                      <motion.div
                        key={idx}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: idx * 0.04 }}
                        className="bg-gray-800 rounded-xl border border-gray-700 hover:border-gray-500 transition-colors overflow-hidden"
                      >
                        {/* Header */}
                        <div className="px-4 py-2.5 bg-gray-900/80 border-b border-gray-700 flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-xs font-mono text-blue-400 truncate max-w-[260px]" title={meta.filename}>
                              📄 {meta.filename || 'unknown'}
                            </span>
                            {fnName && (
                              <span className="text-xs text-purple-400 font-mono bg-purple-900/20 border border-purple-800/40 px-1.5 py-0.5 rounded truncate max-w-[140px]" title={fnName}>
                                ƒ {fnName}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 flex-shrink-0">
                            {lang && (
                              <span className="text-[10px] text-gray-400 bg-gray-700 px-1.5 py-0.5 rounded font-mono uppercase tracking-wide">
                                {lang}
                              </span>
                            )}
                            {chunkType && (
                              <span className="text-[10px] text-gray-400 bg-gray-700 px-1.5 py-0.5 rounded capitalize">
                                {chunkType.replace('_', ' ')}
                              </span>
                            )}
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                              dominant === 'semantic'
                                ? 'text-blue-300 bg-blue-900/30 border border-blue-800/40'
                                : 'text-yellow-300 bg-yellow-900/30 border border-yellow-800/40'
                            }`}>
                              {dominant === 'semantic' ? '🔍 Semantic' : '🔑 Keyword'}
                            </span>
                          </div>
                        </div>

                        {/* Code Content */}
                        <div className="p-4 overflow-x-auto">
                          <pre className="text-xs text-gray-300 font-mono leading-relaxed whitespace-pre-wrap break-all max-h-48 overflow-y-auto">
                            <code>{result.content}</code>
                          </pre>
                        </div>

                        {/* Score Footer */}
                        <div className="px-4 pb-3 border-t border-gray-700/50 pt-3">
                          <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[10px] text-gray-500 uppercase tracking-wide">Retrieval score breakdown</span>
                            <div className="flex items-center gap-3 text-[10px] text-gray-500">
                              <span className="text-blue-400">Vector {vPct}%</span>
                              <span className="text-yellow-400">BM25 {bPct}%</span>
                              <span className="text-gray-400">Fusion {result.score.toFixed(5)}</span>
                            </div>
                          </div>
                          <div className="h-1.5 rounded-full bg-gray-700 flex overflow-hidden">
                            <div
                              className="h-full bg-blue-500 transition-all"
                              style={{ width: `${vPct}%` }}
                            />
                            <div
                              className="h-full bg-yellow-500 transition-all"
                              style={{ width: `${bPct}%` }}
                            />
                          </div>
                          <div className="flex justify-end mt-2">
                            <button
                              onClick={() => handleJumpToFile(result)}
                              className="text-[11px] text-gray-500 hover:text-blue-400 transition-colors flex items-center gap-1"
                            >
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                              Open in editor
                            </button>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center mt-16 text-center">
                  <svg className="w-12 h-12 text-gray-700 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                  <p className="text-gray-400 font-medium">No results found</p>
                  <p className="text-gray-600 text-sm mt-1">Try a different query or upload more files.</p>
                </div>
              )}
            </div>
          ) : (
            activeFile ? (
              <Editor
                height="100%"
                theme="vs-dark"
                path={activeFile.filename}
                defaultLanguage={getLanguage(activeFile.filename)}
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
                Upload a file or import a GitHub repo to get started.
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

      {/* Confirm Delete File Modal */}
      <AnimatePresence>
        {confirmDeleteFileId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-gray-800 rounded-xl shadow-2xl max-w-sm w-full border border-red-900/50 p-6"
            >
              <h3 className="text-base font-semibold text-white mb-2">Delete File</h3>
              <p className="text-sm text-gray-400 mb-4">
                This will permanently remove the file and all its vector embeddings from this project. This cannot be undone.
              </p>
              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setConfirmDeleteFileId(null)}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => handleDeleteFile(confirmDeleteFileId)}
                  disabled={deletingFileId === confirmDeleteFileId}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                >
                  {deletingFileId === confirmDeleteFileId ? <><Spinner small />Deleting...</> : 'Delete File'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* GitHub Import Modal */}
      <AnimatePresence>
        {isGithubModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-gray-800 rounded-xl shadow-2xl max-w-lg w-full border border-purple-900/50 p-6"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-lg bg-purple-500/20 flex items-center justify-center text-purple-400">
                  <GithubIcon />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-white">Import GitHub Repository</h3>
                  <p className="text-xs text-gray-400">All supported code files will be parsed and indexed.</p>
                </div>
              </div>

              <form onSubmit={handleGithubImport} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-1">Repository URL</label>
                  <input
                    type="url"
                    required
                    value={githubUrl}
                    onChange={(e) => setGithubUrl(e.target.value)}
                    placeholder="https://github.com/owner/repository"
                    className="w-full bg-gray-900 border border-gray-700 rounded-md py-2.5 px-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
                    disabled={isImporting}
                  />
                  <p className="text-xs text-gray-500 mt-1">Only public repositories are supported.</p>
                </div>

                {/* Result Message */}
                {importResult && (
                  <div className={`p-3 rounded-lg text-sm ${importResult.success ? 'bg-green-900/30 border border-green-700/50 text-green-300' : 'bg-red-900/30 border border-red-700/50 text-red-300'}`}>
                    {importResult.success ? (
                      <>
                        <p className="font-medium">✅ Import Successful!</p>
                        <p className="mt-1 text-green-400/80">{importResult.data.files_imported} files imported, {importResult.data.files_skipped} skipped.</p>
                      </>
                    ) : (
                      <>
                        <p className="font-medium">❌ Import Failed</p>
                        <p className="mt-1">{importResult.message}</p>
                      </>
                    )}
                  </div>
                )}

                <div className="flex justify-end space-x-3 pt-2">
                  <button
                    type="button"
                    onClick={() => { setIsGithubModalOpen(false); setImportResult(null); }}
                    className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm font-medium transition-colors"
                    disabled={isImporting}
                  >
                    {importResult?.success ? 'Close' : 'Cancel'}
                  </button>
                  {!importResult?.success && (
                    <button
                      type="submit"
                      disabled={isImporting || !githubUrl.trim()}
                      className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-md text-sm font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                      {isImporting ? (
                        <><Spinner small />Importing (this may take a minute)...</>
                      ) : (
                        <><GithubIcon /> Import Repository</>
                      )}
                    </button>
                  )}
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ProjectView;
