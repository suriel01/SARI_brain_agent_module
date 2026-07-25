import { useState, useEffect } from 'react';
import { LogOut, ShieldAlert, BellRing, Lock } from 'lucide-react';
import ChatPanel from './ChatPanel';
import HardwarePanel from './HardwarePanel';
import AdminPanel from './AdminPanel';
import PinModal from './PinModal';
import CameraFeed from './CameraFeed';

interface DashboardProps {
  token: string;
  role: string;
  onLogout: () => void;
}

const API_BASE = 'http://localhost:7000/api';

export default function Dashboard({ token, role, onLogout }: DashboardProps) {
  const [state, setState] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'chat' | 'perception' | 'hardware' | 'admin'>('chat');
  
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
      alert('Permiso denegado: Se requiere rol de Administrador.');
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
    <div className="crt-scanlines" style={{ display: 'flex', height: '100vh', backgroundColor: '#0d1117' }}>
      
      {/* Left Sidebar */}
      <aside style={{ width: '260px', backgroundColor: '#161b22', borderRight: '1px solid #30363d', display: 'flex', flexDirection: 'column', padding: '1rem 0' }}>
        
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '0 1.5rem', gap: '0.8rem', marginBottom: '2rem' }}>
          <ShieldAlert size={24} color="#ff3366" />
          <span style={{ fontSize: '1.2rem', fontWeight: 600, color: '#e6edf3' }}>SARI AGENT</span>
        </div>
        
        {/* Nav Sections */}
        <div style={{ flex: 1, padding: '0 1rem' }}>
          <div style={{ fontSize: '0.7rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0.5rem', paddingLeft: '0.5rem' }}>Modules</div>
          
          <div 
            onClick={() => setActiveTab('chat')}
            style={{ padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'chat' ? 'rgba(255, 51, 102, 0.15)' : 'transparent', color: activeTab === 'chat' ? '#ff3366' : '#c9d1d9', display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.2rem' }}
          >
            <span style={{ fontSize: '0.9rem' }}>Chat</span>
          </div>

          <div 
            onClick={() => setActiveTab('perception')}
            style={{ padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'perception' ? 'rgba(255, 51, 102, 0.15)' : 'transparent', color: activeTab === 'perception' ? '#ff3366' : '#c9d1d9', display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.2rem' }}
          >
            <span style={{ fontSize: '0.9rem' }}>Live Perception</span>
          </div>

          <div 
            onClick={() => setActiveTab('hardware')}
            style={{ padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'hardware' ? 'rgba(255, 51, 102, 0.15)' : 'transparent', color: activeTab === 'hardware' ? '#ff3366' : '#c9d1d9', display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.2rem' }}
          >
            <span style={{ fontSize: '0.9rem' }}>Hardware Control</span>
          </div>

          {role === 'admin' && (
            <div 
              onClick={() => setActiveTab('admin')}
              style={{ marginTop: '0.2rem', padding: '0.55rem 1rem', cursor: 'pointer', borderRadius: '6px', backgroundColor: activeTab === 'admin' ? 'var(--primary-glow)' : 'transparent', color: activeTab === 'admin' ? 'var(--primary)' : '#c9d1d9', display: 'flex', alignItems: 'center', gap: '0.8rem' }}
            >
              <span style={{ fontSize: '0.9rem' }}>User Management</span>
            </div>
          )}
        </div>

        {/* Bottom actions */}
        <div style={{ padding: '1rem', borderTop: '1px solid #30363d' }}>
           <button 
             onClick={onLogout} 
             style={{ 
               width: '100%', 
               padding: '0.65rem 1rem', 
               background: 'rgba(255, 51, 102, 0.12)', 
               border: '1px solid rgba(255, 51, 102, 0.35)', 
               borderRadius: '8px', 
               color: '#ff3366', 
               cursor: 'pointer', 
               display: 'flex', 
               alignItems: 'center', 
               justifyContent: 'center', 
               gap: '0.6rem',
               fontSize: '0.85rem',
               fontWeight: 600,
               transition: 'all 0.2s ease',
               boxShadow: '0 2px 10px rgba(255, 51, 102, 0.15)'
             }}
             onMouseEnter={(e) => {
               e.currentTarget.style.background = 'rgba(255, 51, 102, 0.25)';
               e.currentTarget.style.borderColor = 'rgba(255, 51, 102, 0.7)';
               e.currentTarget.style.transform = 'translateY(-1px)';
             }}
             onMouseLeave={(e) => {
               e.currentTarget.style.background = 'rgba(255, 51, 102, 0.12)';
               e.currentTarget.style.borderColor = 'rgba(255, 51, 102, 0.35)';
               e.currentTarget.style.transform = 'none';
             }}
           >
             <LogOut size={16} /> <span>Logout [{role}]</span>
           </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        
        {/* Topbar with 1-Click Emergency Toolbar */}
        <header style={{ height: '60px', display: 'flex', alignItems: 'center', padding: '0 1.5rem', borderBottom: '1px solid #30363d', justifyContent: 'space-between', backgroundColor: '#0d1117' }}>
           <div style={{ fontSize: '1rem', fontWeight: 600, color: '#ff3366', letterSpacing: '0.02em' }}>
             {activeTab === 'chat' ? 'Chat' : activeTab === 'perception' ? 'Live Perception' : activeTab === 'hardware' ? 'Hardware Control' : 'User Management'}
           </div>

           {/* Emergency 1-Click Action Buttons */}
           <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <button 
                onClick={() => handleQuickEmergencyAction('activar_sirena')}
                title="Activar Sirena Física (30s)"
                style={{
                  background: 'rgba(255, 51, 102, 0.15)',
                  border: '1px solid #ff3366',
                  color: '#ff3366',
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
                <BellRing size={14} /> Sirena (30s)
              </button>

              <button 
                onClick={() => handleQuickEmergencyAction('cerrar_accesos')}
                title="Bloquear Portones Perimetrales"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid #30363d',
                  color: '#c9d1d9',
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
                <Lock size={14} /> Bloquear Accesos
              </button>

              <div style={{ width: '1px', height: '20px', backgroundColor: '#30363d', margin: '0 0.2rem' }} />

              <div style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '0.3rem 0.8rem', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', border: '1px solid #30363d' }}>
                 <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: state?.siren_active ? '#ff3366' : '#2ea043' }}></div>
                 <span style={{ color: '#c9d1d9' }}>{state?.siren_active ? 'Siren Active' : 'System Normal'}</span>
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
