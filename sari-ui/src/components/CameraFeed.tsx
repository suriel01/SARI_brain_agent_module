import { useState, useEffect } from 'react';
import { Eye, Crosshair } from 'lucide-react';

export default function CameraFeed() {
  const [fps, setFps] = useState(30);
  const [confidence, setConfidence] = useState(99.4);
  const [bboxPos, setBboxPos] = useState({ top: '35%', left: '42%' });
  const activeCam = 'Jetson-PTZ_1';

  useEffect(() => {
    const interval = setInterval(() => {
      setFps(Math.floor(28 + Math.random() * 5));
      setConfidence(parseFloat((98.5 + Math.random() * 1.4).toFixed(1)));
      const topVal = 35 + (Math.random() * 4 - 2);
      const leftVal = 42 + (Math.random() * 4 - 2);
      setBboxPos({ top: `${topVal}%`, left: `${leftVal}%` });
    }, 1200);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      
      {/* Feed Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#161b22', padding: '0.6rem 1rem', borderRadius: '8px', border: '1px solid #30363d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Eye size={16} color="#ff3366" />
          <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#e6edf3' }}>Live Perception Feed ({activeCam})</span>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', background: 'rgba(255, 51, 102, 0.15)', border: '1px solid rgba(255, 51, 102, 0.3)', padding: '0.2rem 0.5rem', borderRadius: '4px', color: '#ff3366', fontWeight: 600 }}>
            YOLOv8 Active
          </span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e' }}>{fps} FPS</span>
        </div>
      </div>

      {/* Main Video Viewport simulation */}
      <div style={{ 
        position: 'relative', 
        width: '100%', 
        height: '280px', 
        backgroundColor: '#04060a', 
        borderRadius: '10px', 
        overflow: 'hidden', 
        border: '1px solid #30363d',
        backgroundImage: 'radial-gradient(circle at 50% 50%, rgba(255, 51, 102, 0.05) 0%, transparent 80%)'
      }}>
        
        {/* Synthetic Camera View grid */}
        <div style={{
          position: 'absolute',
          inset: 0,
          backgroundImage: 'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
          backgroundSize: '20px 20px'
        }} />

        {/* HUD Crosshair Center */}
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', opacity: 0.3 }}>
          <Crosshair size={40} color="#ff3366" />
        </div>

        {/* Simulated Object Detection Bounding Box */}
        <div style={{
          position: 'absolute',
          top: bboxPos.top,
          left: bboxPos.left,
          width: '120px',
          height: '120px',
          border: '2px dashed #ff3366',
          boxShadow: '0 0 12px rgba(255, 51, 102, 0.4)',
          borderRadius: '4px',
          transition: 'all 0.8s ease',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '4px'
        }}>
          <div style={{ background: '#ff3366', color: '#000', fontSize: '0.65rem', fontWeight: 700, padding: '2px 4px', borderRadius: '2px', display: 'flex', justifyContent: 'space-between' }}>
            <span>INTRUDER</span>
            <span>{confidence}%</span>
          </div>
          <div style={{ fontSize: '0.6rem', color: '#ff3366', fontWeight: 600, background: 'rgba(0,0,0,0.7)', padding: '2px 4px', borderRadius: '2px' }}>
            OBJ_ID #804
          </div>
        </div>

        {/* HUD Top Info */}
        <div style={{ position: 'absolute', top: '10px', left: '10px', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#ff3366', animation: 'pulse 1s infinite' }} />
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#ff3366', letterSpacing: '1px' }}>REC</span>
          <span style={{ fontSize: '0.75rem', color: '#8b949e', marginLeft: '0.5rem' }}>1080p @ {fps}FPS</span>
        </div>

        {/* HUD Bottom Info */}
        <div style={{ position: 'absolute', bottom: '10px', right: '10px', fontSize: '0.7rem', color: '#8b949e', fontFamily: 'monospace' }}>
          CAM_IP: 192.168.1.104 | RTSP OK
        </div>
      </div>
    </div>
  );
}
