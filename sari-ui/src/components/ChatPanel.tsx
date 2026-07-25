import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, MessageSquarePlus, Edit2, Trash2, Cpu } from 'lucide-react';

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
}

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
  const [isResizing, setIsResizing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const startResizing = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return;
      const newWidth = Math.max(160, Math.min(500, e.clientX - 260));
      setSidebarWidth(newWidth);
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
        setMessages(prev => {
          if (JSON.stringify(prev) === JSON.stringify(data)) {
            return prev;
          }
          return data;
        });
      }
    } catch (e) {
      console.error(e);
    }
  };

  const startNewThread = () => {
    if (role !== 'admin') {
      alert('Acción restringida: Solo los administradores pueden crear nuevos hilos.');
      return;
    }

    requestPin('Crear Nuevo Hilo de Chat', async (pin) => {
      try {
        const res = await fetch(`${API_BASE}/chat/threads`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ title: 'Nuevo Hilo Compartido', pin })
        });
        if (res.ok) {
          const data = await res.json();
          fetchThreads();
          setActiveThreadId(data.id);
        } else {
          alert('PIN incorrecto o error al crear hilo.');
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
        if (!activeThreadId) {
          await fetchThreads();
        } else {
          fetchMessages(activeThreadId);
        }
        fetchState();
      } else {
        const errData = await res.json();
        setMessages(prev => [...prev, { role: 'system', content: errData.detail || 'Error en la petición.' }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'system', content: 'Error de conexión con el agente.' }]);
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
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    
    setTimeout(() => {
      inputRef.current?.focus();
    }, 0);

    await sendToBackend(text);

    setTimeout(() => {
      inputRef.current?.focus();
    }, 50);
  };

  const handleRenameThread = async (e: React.MouseEvent, threadId: number, currentTitle: string) => {
    e.stopPropagation();
    const newTitle = prompt('Nuevo título para el hilo:', currentTitle);
    if (!newTitle || newTitle.trim() === '') return;

    try {
      const res = await fetch(`${API_BASE}/chat/threads/${threadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (res.ok) {
        fetchThreads();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteThread = (e: React.MouseEvent, threadId: number) => {
    e.stopPropagation();
    if (role !== 'admin') {
      alert('Acción restringida: Solo los administradores pueden eliminar hilos.');
      return;
    }

    requestPin('Eliminar Hilo de Conversación', async (pin) => {
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
          alert('PIN incorrecto o permiso denegado.');
        }
      } catch (err) {
        console.error(err);
      }
    });
  };

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden', backgroundColor: '#0d1117' }}>
      
      {/* Thread Sidebar (Resizable) */}
      <div style={{ width: `${sidebarWidth}px`, borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', flexShrink: 0, userSelect: isResizing ? 'none' : 'auto' }}>
        <div style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
          <button 
            onClick={startNewThread} 
            className="btn btn-secondary" 
            style={{ width: '100%', opacity: role === 'admin' ? 1 : 0.6 }}
          >
            <MessageSquarePlus size={16} style={{ marginRight: '0.5rem' }}/> New Chat {role !== 'admin' && '(Admin)'}
          </button>
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
                backgroundColor: activeThreadId === t.id ? 'var(--primary-glow)' : 'transparent',
                color: activeThreadId === t.id ? 'var(--primary)' : 'var(--text-muted)',
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
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

      {/* Resize Handle */}
      <div 
        onMouseDown={startResizing}
        style={{
          width: '5px',
          cursor: 'col-resize',
          backgroundColor: isResizing ? 'var(--primary)' : 'transparent',
          transition: 'background-color 0.2s',
          zIndex: 10,
          borderRight: '1px solid var(--border)'
        }}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--primary-glow)')}
        onMouseLeave={(e) => (!isResizing && (e.currentTarget.style.backgroundColor = 'transparent'))}
      />

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <div 
          ref={chatContainerRef} 
          onScroll={handleScroll} 
          style={{ 
            flex: 1, 
            overflowY: 'auto', 
            padding: '1.5rem', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '1rem',
            WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%)',
            maskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%)'
          }}
        >
          {messages.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.8rem', alignSelf: 'flex-start', maxWidth: '85%' }}>
              <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.5rem', borderRadius: '50%' }}>
                <Bot size={18} color="var(--primary)" />
              </div>
              <div style={{
                background: 'rgba(139, 148, 158, 0.15)',
                border: '1px solid var(--border)',
                padding: '0.8rem 1.2rem',
                borderRadius: '12px',
                borderTopLeftRadius: 0,
                color: 'var(--text-main)',
                fontSize: '0.95rem'
              }}>
                SISTEMA SARI AGENT ONLINE. Conversación iniciada. Escriba su consulta táctica para comenzar.
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
                  background: msg.role === 'user' ? 'linear-gradient(135deg, var(--primary-glow), rgba(255, 51, 102, 0.05))' : 
                              msg.role === 'system' ? 'rgba(139, 148, 158, 0.15)' : 'rgba(255,255,255,0.03)',
                  border: `1px solid ${msg.role === 'user' ? 'var(--primary-glow)' : msg.role === 'system' ? 'var(--border)' : 'var(--border)'}`,
                  padding: '0.8rem 1.2rem',
                  borderRadius: '12px',
                  borderTopRightRadius: msg.role === 'user' ? 0 : '12px',
                  borderTopLeftRadius: msg.role !== 'user' ? 0 : '12px',
                  color: msg.role === 'system' ? 'var(--text-main)' : 'var(--text-main)',
                  fontSize: '0.95rem'
                }}>
                  {msg.content}
                </div>

                {msg.role === 'user' && (
                  <div style={{ background: 'var(--primary-glow)', padding: '0.5rem', borderRadius: '50%' }}>
                    <User size={18} color="var(--primary)" />
                  </div>
                )}
              </div>
            ))
          )}
          {loading && (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', color: 'var(--text-muted)' }}>
              <Bot size={16} /> <span style={{ fontSize: '0.8rem', fontStyle: 'italic', animation: 'pulse 1.5s infinite' }}>SARI analizando parámetros...</span>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Input & LLM Status Bar (LLM Badge to the Left of Chat Input Box) */}
        <div style={{ padding: '1.2rem 1.5rem', display: 'flex', justifyContent: 'center' }}>
          <div style={{ width: '100%', maxWidth: '900px', display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
            
            {/* LLM Status Badge (On the left side of chat input) */}
            <div 
              title="LLM Status: Online (Ollama qwen2.5-coder:14b)"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                background: 'rgba(255, 51, 102, 0.1)',
                border: '1px solid rgba(255, 51, 102, 0.3)',
                padding: '0.6rem 0.85rem',
                borderRadius: '12px',
                fontSize: '0.78rem',
                color: '#ff3366',
                fontWeight: 600,
                whiteSpace: 'nowrap',
                cursor: 'default',
                userSelect: 'none',
                height: '46px'
              }}
            >
              <Cpu size={15} color="#ff3366" />
              <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#2ea043', boxShadow: '0 0 6px #2ea043' }} />
              <span>LLM: Qwen 2.5 14B</span>
            </div>

            {/* Chat Input Form */}
            <form onSubmit={handleSend} style={{ flex: 1, display: 'flex', gap: '0.8rem', background: '#161b22', border: '1px solid #30363d', borderRadius: '12px', padding: '0.5rem 1rem', alignItems: 'center', height: '46px' }}>
              <input 
                ref={inputRef}
                type="text" 
                style={{ flex: 1, background: 'transparent', border: 'none', color: '#c9d1d9', outline: 'none', fontSize: '0.95rem' }}
                value={input} 
                onChange={e => setInput(e.target.value)}
                placeholder="chat with agent..."
                disabled={loading}
                autoFocus
              />
              <button type="submit" disabled={loading} style={{ background: 'transparent', border: 'none', color: '#8b949e', cursor: 'pointer', padding: '0.5rem' }}>
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
