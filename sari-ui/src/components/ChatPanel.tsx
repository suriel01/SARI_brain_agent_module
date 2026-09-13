import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MessageSquarePlus, Edit2, Trash2, PanelLeftOpen, PanelLeftClose } from 'lucide-react';
import { apiFetch, readErrorDetail } from '../api';
import type { Permissions } from '../permissions';
import { useLanguage } from '../i18n/LanguageContext';

interface ChatPanelProps {
  token: string;
  permissions: Permissions;
  requestPin: (actionName: string, callback: (pin: string) => void) => void;
  fetchState: () => void;
  lastAlertThreadId?: number | null;
}

interface Message {
  role: 'user' | 'agent' | 'system';
  content: string;
  created_at?: string;
  timestamp?: string;
  snapshot?: string;
}

const formatMessageTimestamp = (dateStr?: string) => {
  if (!dateStr) return '';
  let iso = dateStr.replace(' ', 'T');
  const timePart = iso.split('T')[1] || '';
  const hasTimezone = timePart.includes('Z') || timePart.includes('+') || (timePart.includes('-') && timePart.lastIndexOf('-') > 0);
  if (!hasTimezone) {
    iso = `${iso}Z`;
  }
  const d = new Date(iso);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
};

const formatInlineText = (text: string, isUser = false) => {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong 
          key={i} 
          className={isUser ? "font-black text-white dark:text-black" : "font-bold text-zinc-950 dark:text-white"}
        >
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code 
          key={i} 
          className={`px-1.5 py-0.5 rounded text-xs font-mono border ${
            isUser 
              ? 'bg-zinc-800/90 border-zinc-700 text-white dark:bg-zinc-200 dark:border-zinc-300 dark:text-black font-bold' 
              : 'bg-zinc-100 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100'
          }`}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
};

const renderFormattedContent = (text: string, isUser = false) => {
  if (!text) return null;

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let tableBuffer: string[] = [];

  const flushTable = () => {
    if (tableBuffer.length < 2) {
      tableBuffer.forEach((tblLine, idx) => {
        elements.push(
          <div key={`tbl-raw-${elements.length}-${idx}`} className={isUser ? "text-white dark:text-zinc-950 font-medium" : "text-zinc-800 dark:text-zinc-200"}>
            {formatInlineText(tblLine, isUser)}
          </div>
        );
      });
      tableBuffer = [];
      return;
    }

    const headerLine = tableBuffer[0];
    const rowsLines = tableBuffer.slice(2);

    const parseRow = (line: string) => 
      line.split('|').map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);

    const headers = parseRow(headerLine);

    elements.push(
      <div key={`tbl-${elements.length}`} className="overflow-x-auto my-3 rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white/40 dark:bg-zinc-900/60 shadow-sm">
        <table className="w-full border-collapse text-xs text-left">
          <thead>
            <tr className="bg-zinc-100/90 dark:bg-zinc-800/90 border-b border-zinc-200 dark:border-zinc-800 text-zinc-900 dark:text-zinc-100 font-bold">
              {headers.map((h, i) => (
                <th key={i} className="py-2.5 px-3.5 tracking-tight">{formatInlineText(h, false)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowsLines.map((rowLine, rIdx) => {
              const cells = parseRow(rowLine);
              if (cells.length === 0) return null;
              return (
                <tr key={rIdx} className="border-b border-zinc-100 dark:border-zinc-800/50 last:border-0 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 transition-colors">
                  {cells.map((cell, cIdx) => (
                    <td key={cIdx} className="py-2.5 px-3.5 text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap">
                      {formatInlineText(cell, false)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
    tableBuffer = [];
  };

  lines.forEach((line, idx) => {
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      tableBuffer.push(line.trim());
      return;
    }

    if (tableBuffer.length > 0) {
      flushTable();
    }

    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={`h1-${idx}`} className={`text-base font-bold tracking-tight mt-3 mb-2 flex items-center gap-2 ${isUser ? 'text-white dark:text-zinc-950' : 'text-zinc-950 dark:text-white'}`}>
          {formatInlineText(line.slice(2), isUser)}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      elements.push(
        <h2 key={`h2-${idx}`} className={`text-sm font-bold tracking-tight mt-2.5 mb-1.5 ${isUser ? 'text-white dark:text-zinc-950' : 'text-zinc-900 dark:text-zinc-100'}`}>
          {formatInlineText(line.slice(3), isUser)}
        </h2>
      );
    } else if (line.startsWith('### ')) {
      elements.push(
        <h3 key={`h3-${idx}`} className={`text-xs font-bold uppercase tracking-wider mt-2 mb-1 ${isUser ? 'text-white dark:text-zinc-950' : 'text-zinc-700 dark:text-zinc-300'}`}>
          {formatInlineText(line.slice(4), isUser)}
        </h3>
      );
    } else if (line.trim() === '---') {
      elements.push(
        <hr key={`hr-${idx}`} className="my-2.5 border-t border-zinc-200 dark:border-zinc-800" />
      );
    } else if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
      elements.push(
        <div key={`bullet-${idx}`} className="flex items-start gap-2 ml-1 my-1">
          <span className="text-zinc-400 dark:text-zinc-500 font-bold">•</span>
          <span className={isUser ? "text-white dark:text-zinc-950" : "text-zinc-800 dark:text-zinc-200"}>
            {formatInlineText(line.trim().slice(1).trim(), isUser)}
          </span>
        </div>
      );
    } else if (line.trim().length > 0) {
      elements.push(
        <p key={`p-${idx}`} className={`my-1 ${isUser ? 'text-white dark:text-zinc-950 font-medium' : 'text-zinc-800 dark:text-zinc-200'}`}>
          {formatInlineText(line, isUser)}
        </p>
      );
    } else {
      elements.push(<div key={`space-${idx}`} className="h-1" />);
    }
  });

  if (tableBuffer.length > 0) {
    flushTable();
  }

  return elements;
};

export default function ChatPanel({ token, permissions, requestPin, fetchState, lastAlertThreadId }: ChatPanelProps) {
  const { language, t } = useLanguage();
  const [threads, setThreads] = useState<any[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [previewSnapshot, setPreviewSnapshot] = useState<string | null>(null);

  const [sidebarWidth, setSidebarWidth] = useState(240);
  const [isChatsCollapsed, setIsChatsCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);

  const endRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const chatPanelRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [userIsScrolledUp, setUserIsScrolledUp] = useState(false);
  const isSwitchingThreadRef = useRef(false);
  const scrollPositionsRef = useRef<{ [threadId: number]: number }>({});

  const startResizing = () => setIsResizing(true);
  const stopResizing = () => setIsResizing(false);

  const resize = (e: MouseEvent) => {
    if (!isResizing || !chatPanelRef.current) return;
    const offsetLeft = chatPanelRef.current.getBoundingClientRect().left;
    const newWidth = e.clientX - offsetLeft;
    if (newWidth < 80) {
      setIsChatsCollapsed(true);
    } else {
      setIsChatsCollapsed(false);
      setSidebarWidth(Math.min(Math.max(newWidth, 160), 380));
    }
  };

  useEffect(() => {
    if (isResizing) {
      window.addEventListener('mousemove', resize);
      window.addEventListener('mouseup', stopResizing);
    }
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [isResizing]);

  const handleScroll = () => {
    if (!chatContainerRef.current || isSwitchingThreadRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    if (activeThreadId) {
      scrollPositionsRef.current[activeThreadId] = scrollTop;
    }
    const isUp = scrollHeight - scrollTop - clientHeight > 80;
    setUserIsScrolledUp(isUp);
  };

  useEffect(() => {
    fetchThreads();
  }, [token]);

  useEffect(() => {
    if (lastAlertThreadId && lastAlertThreadId !== activeThreadId) {
      setActiveThreadId(lastAlertThreadId);
    }
  }, [lastAlertThreadId]);

  useEffect(() => {
    const wsUrl = window.location.hostname === 'localhost' ? 'ws://localhost:8000/ws' : `ws://${window.location.hostname}:8000/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'new_message' && data.message) {
          const incoming = data.message;
          if (activeThreadId && incoming.thread_id === activeThreadId) {
            setMessages(prev => {
              if (prev.some((m: any) => m.id && m.id === incoming.id)) return prev;
              return [...prev, incoming];
            });
          }
          fetchThreads();
        }
      } catch (e) {
        console.error("Error in WS of ChatPanel:", e);
      }
    };

    return () => ws.close();
  }, [activeThreadId]);

  useEffect(() => {
    if (activeThreadId) {
      isSwitchingThreadRef.current = true;
      fetchMessages(activeThreadId).then(() => {
        setTimeout(() => {
          if (chatContainerRef.current) {
            const savedPos = scrollPositionsRef.current[activeThreadId];
            if (savedPos !== undefined) {
              chatContainerRef.current.scrollTop = savedPos;
              const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
              setUserIsScrolledUp(scrollHeight - scrollTop - clientHeight > 80);
            } else {
              chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
              setUserIsScrolledUp(false);
            }
          }
          isSwitchingThreadRef.current = false;
        }, 50);
      });

      const interval = setInterval(() => {
        fetchMessages(activeThreadId);
      }, 1500);
      return () => clearInterval(interval);
    } else {
      setMessages([{ 
        role: 'system', 
        content: language === 'en' 
          ? 'SOC SYSTEM ACTIVE. TACTICAL AI ONLINE. Select or start a conversation thread.' 
          : 'SISTEMA SOC ACTIVO. IA TÁCTICA ONLINE. Seleccione o inicie un hilo de conversación.' 
      }]);
    }
  }, [activeThreadId, language]);

  useEffect(() => {
    if (!userIsScrolledUp && !isSwitchingThreadRef.current) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const fetchThreads = async () => {
    try {
      const res = await apiFetch('/chat/threads', token);
      if (res.ok) {
        const data = await res.json();
        setThreads(prev => {
          if (JSON.stringify(prev) === JSON.stringify(data)) {
            return prev;
          }
          return data;
        });

        if (data.length > 0) {
          setActiveThreadId(prevId => {
            if (!prevId || !data.some((t: any) => t.id === prevId)) {
              return data[data.length - 1].id;
            }
            return prevId;
          });
        } else {
          setActiveThreadId(null);
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchMessages = async (threadId: number) => {
    try {
      const res = await apiFetch(`/chat/threads/${threadId}/messages`, token);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const startNewThread = () => {
    if (!permissions.canCreateChats) {
      alert('Action restricted: Permission required to create new chat threads.');
      return;
    }
    requestPin('Create Chat Thread', async (pin) => {
      try {
        const res = await apiFetch('/chat/threads', token, {
          method: 'POST',
          body: JSON.stringify({ 
            title: language === 'en' ? 'New Shared Chat' : 'Nuevo Hilo Compartido', 
            pin 
          })
        });
        if (res.ok) {
          const data = await res.json();
          fetchThreads();
          setActiveThreadId(data.id);
        } else {
          alert(await readErrorDetail(res, 'Error creating chat.'));
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  const sendToBackend = async (text: string) => {
    setLoading(true);
    try {
      const payload: any = { message: text, language };
      if (activeThreadId) payload.thread_id = activeThreadId;

      const res = await apiFetch('/chat', token, {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        const agentMsg = await res.json();
        setMessages(prev => {
          if (prev.some((m: any) => m.id && m.id === agentMsg.id)) return prev;
          return [...prev, agentMsg];
        });
        if (!activeThreadId && agentMsg.thread_id) {
          await fetchThreads();
          setActiveThreadId(agentMsg.thread_id);
        }
        fetchState();
      } else {
        const errData = await res.json();
        setMessages(prev => [...prev, { role: 'system', content: errData.detail || 'Request error.', timestamp: new Date().toISOString() }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'system', content: 'Connection error with agent.', timestamp: new Date().toISOString() }]);
    } finally {
      setLoading(false);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const text = input.trim();
    const sendTime = new Date().toISOString();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text, created_at: sendTime }]);
    
    setTimeout(() => {
      inputRef.current?.focus();
    }, 0);

    await sendToBackend(text);

    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  const handleRenameThread = (e: React.MouseEvent, threadId: number, currentTitle: string) => {
    e.stopPropagation();
    if (!permissions.canRenameChats) {
      alert('Action restricted: Permission required to rename chats.');
      return;
    }
    const newTitle = prompt(language === 'en' ? 'New title for chat:' : 'Nuevo título para el chat:', currentTitle);
    if (!newTitle || newTitle.trim() === '') return;

    requestPin('Rename Chat', async (pin) => {
      try {
        const res = await apiFetch(`/chat/threads/${threadId}`, token, {
          method: 'PUT',
          body: JSON.stringify({ title: newTitle.trim(), pin })
        });
        if (res.ok) {
          fetchThreads();
        } else {
          alert(await readErrorDetail(res, 'Error renaming chat.'));
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  const handleDeleteThread = (e: React.MouseEvent, threadId: number) => {
    e.stopPropagation();
    if (!permissions.canDeleteChats) {
      alert('Action restricted: Permission required to delete chats.');
      return;
    }

    requestPin('Delete Chat Thread', async (pin) => {
      try {
        const res = await apiFetch(`/chat/threads/${threadId}?pin=${encodeURIComponent(pin)}`, token, {
          method: 'DELETE'
        });
        if (res.ok) {
          if (activeThreadId === threadId) {
            setActiveThreadId(null);
          }
          fetchThreads();
        } else {
          alert(await readErrorDetail(res, 'Error deleting chat.'));
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  return (
    <div ref={chatPanelRef} className="flex h-full overflow-hidden bg-transparent relative">
      
      {/* Thread Sidebar (Resizable & Collapsible) */}
      {!isChatsCollapsed && (
        <div style={{ width: `${sidebarWidth}px` }} className="border-r border-zinc-200/80 dark:border-zinc-800/80 flex flex-col shrink-0 bg-white/50 dark:bg-zinc-900/50 backdrop-blur-sm transition-colors">
          <div className="p-3 border-b border-zinc-200/80 dark:border-zinc-800/80 flex items-center gap-2">
            <button 
              onClick={startNewThread} 
              disabled={!permissions.canCreateChats}
              className={`flex-1 text-xs py-2 px-4 bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 rounded-full font-semibold flex items-center justify-center transition-all active:scale-95 shadow-sm ${permissions.canCreateChats ? 'hover:bg-zinc-800 dark:hover:bg-zinc-200' : 'opacity-50 cursor-not-allowed'}`}
            >
              <MessageSquarePlus size={14} className="mr-2" /> {t('newChat')}
            </button>

            <button 
              onClick={() => setIsChatsCollapsed(true)} 
              className="w-7 h-7 rounded-full flex items-center justify-center text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              title={t('collapseSidebar')}
            >
              <PanelLeftClose size={16} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {threads.map(th => (
              <div 
                key={th.id} 
                onClick={() => setActiveThreadId(th.id)}
                className={`p-2.5 px-3.5 cursor-pointer rounded-full mb-1 text-xs flex items-center justify-between transition-all ${
                  activeThreadId === th.id 
                    ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 font-semibold shadow-sm' 
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 hover:text-zinc-900 dark:hover:text-zinc-100'
                }`}
              >
                <span className="overflow-hidden text-ellipsis whitespace-nowrap flex-1 mr-2">
                  {th.title}
                </span>
                <div className="flex gap-1.5 items-center">
                  {permissions.canRenameChats && (
                    <button 
                      onClick={(e) => handleRenameThread(e, th.id, th.title)}
                      className={`p-1 rounded-full hover:bg-zinc-700/20 transition-colors ${activeThreadId === th.id ? 'text-zinc-300 dark:text-zinc-600 hover:text-white' : 'text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200'}`}
                      title="Rename thread"
                    >
                      <Edit2 size={12} />
                    </button>
                  )}
                  {permissions.canDeleteChats && (
                    <button 
                      onClick={(e) => handleDeleteThread(e, th.id)}
                      className="p-1 rounded-full text-red-500 hover:bg-red-500/20 transition-colors"
                      title="Delete thread"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Resize Handle for Chats Sidebar */}
      {!isChatsCollapsed && (
        <div 
          onMouseDown={startResizing}
          className={`w-1 cursor-col-resize z-10 border-r border-zinc-200/80 dark:border-zinc-800/80 transition-colors ${isResizing ? 'bg-zinc-400/50' : 'hover:bg-zinc-300/40 dark:hover:bg-zinc-700/40'}`}
        />
      )}

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative bg-transparent transition-colors">
        
        {/* Expand Chats Button when Collapsed */}
        {isChatsCollapsed && (
          <button 
            onClick={() => setIsChatsCollapsed(false)} 
            title="Expand Chats Sidebar"
            className="absolute top-3 left-3 z-15 bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 px-3.5 py-1.5 rounded-full text-xs font-semibold flex items-center gap-2 shadow-sm hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all active:scale-95"
          >
            <PanelLeftOpen size={14} /> Chats
          </button>
        )}

        <div 
          ref={chatContainerRef} 
          onScroll={handleScroll} 
          className={`flex-1 overflow-y-auto px-6 pb-6 flex flex-col gap-4 z-10 ${isChatsCollapsed ? 'pt-14' : 'pt-6'}`}
        >
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center select-none p-8">
              <div className="bg-white p-2 rounded-2xl mb-4 shadow-md border border-zinc-200 dark:border-zinc-800">
                <img src="/sari_logo.jpeg" alt="SARI" className="w-14 h-14 object-contain rounded-xl" />
              </div>
              
              <h2 className="text-xl font-bold text-zinc-900 dark:text-zinc-100 tracking-tight mb-2">
                SARI AGENT SOC
              </h2>
              
              <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-md leading-relaxed mb-6">
                {language === 'en'
                  ? 'Autonomous Intrusion Response System online. Select a quick directive or type a query to begin.'
                  : 'Sistema Autónomo de Respuesta a Intrusiones en línea. Selecciona una directiva rápida o escribe una consulta para comenzar.'}
              </p>

              {/* Pill Prompt Chips */}
              <div className="flex flex-wrap gap-2 justify-center max-w-lg">
                {language === 'en' ? (
                  <>
                    <button 
                      onClick={() => sendToBackend('Activate the siren')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🚨 "Activate the siren"
                    </button>
                    <button 
                      onClick={() => sendToBackend('Lock the gates')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🔒 "Lock the gates"
                    </button>
                    <button 
                      onClick={() => sendToBackend('Who are you and what do you do?')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🧠 "Who are you and what do you do?"
                    </button>
                    <button 
                      onClick={() => sendToBackend('What events have been detected recently?')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🔍 "What events have been detected?"
                    </button>
                  </>
                ) : (
                  <>
                    <button 
                      onClick={() => sendToBackend('Activa la sirena')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🚨 "Activa la sirena"
                    </button>
                    <button 
                      onClick={() => sendToBackend('Cierra los portones')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🔒 "Cierra los portones"
                    </button>
                    <button 
                      onClick={() => sendToBackend('¿Quién eres y qué haces?')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🧠 "¿Quién eres y qué haces?"
                    </button>
                    <button 
                      onClick={() => sendToBackend('¿Qué eventos se han detectado recientemente?')}
                      className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full text-xs font-medium hover:border-zinc-900 dark:hover:border-white hover:text-zinc-900 dark:hover:text-white transition-all shadow-sm active:scale-95"
                    >
                      🔍 "¿Qué eventos se han detectado?"
                    </button>
                  </>
                )}
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} className={`flex items-start gap-3 max-w-[85%] ${msg.role === 'user' ? 'self-end flex-row-reverse' : 'self-start'}`}>
                {msg.role !== 'user' && (
                  <div className="w-8 h-8 rounded-full bg-white dark:bg-zinc-800 shadow-sm border border-zinc-200 dark:border-zinc-700 flex items-center justify-center mt-1 shrink-0">
                    <Bot size={16} className="text-zinc-900 dark:text-white" />
                  </div>
                )}
                
                <div className={`p-4 rounded-3xl border shadow-sm transition-all text-sm leading-relaxed ${
                  msg.role === 'user' 
                    ? 'bg-zinc-900 text-white dark:bg-white dark:text-black rounded-tr-md border-zinc-900 dark:border-white font-medium shadow-sm' 
                    : msg.role === 'system'
                      ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 rounded-tl-md border-zinc-200 dark:border-zinc-700'
                      : 'bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 rounded-tl-md border-zinc-200/80 dark:border-zinc-800/80'
                }`}>
                  {renderFormattedContent(msg.content, msg.role === 'user')}

                  {msg.snapshot && msg.snapshot.length > 500 && (
                    <div className="mt-3 rounded-2xl overflow-hidden border border-red-500/40 max-w-lg shadow-lg bg-zinc-950">
                      <div className="bg-red-500/15 px-3.5 py-2 text-[11px] text-red-400 font-mono font-bold flex items-center justify-between border-b border-red-500/20">
                        <span className="flex items-center gap-1.5">
                          <span>📸</span>
                          <span>{language === 'en' ? 'Captured Evidence — YOLO26n' : 'Evidencia Capturada — YOLO26n'}</span>
                        </span>
                        <span className="text-[10px] text-zinc-400 font-mono">1080p HD</span>
                      </div>
                      <div className="bg-black p-1 flex justify-center items-center overflow-hidden">
                        <img 
                          src={msg.snapshot} 
                          alt="Intruder Snapshot" 
                          className="w-full max-h-[360px] object-cover rounded-xl block cursor-pointer hover:opacity-95 transition-opacity"
                          onClick={() => setPreviewSnapshot(msg.snapshot || null)}
                        />
                      </div>
                    </div>
                  )}

                  {(msg.timestamp || msg.created_at) && (
                    <div className={`text-[10px] mt-2 font-semibold flex items-center gap-1 ${
                      msg.role === 'user' 
                        ? 'text-zinc-400 dark:text-zinc-600 justify-end' 
                        : 'text-zinc-400 dark:text-zinc-500 justify-start'
                    }`}>
                      <span>{formatMessageTimestamp(msg.timestamp || msg.created_at)}</span>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-zinc-900 text-white dark:bg-white dark:text-black border border-zinc-700 dark:border-zinc-300 flex items-center justify-center shadow-sm mt-1 shrink-0">
                    <User size={16} />
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div className="flex gap-2.5 items-center text-zinc-500 dark:text-zinc-400 ml-11">
              <Bot size={15} /> <span className="text-xs italic animate-pulse">{language === 'en' ? 'SARI processing tactical response...' : 'SARI procesando respuesta táctica...'}</span>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input Bar: Google Antigravity Capsule */}
        <div className="px-6 py-4 flex justify-center border-t border-zinc-200/80 dark:border-zinc-800/80 bg-white/70 dark:bg-zinc-900/70 backdrop-blur-xl z-10 transition-colors">
          <div className="w-full max-w-4xl flex items-center gap-3">
            
            {/* Chat Input Capsule */}
            <form onSubmit={handleSend} className="flex-1 flex gap-3 bg-zinc-50 dark:bg-zinc-900/90 border border-zinc-200 dark:border-zinc-700 rounded-full px-5 py-2.5 items-center shadow-inner transition-colors focus-within:ring-2 focus-within:ring-zinc-400 dark:focus-within:ring-zinc-400 focus-within:bg-white dark:focus-within:bg-black">
              <input 
                ref={inputRef}
                type="text" 
                className="flex-1 bg-transparent border-none text-zinc-950 dark:text-white font-semibold outline-none text-xs sm:text-sm placeholder-zinc-400 dark:placeholder-zinc-500"
                value={input} 
                onChange={e => setInput(e.target.value)}
                placeholder={language === 'en' ? 'Type a message for SARI Agent...' : 'Escribe un mensaje para SARI Agent...'}
                disabled={loading}
                autoFocus
              />
              <button 
                type="submit" 
                disabled={loading} 
                className="w-8 h-8 rounded-full bg-zinc-900 text-white dark:bg-white dark:text-black flex items-center justify-center hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all disabled:opacity-40 active:scale-90 shadow-sm shrink-0"
                title={t('send')}
              >
                <Send size={14} />
              </button>
            </form>
          </div>
        </div>
      </div>
      {previewSnapshot && (
        <div 
          onClick={() => setPreviewSnapshot(null)}
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-6 cursor-pointer"
        >
          <div className="relative max-w-5xl max-h-[90vh] bg-zinc-900 border border-zinc-700 rounded-3xl overflow-hidden p-2 shadow-2xl">
            <img 
              src={previewSnapshot} 
              alt="Preview Full HD" 
              className="max-w-full max-h-[82vh] object-contain rounded-2xl"
            />
            <div className="text-center py-2 text-xs text-zinc-400 font-mono">
              {language === 'en' ? 'Click anywhere to close preview' : 'Haz clic en cualquier lugar para cerrar'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
