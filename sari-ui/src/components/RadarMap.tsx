import { useEffect, useState } from 'react';

export default function RadarMap() {
  const [dots, setDots] = useState<{x: number, y: number, alpha: number}[]>([]);

  useEffect(() => {
    // Generate random stationary dots simulating cameras/sensors
    const generatedDots = Array.from({ length: 5 }).map(() => ({
      x: Math.random() * 80 + 10, // 10% to 90%
      y: Math.random() * 80 + 10,
      alpha: Math.random() * 0.5 + 0.5
    }));
    setDots(generatedDots);
  }, []);

  return (
    <div style={{
      width: '100%',
      aspectRatio: '1/1',
      maxWidth: '300px',
      margin: '0 auto',
      backgroundColor: 'rgba(0, 0, 0, 0.4)',
      border: '1px solid #30363d',
      borderRadius: '50%',
      position: 'relative',
      overflow: 'hidden',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 0 30px var(--primary-glow) inset'
    }}>
      {/* Grid lines */}
      <div style={{ position: 'absolute', width: '100%', height: '1px', backgroundColor: 'var(--primary-glow)' }} />
      <div style={{ position: 'absolute', width: '1px', height: '100%', backgroundColor: 'var(--primary-glow)' }} />
      
      {/* Concentric circles */}
      <div style={{ position: 'absolute', width: '70%', height: '70%', border: '1px solid var(--primary-glow)', borderRadius: '50%' }} />
      <div style={{ position: 'absolute', width: '40%', height: '40%', border: '1px solid var(--primary-glow)', borderRadius: '50%' }} />

      {/* Sweeping Radar beam (animated in index.css) */}
      <div className="radar-sweep" style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        width: '50%',
        height: '50%',
        background: 'conic-gradient(from 0deg, transparent 0deg, var(--primary-glow) 90deg, transparent 90deg)',
        transformOrigin: '0 0',
      }} />

      {/* Sensor Dots */}
      {dots.map((dot, i) => (
        <div key={i} className="radar-dot" style={{
          position: 'absolute',
          left: `${dot.x}%`,
          top: `${dot.y}%`,
          width: '6px',
          height: '6px',
          backgroundColor: 'var(--primary)',
          borderRadius: '50%',
          boxShadow: '0 0 10px var(--primary)',
          animationDelay: `${Math.random() * 2}s`
        }} />
      ))}
    </div>
  );
}
