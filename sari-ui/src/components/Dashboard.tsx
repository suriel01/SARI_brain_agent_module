import { useState, useEffect } from 'react';
import { LogOut, ShieldAlert, BellRing, Lock, PanelLeftOpen, PanelLeftClose } from 'lucide-react';
import ChatPanel from './ChatPanel';
import HardwarePanel from './HardwarePanel';
import AdminPanel from './AdminPanel';
import PinModal from './PinModal';
import CameraFeed from './CameraFeed';
import CircuitCanvas from './CircuitCanvas';

interface DashboardProps {
  token: string;
  role: string;
  onLogout: () => void;
}

const API_BASE = 'http://localhost:7000/api';

export default function Dashboard({ token, role, onLogout }: DashboardProps) {
  const [state, setState] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'chat' | 'perception' | 'hardware' | 'admin'>('chat');
  
  // Main Modules Sidebar Resizing & Collapsing State
  const [moduleWidth, setModuleWidth] = useState(260);
  const [isModulesCollapsed, setIsModulesCollapsed] = useState(false);
  const [isResizingModules, setIsResizingModules] = useState(false);

  // Modal State
  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<string>('');
  const [actionCallback, setActionCallback] = useState<((pin: string) => void) | null>(null);

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_BASE}/hardware/state`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setState(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 1200);
    return () => clearInterval(interval);
  }, [token]);

  // Modules Resizing Effect
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingModules) return;
      const newWidth = e.clientX;
      if (newWidth < 90) {
        setIsModulesCollapsed(true);
      } else {
        setIsModulesCollapsed(false);
        setModuleWidth(Math.min(Math.max(newWidth, 180), 380));
      }
    };

    const handleMouseUp = () => {
      setIsResizingModules(false);
    };

    if (isResizingModules) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingModules]);

  // Web Audio API Siren Fallback
  useEffect(() => {
    if (state?.siren_active) {
      try {
        const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sawtooth';
        gain.gain.value = 0.15;
        
        const now = audioCtx.currentTime;
        osc.frequency.setValueAtTime(700, now);
        for (let i = 0; i < 40; i++) {
          osc.frequency.linearRampToValueAtTime(1400, now + i * 0.7 + 0.35);
          osc.frequency.linearRampToValueAtTime(700, now + i * 0.7 + 0.7);
        }
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        return () => {
          try {
            osc.stop();
            audioCtx.close();
          } catch (e) {}
        };
      } catch (e) {
        console.error('Web Audio error:', e);
      }
    }
  }, [state?.siren_active]);

  const requestPin = (actionName: string, callback: (pin: string) => void) => {
    setPendingAction(actionName);
    setActionCallback(() => callback);
    setPinModalOpen(true);
  };

  const handlePinSubmit = (pin: string) => {
    if (actionCallback) {
      actionCallback(pin);
    }
    setPinModalOpen(false);
  };

  const handleQuickEmergencyAction = (actionName: string) => {
    if (role !== 'admin') {
      alert('Permission denied: Administrator role required.');
      return;
    }
    requestPin(actionName, async (pin) => {
      try {
        await fetch(`${API_BASE}/manual_action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ action: actionName, pin })
        });
        fetchState();
      } catch (e) {
        console.error('Error executing quick action', e);
      }
    });
  };

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: '#090a0f', overflow: 'hidden', position: 'relative' }}>
      <CircuitCanvas />
      
      {/* Main Left Sidebar (MODULES) */}
      {!isModulesCollapsed && (
        <aside style={{ width: `${moduleWidth}px`, backgroundColor: 'rgba(19, 21, 28, 0.88)', backdropFilter: 'blur(12px)', borderRight: '1px solid #2d323e', display: 'flex', flexDirection: 'column', padding: '1rem 0', flexShrink: 0, zIndex: 2 }}>
          
          {/* Brand & Collapse Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 1.2rem', marginBottom: '2rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', flex: 1 }}>
              <ShieldAlert size={22} color="#94a3b8" />
              <span style={{ fontSize: '1.15rem', fontWeight: 600, color: '#f8fafc', letterSpacing: '0.5px' }}>SARI AGENT</span>
            </div>

            <PanelLeftClose 
              size={18} 
              onClick={() => setIsModulesCollapsed(true)} 
              style={{ cursor: 'pointer', color: '#94a3b8', transition: 'color 0.2s' }} 
              onMouseEnter={(e) => (e.currentTarget.style.color = '#f1f5f9')}
              onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
            />
          </div>
          
          {/* Nav Sections */}
          <div style={{ flex: 1, padding: '0 1rem' }}>
            <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem', paddingLeft: '0.5rem' }}>Modules</div>
            
            <div 
              onClick={() => setActiveTab('chat')}
              style={{ padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'chat' ? 'rgba(255, 255, 255, 0.08)' : 'transparent', color: activeTab === 'chat' ? '#f1f5f9' : '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.2rem', fontWeight: activeTab === 'chat' ? 600 : 400, borderLeft: activeTab === 'chat' ? '3px solid #64748b' : '3px solid transparent' }}
            >
              <span style={{ fontSize: '0.9rem' }}>Chat</span>
            </div>

            <div 
              onClick={() => setActiveTab('perception')}
              style={{ padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'perception' ? 'rgba(255, 255, 255, 0.08)' : 'transparent', color: activeTab === 'perception' ? '#f1f5f9' : '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.2rem', fontWeight: activeTab === 'perception' ? 600 : 400, borderLeft: activeTab === 'perception' ? '3px solid #64748b' : '3px solid transparent' }}
            >
              <span style={{ fontSize: '0.9rem' }}>Live Perception</span>
            </div>

            <div 
              onClick={() => setActiveTab('hardware')}
              style={{ padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'hardware' ? 'rgba(255, 255, 255, 0.08)' : 'transparent', color: activeTab === 'hardware' ? '#f1f5f9' : '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.2rem', fontWeight: activeTab === 'hardware' ? 600 : 400, borderLeft: activeTab === 'hardware' ? '3px solid #64748b' : '3px solid transparent' }}
            >
              <span style={{ fontSize: '0.9rem' }}>Hardware Control</span>
            </div>

            {role === 'admin' && (
              <div 
                onClick={() => setActiveTab('admin')}
                style={{ marginTop: '0.2rem', padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'admin' ? 'rgba(255, 255, 255, 0.08)' : 'transparent', color: activeTab === 'admin' ? '#f1f5f9' : '#94a3b8', display: 'flex', alignItems: 'center', gap: '0.8rem', fontWeight: activeTab === 'admin' ? 600 : 400, borderLeft: activeTab === 'admin' ? '3px solid #64748b' : '3px solid transparent' }}
              >
                <span style={{ fontSize: '0.9rem' }}>User Management</span>
              </div>
            )}
          </div>

          {/* Bottom actions (BOTÓN AZUL DE ACCIÓN) */}
          <div style={{ padding: '1rem', borderTop: '1px solid #2d323e' }}>
             <button 
               onClick={onLogout} 
               style={{ 
                 width: '100%', 
                 padding: '0.65rem 1rem', 
                 background: '#0284c7', 
                 border: '1px solid #0284c7', 
                 borderRadius: '8px', 
                 color: '#ffffff', 
                 cursor: 'pointer', 
                 display: 'flex', 
                 alignItems: 'center', 
                 justifyContent: 'center', 
                 gap: '0.6rem',
                 fontSize: '0.85rem',
                 fontWeight: 600,
                 transition: 'all 0.2s ease',
                 boxShadow: '0 2px 10px rgba(2, 132, 199, 0.3)'
               }}
             >
               <LogOut size={16} /> <span>Logout [{role}]</span>
             </button>
          </div>
        </aside>
      )}

      {/* Resize Handle for Modules Sidebar */}
      {!isModulesCollapsed && (
        <div 
          onMouseDown={() => setIsResizingModules(true)}
          style={{
            width: '5px',
            cursor: 'col-resize',
            backgroundColor: isResizingModules ? '#64748b' : 'transparent',
            transition: 'background-color 0.2s',
            zIndex: 10,
            borderRight: '1px solid #2d323e'
          }}
          onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(148, 163, 184, 0.4)')}
          onMouseLeave={(e) => (!isResizingModules && (e.currentTarget.style.backgroundColor = 'transparent'))}
        />
      )}

      {/* Main Content Area */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', zIndex: 2 }}>
        
        {/* Topbar with 1-Click Emergency Toolbar */}
        <header style={{ height: '60px', display: 'flex', alignItems: 'center', padding: '0 1.5rem', borderBottom: '1px solid #2d323e', justifyContent: 'space-between', backgroundColor: 'rgba(19, 21, 28, 0.88)', backdropFilter: 'blur(12px)' }}>
           <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
             {/* Show Unfold Button for Modules when collapsed (BOTÓN AZUL DE ACCIÓN) */}
             {isModulesCollapsed && (
               <button
                 onClick={() => setIsModulesCollapsed(false)}
                 title="Expand Modules Sidebar"
                 style={{
                   background: '#0284c7',
                   border: '1px solid #0284c7',
                   color: '#ffffff',
                   padding: '0.35rem 0.75rem',
                   borderRadius: '6px',
                   fontSize: '0.8rem',
                   fontWeight: 600,
                   cursor: 'pointer',
                   display: 'flex',
                   alignItems: 'center',
                   gap: '0.4rem',
                   boxShadow: '0 2px 8px rgba(2, 132, 199, 0.3)'
                 }}
               >
                 <PanelLeftOpen size={16} /> Modules
               </button>
             )}

             <div style={{ fontSize: '1rem', fontWeight: 600, color: '#f1f5f9', letterSpacing: '0.02em' }}>
               {activeTab === 'chat' ? 'Chat' : activeTab === 'perception' ? 'Live Perception' : activeTab === 'hardware' ? 'Hardware Control' : 'User Management'}
             </div>
           </div>

           {/* Emergency Action Buttons (Rojo para máxima importancia, Amarillo para alerta de portones) */}
           <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              
              {/* Single Siren Toggle Button (Rojo ÚNICAMENTE si está activa la emergencia) */}
              <button 
                onClick={() => handleQuickEmergencyAction('toggle_sirena')}
                style={{
                  background: state?.siren_active ? '#ff0055' : 'rgba(255, 255, 255, 0.05)',
                  border: `1px solid ${state?.siren_active ? '#ff0055' : '#30363d'}`,
                  color: state?.siren_active ? '#ffffff' : '#9ca3af',
                  padding: '0.35rem 0.8rem',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  animation: state?.siren_active ? 'pulse 1s infinite' : 'none'
                }}
              >
                <BellRing size={14} color={state?.siren_active ? '#ffffff' : '#9ca3af'} /> {state?.siren_active ? '🚨 Siren (ACTIVE EMERGENCY)' : 'Siren (Off)'}
              </button>

              {/* Single Gates Toggle Button (Amarillo ÚNICAMENTE si está bloqueado) */}
              <button 
                onClick={() => handleQuickEmergencyAction('toggle_accesos')}
                style={{
                  background: state?.gates_locked ? 'rgba(245, 158, 11, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1px solid ${state?.gates_locked ? '#f59e0b' : '#30363d'}`,
                  color: state?.gates_locked ? '#f59e0b' : '#9ca3af',
                  padding: '0.35rem 0.8rem',
                  borderRadius: '6px',
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem'
                }}
              >
                <Lock size={14} color={state?.gates_locked ? '#f59e0b' : '#9ca3af'} /> {state?.gates_locked ? '🔒 Gates Locked' : 'Lock Gates'}
              </button>

              <div style={{ width: '1px', height: '20px', backgroundColor: '#30363d', margin: '0 0.2rem' }} />

              {/* Status Badge (Verde = Normal / OK) */}
              <div style={{ background: 'rgba(255, 255, 255, 0.04)', padding: '0.3rem 0.8rem', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', border: '1px solid #30363d' }}>
                 <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: state?.siren_active ? '#ff0055' : state?.gates_locked ? '#f59e0b' : '#10b981' }}></div>
                 <span style={{ color: '#c9d1d9' }}>{state?.siren_active ? 'EMERGENCY ALERT' : state?.gates_locked ? 'Gates Locked' : 'System Normal'}</span>
              </div>
           </div>
        </header>

        {/* Content Body */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {activeTab === 'chat' ? (
            <ChatPanel token={token} role={role} requestPin={requestPin} fetchState={fetchState} lastAlertThreadId={state?.last_alert_thread_id} />
          ) : activeTab === 'perception' ? (
            <div style={{ padding: '2rem', height: '100%' }}>
              <CameraFeed />
            </div>
          ) : activeTab === 'hardware' ? (
            <HardwarePanel token={token} role={role} requestPin={requestPin} state={state} fetchState={fetchState} />
          ) : (
            <AdminPanel token={token} />
          )}
        </div>
      </main>

      <PinModal 
        isOpen={pinModalOpen} 
        onClose={() => setPinModalOpen(false)} 
        onSubmit={handlePinSubmit} 
        actionName={pendingAction} 
      />
    </div>
  );
}
