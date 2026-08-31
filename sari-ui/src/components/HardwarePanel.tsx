import { useState } from 'react';
import { BellRing, Lock, Search, Filter, Clock, Download, Trash2, Expand, Minimize2 } from 'lucide-react';
import RadarMap from './RadarMap';
import Telemetry from './Telemetry';
import NodeStatus from './NodeStatus';
import { apiFetch, readErrorDetail } from '../api';
import type { Permissions } from '../permissions';

interface HardwarePanelProps {
  token: string;
  permissions: Permissions;
  requestPin: (actionName: string, callback: (pin: string) => void) => void;
  state: any;
  fetchState: () => void;
}

export default function HardwarePanel({ token, permissions, requestPin, state, fetchState }: HardwarePanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [moduleFilter, setModuleFilter] = useState('ALL');
  const [isLogsExpanded, setIsLogsExpanded] = useState(false);
  
  const handleManualAction = (actionName: string) => {
    if (!permissions.canControlHardware) {
      alert('Permission denied: Hardware control required.');
      return;
    }
    requestPin(actionName, async (pin) => {
      try {
        const res = await apiFetch('/manual_action', token, {
          method: 'POST',
          body: JSON.stringify({ action: actionName, pin })
        });
        if (!res.ok) {
          alert(await readErrorDetail(res, 'Error executing hardware action.'));
        }
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

    if (log.expires_at) {
      const exp = new Date(String(log.expires_at).replace(' ', 'T'));
      if (!Number.isNaN(exp.getTime()) && exp.getTime() <= Date.now()) return false;
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
           <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '0', alignSelf: 'flex-start' }}>Hardware Node Status</h3>
           <NodeStatus />
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
              opacity: permissions.canControlHardware ? 1 : 0.5, 
              cursor: permissions.canControlHardware ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.6rem',
              fontWeight: 600
            }}
            disabled={!permissions.canControlHardware}
          >
            <BellRing size={18} /> {state?.siren_active ? 'Siren (Active - Click to Deactivate)' : 'Siren (Off - Click to Activate)'}
          </button>

          {/* Single Gates Toggle Button */}
          <button 
            className={`btn ${state?.gates_locked ? 'btn-danger' : 'btn-secondary'}`}
            onClick={() => handleManualAction('toggle_accesos')}
            style={{ 
              padding: '1rem', 
              opacity: permissions.canControlHardware ? 1 : 0.5, 
              cursor: permissions.canControlHardware ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.6rem',
              fontWeight: 600,
              border: state?.gates_locked ? '1px solid #eab308' : '1px solid #30363d',
              color: state?.gates_locked ? '#eab308' : '#c9d1d9'
            }}
            disabled={!permissions.canControlHardware}
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
            
            {/* Export and Clear buttons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginLeft: 'auto' }}>
              <button 
                onClick={() => {
                  const blob = new Blob([JSON.stringify(filteredLogs, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `sari_event_logs_${new Date().toISOString().split('T')[0]}.json`;
                  a.click();
                }}
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid #30363d', color: '#c9d1d9', padding: '0.4rem 0.6rem', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.75rem' }}
                title="Export Logs"
              >
                <Download size={14} /> Export
              </button>
              
              <button
                onClick={() => alert("Función 'Clear Logs' requiere persistencia en la base de datos (por implementar).")}
                style={{ background: 'rgba(255,0,0,0.1)', border: '1px solid rgba(255,0,0,0.2)', color: '#ff4444', padding: '0.4rem 0.6rem', borderRadius: '4px', display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', fontSize: '0.75rem' }}
                title="Clear Logs"
              >
                <Trash2 size={14} /> Clear
              </button>
            </div>
          </div>
        </div>

        {/* Expand / Collapse Control */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
          <button 
            onClick={() => setIsLogsExpanded(!isLogsExpanded)}
            style={{ background: 'transparent', border: 'none', color: '#58a6ff', fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.3rem' }}
          >
            {isLogsExpanded ? <><Minimize2 size={12} /> Mostrar recientes (20)</> : <><Expand size={12} /> Expandir todos ({filteredLogs.length})</>}
          </button>
        </div>

        {/* Logs Table */}
        <div style={{ maxHeight: isLogsExpanded ? 'none' : '400px', overflowY: 'auto', border: '1px solid #30363d', borderRadius: '6px' }}>
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
            {(isLogsExpanded ? filteredLogs : filteredLogs.slice(0, 20)).map((log: any, idx: number) => (
              <tr key={idx} style={{ borderBottom: '1px solid rgba(48, 54, 61, 0.5)' }}>
                <td style={{ padding: '0.8rem', color: '#c9d1d9', opacity: 0.8, whiteSpace: 'nowrap' }}>{log.timestamp}</td>
                <td style={{ padding: '0.8rem' }}>
                  <span style={{ 
                    padding: '0.2rem 0.5rem', 
                    borderRadius: '4px', 
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    background: log.level === 'WARN' ? 'rgba(234, 179, 8, 0.15)' : log.level === 'ERROR' ? 'rgba(255, 0, 60, 0.15)' : 'rgba(88, 166, 255, 0.15)',
                    color: log.level === 'WARN' ? '#eab308' : log.level === 'ERROR' ? '#ff003c' : '#58a6ff'
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

    </div>
  );
}
