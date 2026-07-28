import { useState } from 'react';
import { KeyRound, X } from 'lucide-react';

interface PinModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (pin: string) => void;
  actionName: string;
}

export default function PinModal({ isOpen, onClose, onSubmit, actionName }: PinModalProps) {
  const [pin, setPin] = useState('');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (pin.length >= 4) {
      onSubmit(pin);
      setPin('');
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div className="glass-panel" style={{ padding: '2rem', width: '100%', maxWidth: '350px', animation: 'fadeIn 0.2s ease', position: 'relative' }}>
        <button onClick={onClose} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
          <X size={20} />
        </button>
        
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '1.5rem' }}>
          <div style={{ background: 'rgba(255, 255, 255, 0.08)', padding: '1rem', borderRadius: '50%', marginBottom: '1rem', border: '1px solid #334155' }}>
            <KeyRound size={28} color="#f1f5f9" />
          </div>
          <h3 style={{ fontSize: '1.1rem', color: '#f1f5f9' }}>Confirmación de Seguridad</h3>
          <p style={{ color: '#94a3b8', fontSize: '0.85rem', textAlign: 'center', marginTop: '0.5rem' }}>
            Acción autorizada requerida: <br/><strong style={{color: '#f1f5f9'}}>{actionName}</strong>
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <input 
            type="password" 
            className="input" 
            value={pin} 
            onChange={e => setPin(e.target.value)}
            placeholder="Ingrese su PIN (Ej. 1234)"
            maxLength={6}
            style={{ textAlign: 'center', fontSize: '1.2rem', letterSpacing: '0.5rem' }}
            autoFocus
            required
          />
          <button type="submit" style={{ width: '100%', background: '#0284c7', color: '#ffffff', border: '1px solid #0284c7', padding: '0.65rem', borderRadius: '8px', fontWeight: 600, cursor: 'pointer' }}>
            Autorizar Acción
          </button>
        </form>
      </div>
    </div>
  );
}
