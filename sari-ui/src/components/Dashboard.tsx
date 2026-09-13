import { useState, useEffect } from 'react';
import { LogOut, BellRing, Lock, PanelLeftOpen, PanelLeftClose, Sun, Moon } from 'lucide-react';
import ChatPanel from './ChatPanel';
import HardwarePanel from './HardwarePanel';
import AdminPanel from './AdminPanel';
import PinModal from './PinModal';
import EyesModule from './EyesModule';
import CircuitCanvas from './CircuitCanvas';
import { apiFetch } from '../api';
import type { Permissions } from '../permissions';
import { useLanguage } from '../i18n/LanguageContext';

interface DashboardProps {
  token: string;
  role: string;
  permissions: Permissions;
  onLogout: () => void;
  isDarkMode: boolean;
  toggleTheme: () => void;
}

export default function Dashboard({ token, role, permissions, onLogout, isDarkMode, toggleTheme }: DashboardProps) {
  const { language, setLanguage, t } = useLanguage();
  const [state, setState] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'chat' | 'perception' | 'hardware' | 'admin'>('chat');
  const [selectedEyeId, setSelectedEyeId] = useState<string | null>(null);
  
  const [moduleWidth, setModuleWidth] = useState(260);
  const [isModulesCollapsed, setIsModulesCollapsed] = useState(false);
  const [isResizingModules, setIsResizingModules] = useState(false);

  const [pinModalOpen, setPinModalOpen] = useState(false);
  const [pendingAction, setPendingAction] = useState<string>('');
  const [actionCallback, setActionCallback] = useState<((pin: string) => void) | null>(null);

  const fetchState = async () => {
    try {
      const res = await apiFetch('/hardware/state', token);
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

  useEffect(() => {
    const wsUrl = window.location.hostname === 'localhost' ? 'ws://localhost:8000/ws' : `ws://${window.location.hostname}:8000/ws`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'siren_activated' || data.event === 'siren_deactivated') {
          fetchState();
        }
      } catch (e) {
        console.error("Error parsing WS message:", e);
      }
    };
    return () => ws.close();
  }, []);

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
    const handleMouseUp = () => setIsResizingModules(false);

    if (isResizingModules) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingModules]);

  useEffect(() => {
    if (state?.siren_active) {
      try {
        const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sawtooth';
        gain.gain.value = 0.25;
        
        const now = audioCtx.currentTime;
        osc.frequency.setValueAtTime(700, now);
        for (let i = 0; i < 60; i++) {
          osc.frequency.linearRampToValueAtTime(1400, now + i * 0.7 + 0.35);
          osc.frequency.linearRampToValueAtTime(700, now + i * 0.7 + 0.7);
        }
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        return () => {
          try { osc.stop(); audioCtx.close(); } catch (e) {}
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
    if (actionCallback) actionCallback(pin);
    setPinModalOpen(false);
  };

  const handleQuickEmergencyAction = (actionName: string) => {
    if (!permissions.canControlHardware) {
      alert(t('pinRequiredAction'));
      return;
    }
    requestPin(actionName, async (pin) => {
      try {
        await apiFetch('/manual_action', token, {
          method: 'POST',
          body: JSON.stringify({ action: actionName, pin })
        });
        fetchState();
      } catch (e) {
        console.error('Error executing quick action', e);
      }
    });
  };

  const NavItem = ({ id, label, icon: Icon }: { id: typeof activeTab, label: string, icon?: any }) => {
    const isActive = activeTab === id;
    return (
      <button 
        onClick={() => setActiveTab(id)}
        className={`w-full px-4 py-2.5 rounded-full flex items-center gap-3 mb-1.5 text-sm font-medium transition-all duration-200 active:scale-98 ${
          isActive 
            ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 shadow-sm' 
            : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800/60 hover:text-zinc-900 dark:hover:text-zinc-100'
        }`}
      >
        {Icon && <Icon size={16} className={isActive ? 'text-white dark:text-zinc-950' : 'text-zinc-500 dark:text-zinc-400'} />}
        <span>{label}</span>
      </button>
    );
  };

  return (
    <div className="flex h-screen bg-zinc-100 dark:bg-zinc-950 overflow-hidden relative text-zinc-900 dark:text-zinc-100 font-sans transition-colors duration-200">
      <div className="absolute inset-0 opacity-15 dark:opacity-10 pointer-events-none">
        <CircuitCanvas />
      </div>
      
      {!isModulesCollapsed && (
        <aside 
          style={{ width: `${moduleWidth}px` }} 
          className="m-3 mr-0 bg-white/95 dark:bg-zinc-900/90 backdrop-blur-xl border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl flex flex-col py-5 px-3 shrink-0 z-20 shadow-sm transition-all"
        >
          <div className="flex items-center justify-between px-3 mb-6">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-white p-0.5 flex items-center justify-center shadow-md border border-zinc-200 dark:border-zinc-800 shrink-0">
                <img src="/sari_logo.jpeg" alt="SARI" className="w-7 h-7 object-contain rounded-lg" />
              </div>
              <div>
                <div className="text-sm font-bold tracking-tight text-zinc-900 dark:text-white leading-none">SARI AGENT</div>
                <div className="text-[10px] text-zinc-400 dark:text-zinc-500 font-medium mt-0.5">{t('socPerimeter')}</div>
              </div>
            </div>
            <button 
              onClick={() => setIsModulesCollapsed(true)} 
              className="w-7 h-7 rounded-full flex items-center justify-center text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              title={t('collapseSidebar')}
            >
              <PanelLeftClose size={16} />
            </button>
          </div>
          
          <div className="flex-1 px-1">
            <div className="text-[11px] font-semibold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider mb-2 pl-3">{t('modules')}</div>
            <NavItem id="chat" label={t('chatSari')} />
            <NavItem id="perception" label={t('livePerception')} />
            <NavItem id="hardware" label={t('hardwareControl')} />
            {permissions.canManageUsers && <NavItem id="admin" label={t('userManagement')} />}
          </div>

          <div className="pt-3 border-t border-zinc-100 dark:border-zinc-800 px-1">
             <button 
               onClick={onLogout} 
               className="w-full py-2.5 px-4 rounded-full border border-zinc-200 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-white text-xs font-semibold transition-all flex items-center justify-center gap-2 shadow-sm"
             >
               <LogOut size={14} /> <span>{t('logout')} [{role}]</span>
             </button>
          </div>
        </aside>
      )}

      {!isModulesCollapsed && (
        <div 
          onMouseDown={() => setIsResizingModules(true)} 
          className={`w-2 cursor-col-resize z-30 transition-colors ${isResizingModules ? 'bg-zinc-400/50' : 'hover:bg-zinc-300/40 dark:hover:bg-zinc-700/40'}`}
        />
      )}

      <main className="flex-1 flex flex-col overflow-hidden z-10 relative p-3 gap-3">
        <header className="h-14 flex items-center px-5 rounded-2xl bg-white/90 dark:bg-zinc-900/90 backdrop-blur-xl border border-zinc-200/80 dark:border-zinc-800/80 justify-between shadow-sm transition-colors">
           <div className="flex items-center gap-3">
             {isModulesCollapsed && (
               <button
                 onClick={() => setIsModulesCollapsed(false)}
                 title={t('expandSidebar')}
                 className="bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-2 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all shadow-sm active:scale-95"
               >
                 <PanelLeftOpen size={15} /> {t('expandSidebar')}
               </button>
             )}
             <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight flex items-center gap-2">
               <span className="w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-600"></span>
               {activeTab === 'chat' ? t('chatSari') : activeTab === 'perception' ? t('livePerception') : activeTab === 'hardware' ? t('hardwareControl') : t('userManagement')}
             </div>
           </div>

           <div className="flex items-center gap-2.5">
              {/* Language Switcher Pill (ES | EN) */}
              <div className="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-800/80 p-1 rounded-full border border-zinc-200/80 dark:border-zinc-700/80 shadow-sm">
                <button
                  onClick={() => setLanguage('es')}
                  className={`px-2.5 py-1 rounded-full text-xs font-bold transition-all active:scale-95 ${
                    language === 'es'
                      ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 shadow-sm'
                      : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white'
                  }`}
                  title="Cambiar a Español"
                >
                  ES
                </button>
                <button
                  onClick={() => setLanguage('en')}
                  className={`px-2.5 py-1 rounded-full text-xs font-bold transition-all active:scale-95 ${
                    language === 'en'
                      ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 shadow-sm'
                      : 'text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white'
                  }`}
                  title="Switch to English"
                >
                  EN
                </button>
              </div>

              <button 
                onClick={toggleTheme}
                className="w-9 h-9 rounded-full flex items-center justify-center text-zinc-600 hover:text-zinc-950 dark:text-zinc-400 dark:hover:text-white bg-zinc-100 dark:bg-zinc-800/80 hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-all border border-zinc-200/60 dark:border-zinc-700/60 shadow-sm"
                title={t('toggleTheme')}
              >
                {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
              </button>

              <div className="w-px h-5 bg-zinc-200 dark:bg-zinc-800 mx-1" />

              <button 
                onClick={() => handleQuickEmergencyAction('toggle_sirena')}
                className={`px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-2 transition-all active:scale-95 shadow-sm ${
                  state?.siren_active 
                    ? 'bg-red-600 text-white border border-red-600 shadow-md shadow-red-600/30 animate-pulse' 
                    : 'bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                }`}
              >
                <BellRing size={13} className={state?.siren_active ? 'text-white' : 'text-zinc-500 dark:text-zinc-400'} /> 
                {state?.siren_active ? t('sirenOn') : t('sirenOff')}
              </button>

              <button 
                onClick={() => handleQuickEmergencyAction('toggle_accesos')}
                className={`px-4 py-2 rounded-full text-xs font-semibold flex items-center gap-2 transition-all active:scale-95 shadow-sm ${
                  state?.gates_locked 
                    ? 'bg-amber-600 text-white border border-amber-600 shadow-md shadow-amber-600/30' 
                    : 'bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                }`}
              >
                <Lock size={13} className={state?.gates_locked ? 'text-white' : 'text-zinc-500 dark:text-zinc-400'} /> 
                {state?.gates_locked ? t('unlockGates') : t('lockGates')}
              </button>

              <div className="w-px h-5 bg-zinc-200 dark:bg-zinc-800 mx-1" />

              <div className="bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 px-3.5 py-1.5 rounded-full flex items-center gap-2 text-xs font-medium shadow-sm">
                 <div className={`w-2 h-2 rounded-full ${state?.siren_active ? 'bg-red-500 animate-ping' : state?.gates_locked ? 'bg-amber-500' : 'bg-emerald-500'}`}></div>
                 <span className="text-zinc-700 dark:text-zinc-300">
                   {state?.siren_active ? t('systemAlert') : state?.gates_locked ? t('gatesLocked') : t('systemNormal')}
                 </span>
              </div>
           </div>
        </header>

        <div className="flex-1 overflow-hidden rounded-3xl bg-white/80 dark:bg-zinc-900/80 backdrop-blur-xl border border-zinc-200/80 dark:border-zinc-800/80 shadow-sm relative">
          {activeTab === 'chat' ? (
            <ChatPanel token={token} permissions={permissions} requestPin={requestPin} fetchState={fetchState} lastAlertThreadId={state?.last_alert_thread_id} />
          ) : activeTab === 'perception' ? (
            <div className="p-4 h-full">
              <EyesModule 
                token={token} 
                permissions={permissions} 
                requestPin={requestPin} 
                initialSelectedNodeId={selectedEyeId} 
              />
            </div>
          ) : activeTab === 'hardware' ? (
            <HardwarePanel 
              token={token} 
              permissions={permissions} 
              requestPin={requestPin} 
              state={state} 
              fetchState={fetchState} 
              onNavigateToEye={(nodeId) => {
                setSelectedEyeId(nodeId);
                setActiveTab('perception');
              }}
            />
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
