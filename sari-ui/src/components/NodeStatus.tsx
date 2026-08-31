import { Server, Activity, Thermometer, Wifi } from 'lucide-react';

export default function NodeStatus() {
  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px', border: '1px solid #30363d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Server size={16} color="#10b981" />
          <span style={{ fontSize: '0.8rem', color: '#c9d1d9' }}>Jetson RAM</span>
        </div>
        <span style={{ fontSize: '0.85rem', color: '#10b981', fontWeight: 600 }}>4.2 / 8 GB</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px', border: '1px solid #30363d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Activity size={16} color="#eab308" />
          <span style={{ fontSize: '0.8rem', color: '#c9d1d9' }}>NPU Load</span>
        </div>
        <span style={{ fontSize: '0.85rem', color: '#eab308', fontWeight: 600 }}>68%</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px', border: '1px solid #30363d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Thermometer size={16} color="#ef4444" />
          <span style={{ fontSize: '0.8rem', color: '#c9d1d9' }}>Core Temp</span>
        </div>
        <span style={{ fontSize: '0.85rem', color: '#ef4444', fontWeight: 600 }}>72°C</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '6px', border: '1px solid #30363d' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Wifi size={16} color="#3b82f6" />
          <span style={{ fontSize: '0.8rem', color: '#c9d1d9' }}>Network Link</span>
        </div>
        <span style={{ fontSize: '0.85rem', color: '#3b82f6', fontWeight: 600 }}>Stable (1Gbps)</span>
      </div>
    </div>
  );
}
