import { useEffect, useState } from 'react';

export default function Telemetry() {
  const [cpuLoad, setCpuLoad] = useState<number[]>(Array(10).fill(20));
  const [netLoad, setNetLoad] = useState<number[]>(Array(10).fill(10));

  useEffect(() => {
    const interval = setInterval(() => {
      setCpuLoad(prev => {
        const next = [...prev.slice(1), Math.random() * 40 + 30]; // 30-70%
        return next;
      });
      setNetLoad(prev => {
        const next = [...prev.slice(1), Math.random() * 80 + 10]; // 10-90%
        return next;
      });
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', width: '100%' }}>
      {/* CPU Telemetry */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#8b949e', textTransform: 'uppercase' }}>CPU Load</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>{Math.round(cpuLoad[cpuLoad.length - 1])}%</span>
        </div>
        <div style={{ display: 'flex', gap: '4px', height: '40px', alignItems: 'flex-end' }}>
          {cpuLoad.map((val, idx) => (
            <div key={idx} style={{
              flex: 1,
              backgroundColor: val > 60 ? 'var(--warning)' : 'var(--primary)',
              height: `${val}%`,
              transition: 'height 0.3s ease',
              borderRadius: '2px'
            }} />
          ))}
        </div>
      </div>

      {/* Network Telemetry */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
          <span style={{ fontSize: '0.75rem', color: '#8b949e', textTransform: 'uppercase' }}>Network TX/RX</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--primary)' }}>{Math.round(netLoad[netLoad.length - 1])} MB/s</span>
        </div>
        <div style={{ display: 'flex', gap: '4px', height: '40px', alignItems: 'flex-end' }}>
          {netLoad.map((val, idx) => (
            <div key={idx} style={{
              flex: 1,
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              borderTop: `2px solid ${val > 70 ? 'var(--danger)' : 'var(--primary)'}`,
              height: `${val}%`,
              transition: 'height 0.3s ease'
            }} />
          ))}
        </div>
      </div>
    </div>
  );
}
