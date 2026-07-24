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
          <div style={{ background: 'var(--danger-glow)', padding: '1rem', borderRadius: '50%', marginBottom: '1rem' }}>
            <KeyRound size={28} color="var(--danger)" />
          </div>
          <h3 style={{ fontSize: '1.2rem', color: 'var(--danger)' }}>Confirmación de Seguridad</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center', marginTop: '0.5rem' }}>
            Acción crítica requerida: <br/><strong style={{color: 'var(--text-main)'}}>{actionName}</strong>
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
          <button type="submit" className="btn btn-danger" style={{ width: '100%' }}>
            Autorizar Acción
          </button>
        </form>
      </div>
    </div>
  );
}
