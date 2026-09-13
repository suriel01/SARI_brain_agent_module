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
    <div className="flex min-h-screen w-full bg-white text-zinc-900 font-sans selection:bg-zinc-900 selection:text-white">
      
      {/* Left Side: SARI Logo occupies the background, unobstructed */}
      <div 
        className="hidden lg:flex w-1/2 relative flex-col justify-end p-12 overflow-hidden bg-black bg-no-repeat border-r border-zinc-200 shadow-2xl"
        style={{
          backgroundImage: "url('/sari_logo.jpeg')",
          backgroundSize: "cover",
          backgroundPosition: "center 12%"
        }}
      >
        {/* Subtle vignette at the bottom to ensure text readability without any boxed container */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/30 to-transparent pointer-events-none" />

        {/* Bottom Text Content (No box/cuadro, positioned cleanly at the bottom below the logo) */}
        <div className="relative z-10 max-w-lg mb-2 text-left">
          <h1 className="text-2xl sm:text-3xl font-light mb-2.5 tracking-wide leading-tight text-zinc-200">
            {language === 'en' ? (
              <>Autonomous <span className="font-bold text-white">Intrusion Response System</span></>
            ) : (
              <>Sistema Autónomo de <span className="font-bold text-white">Respuesta a Intrusiones</span></>
            )}
          </h1>
          <p className="text-zinc-400 text-xs sm:text-sm leading-relaxed font-medium max-w-md">
            {language === 'en'
              ? 'Restricted access. Authorization required for tactical controls, perimeter telemetry, and Security Operations Center oversight.'
              : 'Acceso restringido. Autorización requerida para la manipulación de controles tácticos, telemetría perimetral y supervisión del Security Operations Center.'}
          </p>
        </div>
      </div>

      {/* Right Side: Login Form (Always in Light Mode) */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 sm:p-12 relative bg-white">
        
        {/* Mobile Header */}
        <div className="lg:hidden absolute top-8 left-8 flex items-center gap-2">
          <span className="text-xl font-black tracking-[0.2em] text-zinc-900">SARI</span>
          <span className="text-[9px] text-zinc-500 font-mono tracking-widest bg-zinc-100 px-2 py-0.5 rounded-full border border-zinc-200">
            SOC
          </span>
        </div>

        <div className="w-full max-w-[400px] animate-[fadeIn_0.4s_ease-out]">
          
          {/* Header Title (No small logo) */}
          <div className="mb-8">
            <h2 className="text-3xl font-bold tracking-tight text-zinc-900 mb-2">SOC Terminal</h2>
            <p className="text-sm text-zinc-500 font-medium">
              {language === 'en'
                ? 'Enter your operator credentials to access the console.'
                : 'Ingrese sus credenciales de operador para iniciar sesión.'}
            </p>
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 p-4 rounded-2xl mb-6 text-sm flex items-start gap-3 border border-red-200 shadow-sm">
              <ShieldAlert size={18} className="shrink-0 mt-0.5" />
              <span className="font-semibold">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-600 ml-2">
                {language === 'en' ? 'Identifier' : 'Identificador'}
              </label>
              <input 
                type="text" 
                className="w-full bg-zinc-50 border border-zinc-200 rounded-full px-5 py-3.5 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all shadow-sm placeholder:text-zinc-400 font-medium" 
                value={username} 
                onChange={e => setUsername(e.target.value)}
                placeholder={language === 'en' ? 'Username' : 'Nombre de usuario'}
                required
                autoFocus
              />
            </div>
            
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-600 ml-2">
                {language === 'en' ? 'Password' : 'Contraseña'}
              </label>
              <input 
                type="password" 
                className="w-full bg-zinc-50 border border-zinc-200 rounded-full px-5 py-3.5 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:ring-zinc-900 focus:bg-white transition-all shadow-sm placeholder:text-zinc-400 font-medium" 
                value={password} 
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            
            <div className="pt-3">
              <button 
                type="submit" 
                className="w-full flex justify-center items-center rounded-full bg-zinc-900 px-6 py-3.5 text-sm font-semibold text-white transition-all hover:bg-zinc-800 active:scale-95 shadow-md shadow-zinc-900/10 hover:shadow-lg disabled:opacity-50 cursor-pointer" 
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center gap-3">
                    <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                    {language === 'en' ? 'Authenticating...' : 'Autenticando...'}
                  </span>
                ) : (
                  language === 'en' ? 'Enter System' : 'Ingresar al Sistema'
                )}
              </button>
            </div>
          </form>

          {/* Footer: SARI OS V0.5 and Secure Terminal */}
          <div className="mt-12 pt-6 border-t border-zinc-200 flex items-center justify-between text-[11px] uppercase tracking-widest text-zinc-400 font-mono font-semibold">
            <span>SARI OS V0.5</span>
            <span className="flex items-center gap-2 text-zinc-500">
              <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              {language === 'en' ? 'Secure Terminal' : 'Terminal Segura'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
