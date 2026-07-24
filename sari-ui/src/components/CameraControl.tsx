import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Video, ZoomIn, ZoomOut } from 'lucide-react';
import { useState } from 'react';

export default function CameraControl() {
  const [activeCam, setActiveCam] = useState(1);
  const [isPowerOn, setIsPowerOn] = useState(true);
  const [action, setAction] = useState<string | null>(null);

  const simulateAction = (act: string) => {
    setAction(act);
    setTimeout(() => setAction(null), 300);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%', alignItems: 'center' }}>
      
      {/* Cam Selector */}
      <div style={{ display: 'flex', gap: '0.5rem', width: '100%' }}>
        {[1, 2, 3, 4].map(num => (
          <button 
            key={num}
            onClick={() => setActiveCam(num)}
            style={{ 
              flex: 1, 
              padding: '0.5rem', 
              background: activeCam === num ? 'var(--primary-glow)' : 'transparent',
              border: `1px solid ${activeCam === num ? 'var(--primary)' : 'var(--border)'}`,
              color: activeCam === num ? 'var(--text-main)' : 'var(--text-muted)',
              borderRadius: '4px',
              cursor: 'pointer'
            }}>
            CAM 0{num}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '2rem', marginTop: '1rem' }}>
        
        {/* PTZ D-Pad */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem', opacity: isPowerOn ? 1 : 0.5 }}>
          <div />
          <button onClick={() => simulateAction('UP')} className="btn btn-secondary" disabled={!isPowerOn} style={{ padding: '0.8rem', background: action === 'UP' ? 'var(--primary)' : '' }}>
            <ArrowUp size={20} />
          </button>
          <div />
          
          <button onClick={() => simulateAction('LEFT')} className="btn btn-secondary" disabled={!isPowerOn} style={{ padding: '0.8rem', background: action === 'LEFT' ? 'var(--primary)' : '' }}>
            <ArrowLeft size={20} />
          </button>
          <button onClick={() => setIsPowerOn(!isPowerOn)} className="btn btn-secondary" style={{ padding: '0.8rem', color: isPowerOn ? 'var(--primary)' : 'var(--danger)' }}>
            <Video size={20} />
          </button>
          <button onClick={() => simulateAction('RIGHT')} className="btn btn-secondary" disabled={!isPowerOn} style={{ padding: '0.8rem', background: action === 'RIGHT' ? 'var(--primary)' : '' }}>
            <ArrowRight size={20} />
          </button>
          
          <div />
          <button onClick={() => simulateAction('DOWN')} className="btn btn-secondary" disabled={!isPowerOn} style={{ padding: '0.8rem', background: action === 'DOWN' ? 'var(--primary)' : '' }}>
            <ArrowDown size={20} />
          </button>
          <div />
        </div>

        {/* Zoom Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', opacity: isPowerOn ? 1 : 0.5 }}>
           <button onClick={() => simulateAction('ZOOM_IN')} className="btn btn-secondary" disabled={!isPowerOn} style={{ flex: 1, background: action === 'ZOOM_IN' ? 'var(--primary)' : '' }}>
             <ZoomIn size={20} />
           </button>
           <button onClick={() => simulateAction('ZOOM_OUT')} className="btn btn-secondary" disabled={!isPowerOn} style={{ flex: 1, background: action === 'ZOOM_OUT' ? 'var(--primary)' : '' }}>
             <ZoomOut size={20} />
           </button>
        </div>
      </div>
      
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
        {isPowerOn ? `Conectado a CAM 0${activeCam} - Protocolo PTZ Listo` : 'Cámara Desconectada'}
      </div>
    </div>
  );
}
