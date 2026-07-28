import { useState } from 'react';
import { BellRing, Lock, Search, Filter, Clock } from 'lucide-react';
import RadarMap from './RadarMap';
import Telemetry from './Telemetry';
import CameraControl from './CameraControl';

interface HardwarePanelProps {
  token: string;
  role: string;
  requestPin: (actionName: string, callback: (pin: string) => void) => void;
  state: any;
  fetchState: () => void;
}

const API_BASE = 'http://localhost:7000/api';

export default function HardwarePanel({ token, role, requestPin, state, fetchState }: HardwarePanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [moduleFilter, setModuleFilter] = useState('ALL');
  
  const handleManualAction = (actionName: string) => {
    requestPin(actionName, async (pin) => {
      try {
        await fetch(`${API_BASE}/manual_action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ action: actionName, pin })
        });
        fetchState();
      } catch (e) {
        console.error('Error executing manual action', e);
      }
    });
  };

  // Filter logs based on query, level, module and non-expired TTL
  const filteredLogs = (state?.logs || []).filter((log: any) => {
    // Check level
    if (levelFilter !== 'ALL' && log.level !== levelFilter) return false;

    // Check module
    const mod = log.camera_module || 'SYS_CORE';
    if (moduleFilter !== 'ALL' && mod !== moduleFilter) return false;

    // Check search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchMsg = (log.message || '').toLowerCase().includes(q);
      const matchMod = mod.toLowerCase().includes(q);
      const matchLevel = (log.level || '').toLowerCase().includes(q);
      const matchTs = (log.timestamp || '').toLowerCase().includes(q);
      if (!matchMsg && !matchMod && !matchLevel && !matchTs) return false;
    }

    return true;
  });

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      
      {/* Top Section: Radar, Telemetry and PTZ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1rem', alignSelf: 'flex-start' }}>Perimeter Scan</h3>
          <RadarMap />
        </div>

        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
           <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1rem' }}>System Telemetry</h3>
           <Telemetry />
        </div>

        <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
           <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1rem', alignSelf: 'flex-start' }}>PTZ Camera Control</h3>
           <CameraControl />
        </div>
      </div>

      {/* Middle Section: Manual Controls (Single Toggle Buttons) */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1rem' }}>Physical Controls (PIN Required)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          
          {/* Single Siren Toggle Button */}
          <button 
            className={`btn ${state?.siren_active ? 'btn-danger' : 'btn-secondary'}`}
            onClick={() => handleManualAction('toggle_sirena')}
            style={{ 
              padding: '1rem', 
              opacity: role === 'admin' ? 1 : 0.5, 
              cursor: role === 'admin' ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.6rem',
              fontWeight: 600
            }}
            disabled={role !== 'admin'}
          >
            <BellRing size={18} /> {state?.siren_active ? 'Siren (Active - Click to Deactivate)' : 'Siren (Off - Click to Activate)'}
          </button>

          {/* Single Gates Toggle Button */}
          <button 
            className={`btn ${state?.gates_locked ? 'btn-danger' : 'btn-secondary'}`}
            onClick={() => handleManualAction('toggle_accesos')}
            style={{ 
              padding: '1rem', 
              opacity: role === 'admin' ? 1 : 0.5, 
              cursor: role === 'admin' ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.6rem',
              fontWeight: 600,
              border: state?.gates_locked ? '1px solid #eab308' : '1px solid #30363d',
              color: state?.gates_locked ? '#eab308' : '#c9d1d9'
            }}
            disabled={role !== 'admin'}
          >
            <Lock size={18} /> {state?.gates_locked ? 'Gates Locked (Click to Unlock)' : 'Lock Gates (Click to Lock)'}
          </button>

        </div>
      </div>

      {/* Bottom Section: Event Table with Filters & TTL Expiration */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        
        {/* Header & Filter Controls Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.2rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', margin: 0 }}>Event Logs & System Auditing</h3>
            <span style={{ fontSize: '0.72rem', background: 'rgba(0, 240, 255, 0.1)', color: '#00f0ff', padding: '0.15rem 0.5rem', borderRadius: '12px', border: '1px solid rgba(0, 240, 255, 0.3)' }}>
              TTL: 24 Horas
            </span>
          </div>

          {/* Filters Bar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
            {/* Search Input */}
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <Search size={14} color="#8b949e" style={{ position: 'absolute', left: '0.6rem' }} />
              <input
                type="text"
                placeholder="Search logs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  padding: '0.4rem 0.6rem 0.4rem 2rem',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  color: '#e6edf3',
                  fontSize: '0.8rem',
                  width: '180px'
                }}
              />
            </div>

            {/* Level Filter Dropdown */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
              <Filter size={14} color="#8b949e" />
              <select
                value={levelFilter}
                onChange={(e) => setLevelFilter(e.target.value)}
                style={{
                  padding: '0.4rem 0.6rem',
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  color: '#e6edf3',
                  fontSize: '0.8rem',
                  cursor: 'pointer'
                }}
              >
                <option value="ALL">All Levels</option>
                <option value="INFO">INFO</option>
                <option value="WARN">WARN</option>
                <option value="ERROR">ERROR</option>
              </select>
            </div>

            {/* Module Filter Dropdown */}
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              style={{
                padding: '0.4rem 0.6rem',
                background: '#0d1117',
                border: '1px solid #30363d',
                borderRadius: '6px',
                color: '#e6edf3',
                fontSize: '0.8rem',
                cursor: 'pointer'
              }}
            >
              <option value="ALL">All Modules</option>
              <option value="SYS_CORE">SYS_CORE</option>
              <option value="CHAT_USER">CHAT_USER</option>
              <option value="CHAT_AGENT">CHAT_AGENT</option>
              <option value="CHAT_MGMT">CHAT_MGMT</option>
              <option value="HARDWARE_CTRL">HARDWARE_CTRL</option>
              <option value="AUTH_SYS">AUTH_SYS</option>
              <option value="JETSON_CV">JETSON_CV</option>
            </select>
          </div>
        </div>

        {/* Logs Table */}
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
              <th style={{ padding: '0.8rem' }}>Timestamp</th>
              <th style={{ padding: '0.8rem' }}>Level</th>
              <th style={{ padding: '0.8rem' }}>Module</th>
              <th style={{ padding: '0.8rem' }}>Event Description</th>
              <th style={{ padding: '0.8rem' }}>TTL / Expiration</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log: any, idx: number) => (
              <tr key={idx} style={{ borderBottom: '1px solid rgba(48, 54, 61, 0.5)' }}>
                <td style={{ padding: '0.8rem', color: '#c9d1d9', opacity: 0.8, whiteSpace: 'nowrap' }}>{log.timestamp}</td>
                <td style={{ padding: '0.8rem' }}>
                  <span style={{ 
                    padding: '0.2rem 0.5rem', 
                    borderRadius: '4px', 
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: log.level === 'WARN' ? 'rgba(234, 179, 8, 0.15)' : log.level === 'ERROR' ? 'rgba(255, 0, 60, 0.15)' : 'rgba(255, 51, 102, 0.15)',
                    color: log.level === 'WARN' ? '#eab308' : log.level === 'ERROR' ? '#ff003c' : 'var(--primary)'
                  }}>
                    {log.level}
                  </span>
                </td>
                <td style={{ padding: '0.8rem' }}>
                  <span style={{ background: 'rgba(255,255,255,0.04)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: '#58a6ff', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                    {log.camera_module || 'SYS_CORE'}
                  </span>
                </td>
                <td style={{ padding: '0.8rem', color: '#c9d1d9' }}>{log.message}</td>
                <td style={{ padding: '0.8rem', color: '#8b949e', fontSize: '0.78rem', whiteSpace: 'nowrap' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#2ea043' }}>
                    <Clock size={12} /> {log.expires_at ? log.expires_at : '24h Auto-Purge'}
                  </span>
                </td>
              </tr>
            ))}
            {filteredLogs.length === 0 && (
              <tr>
                <td colSpan={5} style={{ padding: '1.5rem', textAlign: 'center', color: '#8b949e', fontStyle: 'italic' }}>
                  No event logs match the selected filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
}
