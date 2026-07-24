import { BellRing, Lock, AlertTriangle } from 'lucide-react';
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

      {/* Middle Section: Manual Controls */}
      <div className="glass-panel" style={{ padding: '1.5rem', marginBottom: '2rem' }}>
        <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1rem' }}>Controles Físicos (PIN Requerido)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
          <button 
            className={`btn ${role === 'admin' ? 'btn-danger' : 'btn-secondary'}`}
            onClick={() => handleManualAction('activar_sirena')}
            style={{ padding: '1rem', opacity: role === 'admin' ? 1 : 0.5, cursor: role === 'admin' ? 'pointer' : 'not-allowed' }}
            disabled={role !== 'admin'}
          >
            <BellRing size={18} /> Activar Sirena
          </button>
          <button 
            className="btn btn-secondary" 
            onClick={() => handleManualAction('desactivar_sirena')}
            style={{ padding: '1rem', opacity: role === 'admin' ? 1 : 0.5, cursor: role === 'admin' ? 'pointer' : 'not-allowed' }}
            disabled={role !== 'admin'}
          >
            <AlertTriangle size={18} /> Desactivar Sirena
          </button>
          <button 
            className="btn btn-secondary" 
            onClick={() => handleManualAction('cerrar_accesos')}
            style={{ padding: '1rem', opacity: role === 'admin' ? 1 : 0.5, cursor: role === 'admin' ? 'pointer' : 'not-allowed' }}
            disabled={role !== 'admin'}
          >
            <Lock size={18} /> Bloquear Portones
          </button>
        </div>
      </div>

      {/* Bottom Section: Event Table */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1rem' }}>Registro de Eventos (Event Logs)</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
              <th style={{ padding: '0.8rem' }}>Timestamp</th>
              <th style={{ padding: '0.8rem' }}>Nivel</th>
              <th style={{ padding: '0.8rem' }}>Cámara/Módulo</th>
              <th style={{ padding: '0.8rem' }}>Evento</th>
            </tr>
          </thead>
          <tbody>
            {state?.logs?.map((log: any, idx: number) => (
              <tr key={idx} style={{ borderBottom: '1px solid rgba(48, 54, 61, 0.5)' }}>
                <td style={{ padding: '0.8rem', color: '#c9d1d9', opacity: 0.8 }}>{log.timestamp}</td>
                <td style={{ padding: '0.8rem' }}>
                  <span style={{ 
                    padding: '0.2rem 0.5rem', 
                    borderRadius: '4px', 
                    background: log.level === 'WARN' ? 'rgba(234, 179, 8, 0.1)' : log.level === 'ERROR' ? 'rgba(255, 0, 60, 0.1)' : 'rgba(46, 160, 67, 0.1)',
                    color: log.level === 'WARN' ? '#eab308' : log.level === 'ERROR' ? '#ff003c' : '#2ea043'
                  }}>
                    {log.level}
                  </span>
                </td>
                <td style={{ padding: '0.8rem', color: '#8b949e' }}>SYS_CORE</td>
                <td style={{ padding: '0.8rem', color: '#c9d1d9' }}>{log.message}</td>
              </tr>
            ))}
            {(!state?.logs || state.logs.length === 0) && (
              <tr>
                <td colSpan={4} style={{ padding: '1rem', textAlign: 'center', color: '#8b949e', fontStyle: 'italic' }}>Sin eventos recientes.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

    </div>
  );
}
