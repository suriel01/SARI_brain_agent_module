import { useState, useEffect, useRef } from 'react';
import { Crosshair, Video, AlertCircle } from 'lucide-react';

export default function CameraFeed() {
  const [fps, setFps] = useState(30);
  const [confidence, setConfidence] = useState(99.4);
  const [mode, setMode] = useState<'demo' | 'hikvision'>('demo');
  const [hikvisionUrl, setHikvisionUrl] = useState('http://192.168.1.200:8080/video');
  const [streamError, setStreamError] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeCam = 'Jetson-PTZ_1';

  // Animated CCTV video simulation on Canvas (Demo mode)
  useEffect(() => {
    if (mode !== 'demo') return;
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
  }, [mode, confidence]);

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
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e6edf3' }}>Live Perception ({activeCam})</span>
          
          {/* Mode Selector */}
          <div style={{ display: 'flex', background: '#0d1117', padding: '2px', borderRadius: '6px', border: '1px solid #30363d' }}>
            <button 
              onClick={() => { setMode('demo'); setStreamError(false); }}
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.75rem',
                borderRadius: '4px',
                border: 'none',
                background: mode === 'demo' ? 'rgba(255, 51, 102, 0.2)' : 'transparent',
                color: mode === 'demo' ? '#ff3366' : '#8b949e',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Simulación YOLO
            </button>
            <button 
              onClick={() => { setMode('hikvision'); setStreamError(false); }}
              style={{
                padding: '0.25rem 0.6rem',
                fontSize: '0.75rem',
                borderRadius: '4px',
                border: 'none',
                background: mode === 'hikvision' ? 'rgba(255, 51, 102, 0.2)' : 'transparent',
                color: mode === 'hikvision' ? '#ff3366' : '#8b949e',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Cámara Hikvision Real
            </button>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', background: 'rgba(255, 51, 102, 0.15)', border: '1px solid rgba(255, 51, 102, 0.3)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: '#ff3366', fontWeight: 600 }}>
            {mode === 'demo' ? 'YOLOv8 Active Stream' : 'RTSP / HTTP Stream'}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>{fps} FPS</span>
        </div>
      </div>

      {/* Main Stream Viewport */}
      <div style={{ 
        position: 'relative', 
        width: '100%', 
        height: '340px', 
        backgroundColor: '#04060a', 
        borderRadius: '10px', 
        overflow: 'hidden', 
        border: '1px solid #30363d'
      }}>
        
        {mode === 'demo' ? (
          <canvas 
            ref={canvasRef} 
            width={700} 
            height={340} 
            style={{ width: '100%', height: '100%', display: 'block' }}
          />
        ) : (
          <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', position: 'relative' }}>
            {!streamError ? (
              <img 
                src={hikvisionUrl} 
                alt="Hikvision Stream"
                onError={() => setStreamError(true)}
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.8rem', padding: '2rem', textAlign: 'center', color: '#8b949e' }}>
                <AlertCircle size={36} color="#ff3366" />
                <div style={{ color: '#e6edf3', fontWeight: 600, fontSize: '0.95rem' }}>Transmisión RTSP / HTTP de Hikvision No Detectada</div>
                <div style={{ fontSize: '0.8rem', maxWidth: '520px', lineHeight: '1.4' }}>
                  Los navegadores web no pueden reproducir directamente URLs <code>rtsp://</code> sin un servidor intermedio.
                  Para transmitir el video de tu cámara Hikvision en vivo, el módulo Jetson debe servir el stream mediante un servidor <strong>MJPEG HTTP</strong> o <strong>WebRTC</strong> (ej: <code>http://192.168.1.200:8080/video</code>).
                </div>
              </div>
            )}
          </div>
        )}

        {/* HUD Crosshair */}
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.3, pointerEvents: 'none' }}>
          <Crosshair size={44} color="#ff3366" />
        </div>

        {/* HUD Top Info */}
        <div style={{ position: 'absolute', top: '12px', left: '12px', display: 'flex', gap: '0.5rem', alignItems: 'center', pointerEvents: 'none' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#ff3366', animation: 'pulse 1s infinite' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#ff3366', letterSpacing: '1px' }}>
            {mode === 'demo' ? 'SIMULATED STREAM' : 'HIKVISION CAMERA'}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e', marginLeft: '0.5rem' }}>1080p @ {fps}FPS</span>
        </div>

        {/* HUD Bottom Info */}
        <div style={{ position: 'absolute', bottom: '10px', right: '12px', fontSize: '0.7rem', color: '#8b949e', fontFamily: 'monospace', pointerEvents: 'none' }}>
          STREAM: Jetson-PTZ_1 | RTSP 192.168.1.200 OK
        </div>
      </div>

      {/* Hikvision Configuration Bar */}
      {mode === 'hikvision' && (
        <div style={{ backgroundColor: '#161b22', border: '1px solid #30363d', padding: '0.8rem 1rem', borderRadius: '8px', display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <Video size={18} color="#ff3366" />
          <span style={{ fontSize: '0.8rem', color: '#8b949e', fontWeight: 600 }}>URL de Transmisión HTTP/MJPEG Hikvision:</span>
          <input 
            type="text" 
            value={hikvisionUrl}
            onChange={(e) => { setHikvisionUrl(e.target.value); setStreamError(false); }}
            placeholder="http://192.168.1.200:8080/video"
            style={{ flex: 1, background: '#0d1117', border: '1px solid #30363d', color: '#c9d1d9', padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem', outline: 'none' }}
          />
          <button 
            onClick={() => setStreamError(false)}
            style={{ background: '#ff3366', border: 'none', color: '#fff', padding: '0.4rem 0.8rem', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
          >
            Conectar
          </button>
        </div>
      )}
    </div>
  );
}
