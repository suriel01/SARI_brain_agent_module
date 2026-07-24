import { useState, useEffect } from 'react';
import { LogOut, ShieldAlert } from 'lucide-react';
import ChatPanel from './ChatPanel';
import HardwarePanel from './HardwarePanel';
import AdminPanel from './AdminPanel';
import PinModal from './PinModal';

interface DashboardProps {
  token: string;
  role: string;
  onLogout: () => void;
}

const API_BASE = 'http://localhost:7000/api';

export default function Dashboard({ token, role, onLogout }: DashboardProps) {
  const [state, setState] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'chat' | 'hardware' | 'admin'>('chat');
  
  // Modal State
  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<string>('');
  const [pendingCallback, setPendingCallback] = useState<((pin: string) => void) | null>(null);

  const fetchState = async () => {
    try {
      const res = await fetch(`${API_BASE}/state`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setState(await res.json());
      } else if (res.status === 401) {
        onLogout();
      }
    } catch (e) {
      console.error('Error fetching state', e);
    }
  };

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 2000);
    return () => clearInterval(interval);
  }, [token]);

  // Sintetizador Web Audio API para reproducir alarma física en la UI
  useEffect(() => {
    if (!state?.siren_active) return;

    let audioCtx: AudioContext | null = null;
    let osc: OscillatorNode | null = null;
    let gain: GainNode | null = null;
    let intervalId: any = null;

    try {
      audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      if (audioCtx.state === 'suspended') {
        audioCtx.resume();
      }
      osc = audioCtx.createOscillator();
      gain = audioCtx.createGain();

      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(700, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);

      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();

      let high = false;
      intervalId = setInterval(() => {
        if (audioCtx && osc) {
          osc.frequency.setValueAtTime(high ? 700 : 950, audioCtx.currentTime);
          high = !high;
        }
      }, 350);
    } catch (e) {
      console.error('AudioContext error:', e);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
      if (osc) {
        try { osc.stop(); } catch(e){}
      }
      if (audioCtx) {
        try { audioCtx.close(); } catch(e){}
      }
    };
  }, [state?.siren_active, state?.alert_count]);

  const requestPin = (actionName: string, callback: (pin: string) => void) => {
    setPendingAction(actionName);
    setPendingCallback(() => callback);
    setPinModalOpen(true);
  };

  const handlePinSubmit = (pin: string) => {
    if (pendingCallback) {
      pendingCallback(pin);
    }
    setPinModalOpen(false);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', backgroundColor: 'var(--bg-dark)' }}>
      
      {/* Left Sidebar */}
      <aside style={{ width: '260px', backgroundColor: 'var(--bg-panel)', borderRight: '1px solid var(--border)', display: 'flex', flexDirection: 'column', padding: '1rem 0' }}>
        
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', padding: '0 1.5rem', gap: '0.8rem', marginBottom: '2rem' }}>
          <ShieldAlert size={24} color="var(--primary)" style={{ filter: 'drop-shadow(0 0 8px var(--primary-glow))' }} />
          <span style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '0.05em' }}>SARI SOC</span>
        </div>
        
        {/* Nav Sections */}
        <div style={{ flex: 1, padding: '0 1rem' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '1.5px', marginBottom: '0.6rem', paddingLeft: '0.5rem', fontWeight: 600 }}>Modules</div>
          
          <div 
            onClick={() => setActiveTab('chat')}
            style={{ 
              padding: '0.65rem 1rem', 
              cursor: 'pointer', 
              borderRadius: '6px', 
              backgroundColor: activeTab === 'chat' ? 'var(--primary-glow-subtle)' : 'transparent', 
              color: activeTab === 'chat' ? 'var(--primary)' : 'var(--text-muted)', 
              border: `1px solid ${activeTab === 'chat' ? 'var(--border-focus)' : 'transparent'}`,
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.8rem', 
              marginBottom: '0.3rem',
              fontWeight: activeTab === 'chat' ? 600 : 400
            }}
          >
            <span style={{ fontSize: '0.9rem' }}>Main Terminal</span>
          </div>

          <div 
            onClick={() => setActiveTab('hardware')}
            style={{ 
              padding: '0.65rem 1rem', 
              cursor: 'pointer', 
              borderRadius: '6px', 
              backgroundColor: activeTab === 'hardware' ? 'var(--primary-glow-subtle)' : 'transparent', 
              color: activeTab === 'hardware' ? 'var(--primary)' : 'var(--text-muted)', 
              border: `1px solid ${activeTab === 'hardware' ? 'var(--border-focus)' : 'transparent'}`,
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.8rem',
              marginBottom: '0.3rem',
              fontWeight: activeTab === 'hardware' ? 600 : 400
            }}
          >
            <span style={{ fontSize: '0.9rem' }}>Hardware Control</span>
          </div>

          {role === 'admin' && (
            <div 
              onClick={() => setActiveTab('admin')}
              style={{ 
                padding: '0.65rem 1rem', 
                cursor: 'pointer', 
                borderRadius: '6px', 
                backgroundColor: activeTab === 'admin' ? 'var(--primary-glow-subtle)' : 'transparent', 
                color: activeTab === 'admin' ? 'var(--primary)' : 'var(--text-muted)', 
                border: `1px solid ${activeTab === 'admin' ? 'var(--border-focus)' : 'transparent'}`,
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.8rem',
                fontWeight: activeTab === 'admin' ? 600 : 400
              }}
            >
              <span style={{ fontSize: '0.9rem' }}>User Management</span>
            </div>
          )}
        </div>

        {/* Bottom actions */}
        <div style={{ padding: '1rem', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'center' }}>
           <button onClick={onLogout} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
             <LogOut size={18} /> <span style={{ fontSize: '0.8rem' }}>Logout [{role}]</span>
           </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        
        {/* Topbar */}
        <header style={{ height: '60px', display: 'flex', alignItems: 'center', padding: '0 1.5rem', borderBottom: '1px solid var(--border)', justifyContent: 'space-between', backgroundColor: 'var(--bg-panel)' }}>
           <div style={{ fontSize: '0.88rem', color: 'var(--text-muted)' }}>
             SARI SOC <span style={{ margin: '0 0.5rem', opacity: 0.5 }}>›</span> main <span style={{ margin: '0 0.5rem', opacity: 0.5 }}>›</span> <span style={{ color: 'var(--primary)', fontWeight: 600 }}>{activeTab === 'chat' ? 'Chat' : activeTab === 'hardware' ? 'Hardware' : 'Admin'}</span>
           </div>

           <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '0.35rem 0.9rem', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', border: '1px solid var(--border)' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: state?.siren_active ? 'var(--danger)' : 'var(--primary)', boxShadow: state?.siren_active ? '0 0 8px var(--danger)' : '0 0 8px var(--primary-glow)' }}></div>
              <span style={{ color: 'var(--text-main)', fontWeight: 500 }}>{state?.siren_active ? 'Siren Active' : 'System Normal'}</span>
           </div>
        </header>

        {/* Content Body */}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          {activeTab === 'chat' ? (
            <ChatPanel token={token} role={role} requestPin={requestPin} fetchState={fetchState} lastAlertThreadId={state?.last_alert_thread_id} />
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
