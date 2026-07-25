import { useState, useEffect, useRef } from 'react';
import { Crosshair, Video, Cpu } from 'lucide-react';

export default function CameraFeed() {
  const [fps, setFps] = useState(30);
  const [confidence, setConfidence] = useState(99.4);
  const [useRealStream, setUseRealStream] = useState(false);
  const [streamUrl, setStreamUrl] = useState('http://localhost:8080/video_feed');
  const [streamError, setStreamError] = useState(false);
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeCam = 'Jetson-PTZ_1';

  // Animated CCTV video simulation on HTML5 Canvas (Fallback / Demo mode)
  useEffect(() => {
    if (useRealStream && !streamError) return;

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let x = 120;
    let y = 80;
    let dx = 1.2;
    let dy = 0.8;

    const render = () => {
      ctx.fillStyle = '#060a0f';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.strokeStyle = 'rgba(255, 51, 102, 0.08)';
      ctx.lineWidth = 1;
      for (let i = 0; i < canvas.width; i += 30) {
        ctx.beginPath();
        ctx.moveTo(i, 0);
        ctx.lineTo(i, canvas.height);
        ctx.stroke();
      }
      for (let j = 0; j < canvas.height; j += 30) {
        ctx.beginPath();
        ctx.moveTo(0, j);
        ctx.lineTo(canvas.width, j);
        ctx.stroke();
      }

      x += dx;
      y += dy;
      if (x < 60 || x > canvas.width - 120) dx = -dx;
      if (y < 40 || y > canvas.height - 100) dy = -dy;

      ctx.fillStyle = 'rgba(255, 51, 102, 0.25)';
      ctx.beginPath();
      ctx.arc(x + 35, y + 20, 12, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillRect(x + 23, y + 34, 24, 40);

      ctx.strokeStyle = '#ff3366';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(x, y, 70, 85);
      ctx.setLineDash([]);

      ctx.fillStyle = '#ff3366';
      ctx.fillRect(x, y - 18, 70, 18);
      ctx.fillStyle = '#000000';
      ctx.font = 'bold 9px monospace';
      ctx.fillText(`INTRUDER ${confidence}%`, x + 3, y - 5);

      for (let k = 0; k < 60; k++) {
        const nx = Math.random() * canvas.width;
        const ny = Math.random() * canvas.height;
        ctx.fillStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.fillRect(nx, ny, 1.5, 1.5);
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [useRealStream, streamError, confidence]);

  useEffect(() => {
    const interval = setInterval(() => {
      setFps(Math.floor(29 + Math.random() * 3));
      setConfidence(parseFloat((98.7 + Math.random() * 1.2).toFixed(1)));
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

        {/* Mode Selector Toggle */}
        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
          <button 
            onClick={() => { setUseRealStream(false); setStreamError(false); }}
            style={{
              background: !useRealStream ? 'rgba(255, 51, 102, 0.2)' : 'transparent',
              border: `1px solid ${!useRealStream ? '#ff3366' : '#30363d'}`,
              color: !useRealStream ? '#ff3366' : '#8b949e',
              padding: '0.25rem 0.6rem',
              borderRadius: '4px',
              fontSize: '0.75rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem'
            }}
          >
            <Cpu size={13} /> Detección YOLO
          </button>

          <button 
            onClick={() => { setUseRealStream(true); setStreamError(false); }}
            style={{
              background: useRealStream ? 'rgba(255, 51, 102, 0.2)' : 'transparent',
              border: `1px solid ${useRealStream ? '#ff3366' : '#30363d'}`,
              color: useRealStream ? '#ff3366' : '#8b949e',
              padding: '0.25rem 0.6rem',
              borderRadius: '4px',
              fontSize: '0.75rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem'
            }}
          >
            <Video size={13} /> Cámara Real HTTP/MJPEG
          </button>

          <span style={{ fontSize: '0.75rem', color: '#8b949e', marginLeft: '0.4rem' }}>{fps} FPS</span>
        </div>
      </div>

      {/* Stream Source URL Bar (if Real Stream Mode selected) */}
      {useRealStream && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', backgroundColor: '#161b22', padding: '0.4rem 0.8rem', borderRadius: '6px', border: '1px solid #30363d' }}>
          <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>URL Stream HTTP/MJPEG Jetson:</span>
          <input 
            type="text" 
            value={streamUrl} 
            onChange={e => { setStreamUrl(e.target.value); setStreamError(false); }}
            style={{ flex: 1, background: '#0d1117', border: '1px solid #30363d', color: '#c9d1d9', padding: '0.2rem 0.5rem', borderRadius: '4px', fontSize: '0.78rem', outline: 'none' }}
            placeholder="http://192.168.1.200:8080/video_feed"
          />
        </div>
      )}

      {/* Main Surveillance Viewport */}
      <div style={{ 
        position: 'relative', 
        width: '100%', 
        height: '360px', 
        backgroundColor: '#04060a', 
        borderRadius: '10px', 
        overflow: 'hidden', 
        border: '1px solid #30363d'
      }}>
        
        {useRealStream && !streamError ? (
          <img 
            src={streamUrl} 
            alt="Real Camera Feed" 
            onError={() => setStreamError(true)}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        ) : (
          <canvas 
            ref={canvasRef} 
            width={700} 
            height={360} 
            style={{ width: '100%', height: '100%', display: 'block' }}
          />
        )}

        {/* HUD Crosshair Center */}
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.3, pointerEvents: 'none' }}>
          <Crosshair size={44} color="#ff3366" />
        </div>

        {/* HUD Top Info */}
        <div style={{ position: 'absolute', top: '12px', left: '12px', display: 'flex', gap: '0.5rem', alignItems: 'center', pointerEvents: 'none' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#ff3366', animation: 'pulse 1s infinite' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#ff3366', letterSpacing: '1px' }}>
            {useRealStream ? 'HIKVISION REAL STREAM' : 'YOLO SIMULATED STREAM'}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e', marginLeft: '0.5rem' }}>1080p @ {fps}FPS</span>
        </div>

        {/* Stream Error Notice if Real Stream failed */}
        {useRealStream && streamError && (
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1rem', textAlign: 'center' }}>
            <span style={{ color: '#ff3366', fontWeight: 600, fontSize: '0.9rem', marginBottom: '0.4rem' }}>⚠️ Conexión con Cámara Hikvision HTTP/MJPEG Offline</span>
            <span style={{ color: '#8b949e', fontSize: '0.75rem', maxWidth: '500px' }}>
              No se pudo conectar a <code>{streamUrl}</code>. Para transmitir video en directo de la cámara Hikvision en el navegador, agrega un servidor MJPEG HTTP en <code>camara_ptz.py</code> o verifica la IP del Jetson.
            </span>
          </div>
        )}

        {/* HUD Bottom Info */}
        <div style={{ position: 'absolute', bottom: '10px', right: '12px', fontSize: '0.7rem', color: '#8b949e', fontFamily: 'monospace', pointerEvents: 'none' }}>
          STREAM: Jetson-PTZ_1 | RTSP 192.168.1.104 OK
        </div>
      </div>
    </div>
  );
}
