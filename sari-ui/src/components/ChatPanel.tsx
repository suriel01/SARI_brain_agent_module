import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MessageSquarePlus, Edit2, Trash2, Cpu, ShieldAlert, PanelLeftOpen, PanelLeftClose } from 'lucide-react';

interface ChatPanelProps {
  token: string;
  role: string;
  requestPin: (actionName: string, callback: (pin: string) => void) => void;
  fetchState: () => void;
  lastAlertThreadId?: number | null;
}

interface Message {
  role: 'user' | 'agent' | 'system';
  content: string;
  created_at?: string;
  timestamp?: string;
}

const formatInlineText = (text: string) => {
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i} style={{ color: '#e6edf3', fontWeight: 600 }}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} style={{ background: 'rgba(110, 118, 129, 0.2)', padding: '0.15rem 0.4rem', borderRadius: '4px', color: '#ff7b72', fontSize: '0.85em', fontFamily: 'monospace' }}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
};

const renderFormattedContent = (text: string) => {
  if (!text) return null;

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let tableBuffer: string[] = [];

  const flushTable = () => {
    if (tableBuffer.length < 2) {
      tableBuffer.forEach((tblLine, idx) => {
        elements.push(<div key={`tbl-raw-${elements.length}-${idx}`}>{formatInlineText(tblLine)}</div>);
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
      <div key={`tbl-${elements.length}`} style={{ overflowX: 'auto', margin: '0.8rem 0', borderRadius: '8px', border: '1px solid #2d323e' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'rgba(255, 255, 255, 0.07)', borderBottom: '1px solid #334155', color: '#e2e8f0', fontWeight: 600 }}>
              {headers.map((h, i) => (
                <th key={i} style={{ padding: '0.6rem 0.8rem' }}>{formatInlineText(h)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowsLines.map((rowStr, rIdx) => {
              const cells = parseRow(rowStr);
              return (
                <tr key={rIdx} style={{ borderBottom: '1px solid rgba(30, 41, 59, 0.5)', background: rIdx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  {cells.map((c, cIdx) => (
                    <td key={cIdx} style={{ padding: '0.6rem 0.8rem', color: '#cbd5e1' }}>{formatInlineText(c)}</td>
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
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      tableBuffer.push(trimmed);
      return;
    } else if (tableBuffer.length > 0) {
      flushTable();
    }

    if (!trimmed) {
      elements.push(<div key={idx} style={{ height: '0.4rem' }} />);
      return;
    }

    const imgMatch = trimmed.match(/^!\[(.*?)\]\((.*?)\)$/);
    if (imgMatch) {
      elements.push(
        <div key={idx} style={{ margin: '0.8rem 0', textAlign: 'center' }}>
          <img 
            src={imgMatch[2]} 
            alt={imgMatch[1]} 
            style={{ 
              maxWidth: '100%', 
              borderRadius: '8px', 
              border: '1px solid rgba(56, 189, 248, 0.3)', 
              boxShadow: '0 4px 15px rgba(0,0,0,0.4)' 
            }} 
          />
        </div>
      );
      return;
    }

    if (trimmed.startsWith('# ')) {
      elements.push(<h1 key={idx} style={{ fontSize: '1.25rem', color: '#f1f5f9', margin: '0.8rem 0 0.4rem', fontWeight: 700 }}>{formatInlineText(trimmed.substring(2))}</h1>);
      return;
    }
    if (trimmed.startsWith('## ')) {
      elements.push(<h2 key={idx} style={{ fontSize: '1.1rem', color: '#e2e8f0', margin: '0.7rem 0 0.3rem', fontWeight: 600 }}>{formatInlineText(trimmed.substring(3))}</h2>);
      return;
    }
    if (trimmed.startsWith('### ')) {
      elements.push(<h3 key={idx} style={{ fontSize: '1rem', color: '#cbd5e1', margin: '0.6rem 0 0.3rem', fontWeight: 600 }}>{formatInlineText(trimmed.substring(4))}</h3>);
      return;
    }

    if (trimmed === '---') {
      elements.push(<hr key={idx} style={{ border: 'none', borderTop: '1px solid #30363d', margin: '0.8rem 0' }} />);
      return;
    }

    elements.push(
      <div key={idx} style={{ lineHeight: '1.55', margin: '0.2rem 0' }}>
        {formatInlineText(trimmed)}
      </div>
    );
  });

  if (tableBuffer.length > 0) {
    flushTable();
  }

  return elements;
};

const API_BASE = 'http://localhost:7000/api';

export default function ChatPanel({ token, role, requestPin, fetchState, lastAlertThreadId }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [threads, setThreads] = useState<any[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<number | null>(null);

  useEffect(() => {
    if (lastAlertThreadId) {
      setActiveThreadId(lastAlertThreadId);
    }
  }, [lastAlertThreadId]);
  
  const [sidebarWidth, setSidebarWidth] = useState(250);
  const [isChatsCollapsed, setIsChatsCollapsed] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const chatPanelRef = useRef<HTMLDivElement>(null);

  const startResizing = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !chatPanelRef.current) return;
      const rect = chatPanelRef.current.getBoundingClientRect();
      const newWidth = e.clientX - rect.left;
      if (newWidth < 80) {
        setIsChatsCollapsed(true);
      } else {
        setIsChatsCollapsed(false);
        setSidebarWidth(Math.min(Math.max(newWidth, 160), 400));
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    if (isResizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing]);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [userIsScrolledUp, setUserIsScrolledUp] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const scrollPositionsRef = useRef<Record<number, number>>({});
  const isSwitchingThreadRef = useRef(false);

  useEffect(() => {
    if (!loading) {
      inputRef.current?.focus();
    }
  }, [loading]);

  const handleScroll = () => {
    if (chatContainerRef.current && activeThreadId && !isSwitchingThreadRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      const scrolledUp = scrollHeight - scrollTop - clientHeight > 80;
      setUserIsScrolledUp(scrolledUp);
      scrollPositionsRef.current[activeThreadId] = scrollTop;
    }
  };

  useEffect(() => {
    fetchThreads();
    const interval = setInterval(fetchThreads, 1500);
    return () => clearInterval(interval);
  }, [token]);

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
      setMessages([{ role: 'system', content: 'SISTEMA SOC ACTIVO. IA TÁCTICA ONLINE. Seleccione o inicie un hilo de conversación.' }]);
    }
  }, [activeThreadId]);

  useEffect(() => {
    if (!userIsScrolledUp && !isSwitchingThreadRef.current) {
      endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const fetchThreads = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/threads`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
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
      const res = await fetch(`${API_BASE}/chat/threads/${threadId}/messages`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const startNewThread = () => {
    if (role !== 'admin') {
      alert('Action restricted: Only administrators can create new chats.');
      return;
    }

    requestPin('Create New Chat', async (pin) => {
      try {
        const res = await fetch(`${API_BASE}/chat/threads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ title: 'New Shared Chat', pin })
        });
        if (res.ok) {
          const data = await res.json();
          fetchThreads();
          setActiveThreadId(data.id);
        } else {
          alert('Incorrect PIN or error creating chat.');
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  const sendToBackend = async (text: string) => {
    setLoading(true);
    try {
      const payload: any = { message: text };
      if (activeThreadId) payload.thread_id = activeThreadId;

      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
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
    if (role !== 'admin') {
      alert('Action restricted: Permission required to rename chats.');
      return;
    }
    const newTitle = prompt('New title for chat:', currentTitle);
    if (!newTitle || newTitle.trim() === '') return;

    requestPin('Rename Chat', async (pin) => {
      try {
        const res = await fetch(`${API_BASE}/chat/threads/${threadId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ title: newTitle.trim(), pin })
        });
        if (res.ok) {
          fetchThreads();
        } else {
          alert('Incorrect PIN or permission denied.');
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  const handleDeleteThread = (e: React.MouseEvent, threadId: number) => {
    e.stopPropagation();
    if (role !== 'admin') {
      alert('Action restricted: Only administrators can delete chats.');
      return;
    }

    requestPin('Delete Chat Thread', async (pin) => {
      try {
        const res = await fetch(`${API_BASE}/chat/threads/${threadId}?pin=${pin}`, {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
          if (activeThreadId === threadId) {
            setActiveThreadId(null);
          }
          fetchThreads();
        } else {
          alert('Incorrect PIN or permission denied.');
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  return (
    <div ref={chatPanelRef} style={{ display: 'flex', height: '100%', overflow: 'hidden', backgroundColor: 'transparent', position: 'relative' }}>
      
      {/* Thread Sidebar (Resizable & Collapsible) */}
      {!isChatsCollapsed && (
        <div style={{ width: `${sidebarWidth}px`, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0, userSelect: isResizing ? 'none' : 'auto' }}>
          <div style={{ padding: '0.8rem 1rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <button 
              onClick={startNewThread} 
              style={{ flex: 1, opacity: role === 'admin' ? 1 : 0.6, fontSize: '0.82rem', padding: '0.5rem', background: '#0284c7', color: '#ffffff', border: '1px solid #0284c7', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              <MessageSquarePlus size={15} style={{ marginRight: '0.4rem' }}/> New Chat
            </button>

            <PanelLeftClose
              size={18}
              onClick={() => setIsChatsCollapsed(true)}
              style={{ cursor: 'pointer', color: '#94a3b8', transition: 'color 0.2s' }}
              onMouseEnter={(e) => (e.currentTarget.style.color = '#f1f5f9')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
            />
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '0.5rem' }}>
            {threads.map(t => (
              <div 
                key={t.id} 
                onClick={() => setActiveThreadId(t.id)}
                className="thread-item"
                style={{ 
                  padding: '0.8rem', 
                  cursor: 'pointer',
                  borderRadius: '6px',
                  marginBottom: '0.5rem',
                  backgroundColor: activeThreadId === t.id ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
                  color: activeThreadId === t.id ? '#f1f5f9' : '#94a3b8',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  borderLeft: activeThreadId === t.id ? '3px solid #64748b' : '3px solid transparent'
                }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, marginRight: '0.5rem' }}>
                  {t.title}
                </span>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <Edit2 
                    size={14} 
                    onClick={(e) => handleRenameThread(e, t.id, t.title)}
                    style={{ cursor: 'pointer', opacity: 0.7 }}
                  />
                  {role === 'admin' && (
                    <Trash2 
                      size={14} 
                      onClick={(e) => handleDeleteThread(e, t.id)}
                      style={{ cursor: 'pointer', opacity: 0.7, color: 'var(--danger)' }}
                    />
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
          style={{
            width: '5px',
            cursor: 'col-resize',
            backgroundColor: isResizing ? '#64748b' : 'transparent',
            transition: 'background-color 0.2s',
            zIndex: 10,
            borderRight: '1px solid var(--border)'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(148, 163, 184, 0.4)')}
          onMouseLeave={(e) => (!isResizing && (e.currentTarget.style.backgroundColor = 'transparent'))}
        />
      )}

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        
        {/* Expand Chats Button when Collapsed */}
        {isChatsCollapsed && (
          <button
            onClick={() => setIsChatsCollapsed(false)}
            title="Expand Chats Sidebar"
            style={{
              position: 'absolute',
              top: '12px',
              left: '12px',
              zIndex: 15,
              background: '#0284c7',
              border: '1px solid #0284c7',
              color: '#ffffff',
              padding: '0.4rem 0.75rem',
              borderRadius: '6px',
              fontSize: '0.78rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              boxShadow: '0 2px 8px rgba(2, 132, 199, 0.3)'
            }}
          >
            <PanelLeftOpen size={16} color="#ffffff" /> Show Chats
          </button>
        )}

        <div 
          ref={chatContainerRef} 
          onScroll={handleScroll} 
          style={{ 
            flex: 1, 
            overflowY: 'auto', 
            padding: '1.5rem', 
            paddingTop: isChatsCollapsed ? '3.5rem' : '1.5rem', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '1rem',
            zIndex: 2,
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%)',
            maskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%)'
          }}
        >
          {messages.length === 0 ? (
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              textAlign: 'center',
              userSelect: 'none',
              padding: '2rem'
            }}>
              <div style={{
                background: 'rgba(255, 51, 102, 0.12)',
                border: '1px solid rgba(255, 51, 102, 0.35)',
                padding: '1.2rem',
                borderRadius: '50%',
                marginBottom: '1.2rem',
                boxShadow: '0 0 30px rgba(255, 51, 102, 0.2)'
              }}>
                <ShieldAlert size={44} color="#ff3366" />
              </div>
              
              <h2 style={{ fontSize: '1.6rem', fontWeight: 700, color: '#e6edf3', letterSpacing: '1px', marginBottom: '0.4rem' }}>
                SARI AGENT SOC
              </h2>
              
              <p style={{ fontSize: '0.9rem', color: '#8b949e', maxWidth: '480px', lineHeight: 1.5, marginBottom: '1.8rem' }}>
                Tactical Autonomous System Online. Select a quick command or type your query below to start the conversation.
              </p>

              {/* Sample Prompt Chips */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', justifyContent: 'center', maxWidth: '540px' }}>
                <button
                  onClick={() => sendToBackend('Activa la sirena')}
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    color: '#c9d1d9',
                    padding: '0.55rem 1rem',
                    borderRadius: '20px',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontWeight: 500
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#ff3366';
                    e.currentTarget.style.color = '#ff3366';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#30363d';
                    e.currentTarget.style.color = '#c9d1d9';
                  }}
                >
                  🚨 "Activa la sirena"
                </button>

                <button
                  onClick={() => sendToBackend('Cierra los portones')}
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    color: '#c9d1d9',
                    padding: '0.55rem 1rem',
                    borderRadius: '20px',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontWeight: 500
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#ff3366';
                    e.currentTarget.style.color = '#ff3366';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#30363d';
                    e.currentTarget.style.color = '#c9d1d9';
                  }}
                >
                  🔒 "Cierra los portones"
                </button>

                <button
                  onClick={() => sendToBackend('¿Quién eres y qué haces?')}
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    color: '#c9d1d9',
                    padding: '0.55rem 1rem',
                    borderRadius: '20px',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontWeight: 500
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#ff3366';
                    e.currentTarget.style.color = '#ff3366';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#30363d';
                    e.currentTarget.style.color = '#c9d1d9';
                  }}
                >
                  🧠 "¿Quién eres y qué haces?"
                </button>

                <button
                  onClick={() => sendToBackend('¿Qué eventos se han detectado recientemente?')}
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    color: '#c9d1d9',
                    padding: '0.55rem 1rem',
                    borderRadius: '20px',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    fontWeight: 500
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#ff3366';
                    e.currentTarget.style.color = '#ff3366';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#30363d';
                    e.currentTarget.style.color = '#c9d1d9';
                  }}
                >
                  🔍 "¿Qué eventos se han detectado?"
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'flex-start', gap: '0.8rem', alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                {msg.role !== 'user' && (
                  <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.5rem', borderRadius: '50%' }}>
                    <Bot size={18} color="var(--primary)" />
                  </div>
                )}
                
                <div style={{
                  background: msg.role === 'user' ? 'linear-gradient(135deg, rgba(56, 189, 248, 0.16), rgba(56, 189, 248, 0.04))' : 
                              msg.role === 'system' ? 'rgba(148, 163, 184, 0.15)' : 'rgba(15, 23, 42, 0.65)',
                  border: `1px solid ${msg.role === 'user' ? 'rgba(56, 189, 248, 0.35)' : msg.role === 'system' ? 'var(--border)' : 'var(--border)'}`,
                  padding: '0.8rem 1.2rem',
                  borderRadius: '12px',
                  borderTopRightRadius: msg.role === 'user' ? 0 : '12px',
                  borderTopLeftRadius: msg.role !== 'user' ? 0 : '12px',
                  color: msg.role === 'system' ? 'var(--text-main)' : 'var(--text-main)',
                  fontSize: '0.95rem',
                  backdropFilter: 'blur(8px)'
                }}>
                  {renderFormattedContent(msg.content)}
                  {(msg.timestamp || msg.created_at) && (
                    <div style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: '0.4rem', textAlign: msg.role === 'user' ? 'right' : 'left', opacity: 0.75, display: 'flex', alignItems: 'center', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', gap: '0.3rem' }}>
                      <span>{new Date(msg.timestamp || msg.created_at!).toLocaleString()}</span>
                    </div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div style={{ background: 'rgba(56, 189, 248, 0.15)', padding: '0.5rem', borderRadius: '50%' }}>
                    <User size={18} color="var(--primary)" />
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: 'var(--text-muted)' }}>
              <Bot size={16} /> <span style={{ fontSize: '0.8rem', fontStyle: 'italic', animation: 'pulse 1.5s infinite' }}>SARI analyzing parameters...</span>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input & LLM Status Bar (LLM Badge to the Left of Chat Input Box) */}
        <div style={{ padding: '1.2rem 1.5rem', display: 'flex', justifyContent: 'center' }}>
          <div style={{ width: '100%', maxWidth: '900px', display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
            
            {/* LLM Status Badge (Generic for security) */}
            <div 
              title="LLM Status: Online"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                background: 'rgba(56, 189, 248, 0.08)',
                border: '1px solid rgba(56, 189, 248, 0.25)',
                padding: '0.6rem 0.85rem',
                borderRadius: '12px',
                fontSize: '0.78rem',
                color: '#38bdf8',
                fontWeight: 600,
                whiteSpace: 'nowrap',
                cursor: 'default',
                userSelect: 'none',
                height: '46px'
              }}
            >
              <Cpu size={15} color="#94a3b8" />
              <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#10b981', boxShadow: '0 0 6px #10b981' }} />
              <span style={{ color: '#94a3b8' }}>LLM Online</span>
            </div>

            {/* Chat Input Form */}
            <form onSubmit={handleSend} style={{ flex: 1, display: 'flex', gap: '0.8rem', background: 'rgba(15, 23, 42, 0.75)', border: '1px solid #334155', borderRadius: '12px', padding: '0.4rem 0.6rem 0.4rem 1rem', alignItems: 'center', height: '46px' }}>
              <input 
                ref={inputRef}
                type="text" 
                style={{ flex: 1, background: 'transparent', border: 'none', color: '#f1f5f9', outline: 'none', fontSize: '0.95rem' }}
                value={input} 
                onChange={e => setInput(e.target.value)}
                placeholder="chat with agent..."
                disabled={loading}
                autoFocus
              />
              <button type="submit" disabled={loading} style={{ background: '#0284c7', border: '1px solid #0284c7', color: '#ffffff', borderRadius: '8px', cursor: 'pointer', padding: '0.4rem 0.7rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Send size={16} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
