import { useState, useEffect, useRef } from 'react';
import { RotateCw, FlipHorizontal, FlipVertical, Maximize2, Minimize2, RefreshCcw } from 'lucide-react';

export default function CameraFeed() {
  const [fps, setFps] = useState(30);
  const [streamUrl, setStreamUrl] = useState('http://192.168.1.73:8080/video_feed');
  const [streamError, setStreamError] = useState(false);
  const activeCam = 'Jetson-PTZ_1';

  // Dynamic Orientation & Fullscreen State (Default 180° for upside down stream fix)
  const [rotation, setRotation] = useState<number>(180);
  const [flipH, setFlipH] = useState<boolean>(false);
  const [flipV, setFlipV] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setFps(Math.floor(29 + Math.random() * 3));
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  // Listen for fullscreen change events (e.g. Pressing ESC key)
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const rotateVideo = () => {
    setRotation(prev => (prev + 90) % 360);
  };

  const resetOrientation = () => {
    setRotation(0);
    setFlipH(false);
    setFlipV(false);
  };

  const toggleFullscreen = () => {
    if (!viewportRef.current) return;
    if (!document.fullscreenElement) {
      viewportRef.current.requestFullscreen().catch(err => {
        console.error('Error enabling fullscreen mode:', err);
      });
    } else {
      document.exitFullscreen().catch(err => {
        console.error('Error exiting fullscreen mode:', err);
      });
    }
  };

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
      
      {/* Feed Header */}
      <div style={{ width: '100%', maxWidth: '1100px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: 'rgba(19, 21, 28, 0.88)', padding: '0.6rem 1rem', borderRadius: '8px', border: '1px solid #2d323e' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f1f5f9' }}>Live Perception ({activeCam})</span>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', background: 'rgba(255, 255, 255, 0.05)', border: '1px solid #334155', padding: '0.2rem 0.5rem', borderRadius: '4px', color: '#94a3b8', fontWeight: 600 }}>
            Transmisión Cámara Hikvision
          </span>
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{fps} FPS</span>
        </div>
      </div>

      {/* Stream Source URL Bar */}
      <div style={{ width: '100%', maxWidth: '1100px', display: 'flex', gap: '0.5rem', alignItems: 'center', backgroundColor: 'rgba(19, 21, 28, 0.88)', padding: '0.5rem 0.8rem', borderRadius: '6px', border: '1px solid #2d323e' }}>
        <span style={{ fontSize: '0.78rem', color: '#94a3b8', fontWeight: 500 }}>URL Stream Jetson:</span>
        <input 
          type="text" 
          value={streamUrl} 
          onChange={e => { setStreamUrl(e.target.value); setStreamError(false); }}
          style={{ flex: 1, background: '#090a0f', border: '1px solid #2d323e', color: '#f1f5f9', padding: '0.3rem 0.6rem', borderRadius: '4px', fontSize: '0.8rem', outline: 'none' }}
          placeholder="http://192.168.1.73:8080/mjpeg"
        />
        <div style={{ display: 'flex', gap: '0.3rem' }}>
          {['http://192.168.1.73:8080/mjpeg', 'http://192.168.1.73:8080/video_feed', 'http://192.168.55.1:8080/mjpeg'].map((preset, i) => (
            <button
              key={i}
              onClick={() => { setStreamUrl(preset); setStreamError(false); }}
              style={{
                background: streamUrl === preset ? '#0284c7' : 'rgba(255, 255, 255, 0.04)',
                border: `1px solid ${streamUrl === preset ? '#0284c7' : '#2d323e'}`,
                color: streamUrl === preset ? '#ffffff' : '#94a3b8',
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                fontSize: '0.7rem',
                cursor: 'pointer',
                fontWeight: streamUrl === preset ? 600 : 400
              }}
            >
              {preset.split('/').pop()}
            </button>
          ))}
        </div>
      </div>

      {/* Main Video Viewport (Con soporte de Pantalla Completa y Orientación Dinámica) */}
      <div 
        ref={viewportRef}
        style={{ 
          position: 'relative', 
          width: '100%', 
          maxWidth: isFullscreen ? 'none' : '1100px', 
          aspectRatio: isFullscreen ? 'auto' : '16 / 9',
          height: isFullscreen ? '100vh' : 'auto',
          maxHeight: isFullscreen ? 'none' : 'calc(100vh - 230px)',
          backgroundColor: '#000000', 
          borderRadius: isFullscreen ? '0' : '10px', 
          overflow: 'hidden', 
          border: isFullscreen ? 'none' : '1px solid #2d323e',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: isFullscreen ? 'none' : '0 8px 30px rgba(0,0,0,0.6)'
        }}
      >
        {!streamError ? (
          <img 
            src={streamUrl} 
            alt="Hikvision Live Stream" 
            onError={() => setStreamError(true)}
            style={{ 
              width: '100%', 
              height: '100%', 
              objectFit: 'contain', 
              backgroundColor: '#000000',
              transform: `rotate(${rotation}deg) scaleX(${flipH ? -1 : 1}) scaleY(${flipV ? -1 : 1})`,
              transition: 'transform 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
            }}
          />
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
            <div style={{ color: '#f1f5f9', fontWeight: 600, fontSize: '1rem', marginBottom: '0.5rem' }}>
              📡 Esperando Transmisión de Video (`{streamUrl}`)
            </div>
            <div style={{ fontSize: '0.8rem', maxWidth: '500px', margin: '0 auto', lineHeight: '1.4' }}>
              Ingresa la dirección HTTP de la cámara o ejecuta el servidor MJPEG en la Jetson para visualizar el flujo en vivo.
            </div>
          </div>
        )}

        {/* HUD Top Info Status */}
        <div style={{ position: 'absolute', top: '12px', left: '12px', display: 'flex', gap: '0.5rem', alignItems: 'center', pointerEvents: 'none', background: 'rgba(0, 0, 0, 0.65)', padding: '0.35rem 0.7rem', borderRadius: '6px', backdropFilter: 'blur(6px)', border: '1px solid rgba(255, 255, 255, 0.1)', zIndex: 10 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: !streamError ? '#10b981' : '#ff0055', boxShadow: !streamError ? '0 0 6px #10b981' : '0 0 6px #ff0055' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: !streamError ? '#10b981' : '#ff0055', letterSpacing: '1px' }}>
            {!streamError ? 'LIVE STREAMING' : 'OFFLINE'}
          </span>
          <span style={{ fontSize: '0.75rem', color: '#cbd5e1', marginLeft: '0.5rem' }}>1080p @ {fps}FPS</span>
          <span style={{ fontSize: '0.7rem', color: '#0284c7', background: 'rgba(2, 132, 199, 0.15)', padding: '0.1rem 0.4rem', borderRadius: '4px', marginLeft: '0.4rem' }}>
            {rotation}° {flipH ? '| Flip H' : ''} {flipV ? '| Flip V' : ''}
          </span>
        </div>

        {/* Dynamic Video Orientation & Fullscreen Control Toolbar (Top-Right HUD) */}
        <div style={{ position: 'absolute', top: '12px', right: '12px', display: 'flex', gap: '0.4rem', alignItems: 'center', background: 'rgba(0, 0, 0, 0.65)', padding: '0.35rem 0.5rem', borderRadius: '6px', backdropFilter: 'blur(6px)', border: '1px solid rgba(255, 255, 255, 0.1)', zIndex: 10 }}>
          <button
            onClick={rotateVideo}
            title="Rotar Video (+90°)"
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#f1f5f9',
              padding: '0.35rem',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#0284c7')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)')}
          >
            <RotateCw size={15} />
          </button>

          <button
            onClick={() => setFlipH(prev => !prev)}
            title="Invertir Horizontalmente (Flip H)"
            style={{
              background: flipH ? '#0284c7' : 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#f1f5f9',
              padding: '0.35rem',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s'
            }}
          >
            <FlipHorizontal size={15} />
          </button>

          <button
            onClick={() => setFlipV(prev => !prev)}
            title="Invertir Verticalmente (Flip V)"
            style={{
              background: flipV ? '#0284c7' : 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#f1f5f9',
              padding: '0.35rem',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s'
            }}
          >
            <FlipVertical size={15} />
          </button>

          <button
            onClick={resetOrientation}
            title="Restablecer Orientación Original (0°)"
            style={{
              background: 'rgba(255, 255, 255, 0.08)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              color: '#94a3b8',
              padding: '0.35rem',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = '#f1f5f9')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#94a3b8')}
          >
            <RefreshCcw size={14} />
          </button>

          <div style={{ width: '1px', height: '18px', backgroundColor: 'rgba(255, 255, 255, 0.2)', margin: '0 0.2rem' }} />

          <button
            onClick={toggleFullscreen}
            title={isFullscreen ? "Salir de Pantalla Completa (ESC)" : "Pantalla Completa (Fullscreen)"}
            style={{
              background: isFullscreen ? '#0284c7' : 'rgba(255, 255, 255, 0.12)',
              border: '1px solid rgba(255, 255, 255, 0.25)',
              color: '#ffffff',
              padding: '0.35rem',
              borderRadius: '4px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'all 0.2s'
            }}
          >
            {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        </div>

        {/* HUD Bottom Info */}
        <div style={{ position: 'absolute', bottom: '10px', right: '12px', fontSize: '0.7rem', color: '#cbd5e1', fontFamily: 'monospace', pointerEvents: 'none', background: 'rgba(0, 0, 0, 0.65)', padding: '0.2rem 0.5rem', borderRadius: '4px', backdropFilter: 'blur(4px)', border: '1px solid rgba(255, 255, 255, 0.1)', zIndex: 10 }}>
          STREAM: Jetson-PTZ_1 | HIKVISION REAL
        </div>
      </div>
    </div>
  );
}
