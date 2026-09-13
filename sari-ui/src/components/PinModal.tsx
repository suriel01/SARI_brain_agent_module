import { useState } from 'react';
import { KeyRound, X } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';

interface PinModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (pin: string) => void;
  actionName: string;
}

export default function PinModal({ isOpen, onClose, onSubmit, actionName }: PinModalProps) {
  const { language, t } = useLanguage();
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
    <div className="fixed inset-0 bg-black/70 backdrop-blur-md flex items-center justify-center z-[100] p-4">
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 p-8 w-full max-w-[360px] rounded-3xl relative shadow-2xl transition-all">
        <button 
          onClick={onClose} 
          className="absolute top-4 right-4 w-8 h-8 rounded-full flex items-center justify-center text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
          title={language === 'en' ? 'Close' : 'Cerrar'}
        >
          <X size={16} />
        </button>
        
        <div className="flex flex-col items-center mb-6 text-center">
          <div className="w-12 h-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mb-4 border border-zinc-200 dark:border-zinc-700 shadow-sm text-zinc-900 dark:text-zinc-100">
            <KeyRound size={22} />
          </div>
          <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100 tracking-tight">
            {t('securityPinTitle')}
          </h3>
          <p className="text-zinc-500 dark:text-zinc-400 text-xs mt-1.5 leading-relaxed">
            {t('enterPinMessage')} <br/>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100 mt-1 inline-block bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-full text-xs border border-zinc-200/60 dark:border-zinc-700/60 shadow-sm">
              {actionName}
            </span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input 
            type="password" 
            className="w-full bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-full px-5 py-3 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-900 dark:focus:ring-white transition-all text-center text-xl tracking-[0.5rem] font-mono shadow-sm" 
            value={pin} 
            onChange={e => setPin(e.target.value)}
            placeholder="••••"
            maxLength={6}
            autoFocus
            required
          />
          <button 
            type="submit" 
            className="w-full bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 font-semibold py-3 px-6 rounded-full shadow-sm hover:bg-zinc-800 dark:hover:bg-zinc-200 active:scale-95 transition-all text-sm"
          >
            {language === 'en' ? 'Authorize Action' : 'Autorizar Acción'}
          </button>
        </form>
      </div>
    </div>
  );
}
