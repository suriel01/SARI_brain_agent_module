import { useState, useEffect } from 'react';
import { ShieldAlert } from 'lucide-react';
import { API_BASE } from '../config';
import { useLanguage } from '../i18n/LanguageContext';

interface LoginProps {
  onLogin: (token: string, role: string) => void;
}

export default function Login({ onLogin }: LoginProps) {
  const { language } = useLanguage();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(() => sessionStorage.getItem('sari_session_msg') || '');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    sessionStorage.removeItem('sari_session_msg');
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!res.ok) {
        throw new Error(language === 'en' ? 'Invalid credentials' : 'Credenciales incorrectas');
      }

      const data = await res.json();
      onLogin(data.access_token, data.role);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full bg-black text-white font-sans selection:bg-white selection:text-black">
      
      {/* Left Side: SARI Logo occupies the background cleanly without vignette or text */}
      <div 
        className="hidden lg:flex w-1/2 relative overflow-hidden bg-black bg-no-repeat border-r border-zinc-900 shadow-2xl"
        style={{
          backgroundImage: "url('/sari_logo.jpeg')",
          backgroundSize: "cover",
          backgroundPosition: "center center"
        }}
      />

      {/* Right Side: Login Form with Black Background & Tactical Dark Theme */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 sm:p-12 relative bg-black">
        
        {/* Mobile Header */}
        <div className="lg:hidden absolute top-8 left-8 flex items-center gap-2">
          <span className="text-xl font-black tracking-[0.2em] text-white">SARI</span>
          <span className="text-[9px] text-zinc-400 font-mono tracking-widest bg-zinc-900 px-2 py-0.5 rounded-full border border-zinc-800">
            SOC
          </span>
        </div>

        <div className="w-full max-w-[420px] animate-[fadeIn_0.4s_ease-out]">
          
          {/* Header Title: Autonomous Intrusion Response System text replacing SOC Terminal */}
          <div className="mb-8">
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white mb-3 leading-snug">
              {language === 'en' ? (
                <>Autonomous <span className="text-zinc-400 font-normal">Intrusion Response System</span></>
              ) : (
                <>Sistema Autónomo de <span className="text-zinc-400 font-normal">Respuesta a Intrusiones</span></>
              )}
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400 font-medium leading-relaxed">
              {language === 'en'
                ? 'Restricted access. Authorization required for tactical controls, perimeter telemetry, and Security Operations Center oversight.'
                : 'Acceso restringido. Autorización requerida para la manipulación de controles tácticos, telemetría perimetral y supervisión del Security Operations Center.'}
            </p>
          </div>

          {error && (
            <div className="bg-red-950/40 text-red-400 p-4 rounded-2xl mb-6 text-sm flex items-start gap-3 border border-red-900/60 shadow-sm">
              <ShieldAlert size={18} className="shrink-0 mt-0.5" />
              <span className="font-semibold">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-300 ml-2">
                {language === 'en' ? 'Identifier' : 'Identificador'}
              </label>
              <input 
                type="text" 
                className="w-full bg-zinc-900/90 border border-zinc-800 rounded-full px-5 py-3.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-white focus:border-transparent transition-all shadow-inner placeholder:text-zinc-500 font-medium" 
                value={username} 
                onChange={e => setUsername(e.target.value)}
                placeholder={language === 'en' ? 'Username' : 'Nombre de usuario'}
                required
                autoFocus
              />
            </div>
            
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-300 ml-2">
                {language === 'en' ? 'Password' : 'Contraseña'}
              </label>
              <input 
                type="password" 
                className="w-full bg-zinc-900/90 border border-zinc-800 rounded-full px-5 py-3.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-white focus:border-transparent transition-all shadow-inner placeholder:text-zinc-500 font-medium" 
                value={password} 
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            
            <div className="pt-3">
              <button 
                type="submit" 
                className="w-full flex justify-center items-center rounded-full bg-white px-6 py-3.5 text-sm font-bold text-black transition-all hover:bg-zinc-200 active:scale-95 shadow-lg shadow-white/10 hover:shadow-white/20 disabled:opacity-50 cursor-pointer" 
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center gap-3">
                    <div className="h-4 w-4 rounded-full border-2 border-zinc-400 border-t-black animate-spin" />
                    {language === 'en' ? 'Authenticating...' : 'Autenticando...'}
                  </span>
                ) : (
                  language === 'en' ? 'Enter System' : 'Ingresar al Sistema'
                )}
              </button>
            </div>
          </form>

          {/* Footer: SARI OS V0.5 and Secure Terminal */}
          <div className="mt-12 pt-6 border-t border-zinc-800 flex items-center justify-between text-[11px] uppercase tracking-widest text-zinc-500 font-mono font-semibold">
            <span>SARI OS V0.5</span>
            <span className="flex items-center gap-2 text-zinc-400">
              <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              {language === 'en' ? 'Secure Terminal' : 'Terminal Segura'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
