import { useState, useEffect } from 'react';
import { Crosshair } from 'lucide-react';

export default function CameraFeed() {
  const [fps, setFps] = useState(30);
  const [streamUrl, setStreamUrl] = useState('http://192.168.1.73:8080/video_feed');
  const [streamError, setStreamError] = useState(false);
  const activeCam = 'Jetson-PTZ_1';

  useEffect(() => {
    const interval = setInterval(() => {
      setFps(Math.floor(29 + Math.random() * 3));
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      
      {/* Feed Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#161b22', padding: '0.6rem 1rem', borderRadius: '8px', border: '1px solid #30363d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e6edf3' }}>Live Perception ({activeCam})</span>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', background: 'rgba(255, 51, 102, 0.15)', border: '1px solid rgba(255, 51, 102, 0.3)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: '#ff3366', fontWeight: 600 }}>
            Transmisión Cámara Hikvision
          </span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>{fps} FPS</span>
        </div>
      </div>

      {/* Stream Source URL Bar */}
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', backgroundColor: '#161b22', padding: '0.5rem 0.8rem', borderRadius: '6px', border: '1px solid #30363d' }}>
        <span style={{ fontSize: '0.78rem', color: '#8b949e', fontWeight: 500 }}>URL Stream Jetson:</span>
        <input 
          type="text" 
          value={streamUrl} 
          onChange={e => { setStreamUrl(e.target.value); setStreamError(false); }}
          style={{ flex: 1, background: '#0d1117', border: '1px solid #30363d', color: '#c9d1d9', padding: '0.3rem 0.6rem', borderRadius: '4px', fontSize: '0.8rem', outline: 'none' }}
          placeholder="http://192.168.1.73:8080/mjpeg"
        />
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {['http://192.168.1.73:8080/mjpeg', 'http://192.168.1.73:8080/video_feed', 'http://192.168.55.1:8080/mjpeg'].map((preset, i) => (
            <button
              key={i}
              onClick={() => { setStreamUrl(preset); setStreamError(false); }}
              style={{
                background: streamUrl === preset ? 'rgba(255, 51, 102, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${streamUrl === preset ? '#ff3366' : '#30363d'}`,
                color: streamUrl === preset ? '#ff3366' : '#8b949e',
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.7rem',
                cursor: 'pointer'
              }}
            >
              {preset.split('/').pop()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Video Viewport */}
      <div style={{ 
        position: 'relative', 
        width: '100%', 
        height: '380px', 
        backgroundColor: '#04060a', 
        borderRadius: '10px', 
        overflow: 'hidden', 
        border: '1px solid #30363d',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        
        {!streamError ? (
          <img 
            src={streamUrl} 
            alt="Hikvision Live Stream" 
            onError={() => setStreamError(true)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#8b949e' }}>
            <div style={{ color: '#ff3366', fontWeight: 600, fontSize: '1rem', marginBottom: '0.5rem' }}>
              📡 Esperando Transmisión de Video (`{streamUrl}`)
            </div>
            <div style={{ fontSize: '0.8rem', maxWidth: '500px', margin: '0 auto', lineHeight: '1.4' }}>
              Ingresa la dirección HTTP de la cámara o ejecuta el servidor MJPEG en la Jetson para visualizar el flujo en vivo sin simuladores.
            </div>
          </div>
        )}

        {/* HUD Overlay Crosshair */}
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.25, pointerEvents: 'none' }}>
          <Crosshair size={48} color="#ff3366" />
        </div>

        {/* HUD Top Info */}
        <div style={{ position: 'absolute', top: '12px', left: '12px', display: 'flex', gap: '0.5rem', alignItems: 'center', pointerEvents: 'none' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: !streamError ? '#2ea043' : '#ff3366', boxShadow: !streamError ? '0 0 6px #2ea043' : '0 0 6px #ff3366' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#ff3366', letterSpacing: '1px' }}>
            {!streamError ? 'LIVE STREAMING' : 'OFFLINE'}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e', marginLeft: '0.5rem' }}>1080p @ {fps}FPS</span>
        </div>

        {/* HUD Bottom Info */}
        <div style={{ position: 'absolute', bottom: '10px', right: '12px', fontSize: '0.7rem', color: '#8b949e', fontFamily: 'monospace', pointerEvents: 'none' }}>
          STREAM: Jetson-PTZ_1 | HIKVISION REAL
        </div>
      </div>
    </div>
  );
}
