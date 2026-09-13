import { useState, useEffect } from 'react';
import { ShieldAlert, Terminal, Lock } from 'lucide-react';
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
    <div className="flex min-h-screen w-full bg-zinc-100 dark:bg-black font-sans transition-colors duration-300 selection:bg-black selection:text-white dark:selection:bg-white dark:selection:text-black">
      
      {/* Left Side: Branding / Visuals (Hidden on mobile) */}
      <div className="hidden lg:flex w-1/2 relative bg-black flex-col justify-between p-12 overflow-hidden border-r border-zinc-200 dark:border-zinc-800 shadow-[4px_0_24px_rgba(0,0,0,0.02)] dark:shadow-none">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(255,255,255,0.08),_transparent_40%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,_rgba(255,255,255,0.05),_transparent_50%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.03)_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_60%_at_50%_50%,#000_70%,transparent_100%)]" />

        {/* Top Logo */}
        <div className="relative z-10 flex items-center gap-3.5">
          <div className="bg-white p-1.5 rounded-2xl shadow-xl border border-white/20">
            <img 
              src="/sari_logo.jpeg" 
              alt="SARI Logo" 
              className="w-9 h-9 object-contain rounded-lg" 
            />
          </div>
          <div>
            <span className="text-2xl font-black tracking-[0.2em] text-white">SARI</span>
            <div className="text-[10px] text-zinc-400 font-mono tracking-widest leading-none mt-0.5">AUTONOMOUS AGENT</div>
          </div>
        </div>

        {/* Center/Bottom Content */}
        <div className="relative z-10 max-w-lg mb-8">
          <h1 className="text-[2.75rem] font-light mb-6 tracking-wide leading-[1.1] text-zinc-400">
            {language === 'en' ? (
              <>Autonomous <br/><span className="font-bold text-white">Intrusion Response System</span></>
            ) : (
              <>Sistema Autónomo de <br/><span className="font-bold text-white">Respuesta a Intrusiones</span></>
            )}
          </h1>
          <p className="text-zinc-400 text-sm leading-relaxed mb-10 max-w-md font-medium">
            {language === 'en'
              ? 'Restricted access. Authorization required for tactical controls, perimeter telemetry, and Security Operations Center oversight.'
              : 'Acceso restringido. Autorización requerida para la manipulación de controles tácticos, telemetría perimetral y supervisión del Security Operations Center.'}
          </p>
          
          <div className="flex items-center gap-4 text-xs font-mono text-zinc-500 uppercase tracking-widest">
            <div className="flex items-center gap-2"><Terminal size={14} /> SYS_CORE_ONLINE</div>
            <div className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
            <div className="flex items-center gap-2 text-white"><Lock size={14} /> ENCRYPTED_CHANNEL</div>
          </div>
        </div>
      </div>

      {/* Right Side: Login Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 relative">
        <div className="lg:hidden absolute top-8 left-8 flex items-center gap-3">
          <div className="bg-white p-1 rounded-xl shadow-md border border-zinc-200">
            <img 
              src="/sari_logo.jpeg" 
              alt="SARI Logo" 
              className="w-7 h-7 object-contain rounded-md" 
            />
          </div>
          <span className="text-xl font-black tracking-[0.2em] text-zinc-900 dark:text-white">SARI</span>
        </div>

        <div className="w-full max-w-[400px] animate-[fadeIn_0.5s_ease-out]">
          <div className="mb-8">
            <div className="w-12 h-12 bg-white p-1 rounded-2xl shadow-md border border-zinc-200 dark:border-zinc-800 mb-4 flex items-center justify-center">
              <img 
                src="/sari_logo.jpeg" 
                alt="SARI Logo" 
                className="w-10 h-10 object-contain rounded-xl" 
              />
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-white mb-2">SOC Terminal</h2>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 font-medium">
              {language === 'en'
                ? 'Enter your operator credentials to access the console.'
                : 'Ingrese sus credenciales de operador para iniciar sesión.'}
            </p>
          </div>

          {error && (
            <div className="bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 p-4 rounded-xl mb-8 text-sm flex items-start gap-3 border border-red-200 dark:border-red-900/50 shadow-sm">
              <ShieldAlert size={18} className="shrink-0 mt-0.5" />
              <span className="font-semibold">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 ml-2">
                {language === 'en' ? 'Identifier' : 'Identificador'}
              </label>
              <input 
                type="text" 
                className="w-full bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-full px-5 py-3 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-900 dark:focus:ring-white focus:bg-white dark:focus:bg-zinc-900 transition-all shadow-sm placeholder:text-zinc-400 dark:placeholder:text-zinc-600" 
                value={username} 
                onChange={e => setUsername(e.target.value)}
                placeholder={language === 'en' ? 'Username' : 'Nombre de usuario'}
                required
              />
            </div>
            
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 ml-2">
                {language === 'en' ? 'Password' : 'Contraseña'}
              </label>
              <input 
                type="password" 
                className="w-full bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-full px-5 py-3 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-900 dark:focus:ring-white focus:bg-white dark:focus:bg-zinc-900 transition-all shadow-sm placeholder:text-zinc-400 dark:placeholder:text-zinc-600" 
                value={password} 
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>
            
            <div className="pt-4">
              <button 
                type="submit" 
                className="w-full flex justify-center items-center rounded-full bg-zinc-900 dark:bg-white px-6 py-3.5 text-sm font-semibold text-white dark:text-zinc-950 transition-all hover:bg-zinc-800 dark:hover:bg-zinc-200 active:scale-95 shadow-sm hover:shadow disabled:opacity-50" 
                disabled={loading}
              >
                {loading ? (
                  <span className="flex items-center gap-3">
                    <div className="h-4 w-4 rounded-full border-2 border-white/30 dark:border-zinc-950/30 border-t-white dark:border-t-zinc-950 animate-spin" />
                    {language === 'en' ? 'Authenticating...' : 'Autenticando...'}
                  </span>
                ) : (
                  language === 'en' ? 'Enter System' : 'Ingresar al Sistema'
                )}
              </button>
            </div>
          </form>

          <div className="mt-14 pt-8 border-t border-zinc-200 dark:border-zinc-800 flex items-center justify-between text-[11px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 font-mono font-semibold">
            <span>SARI OS v2.0.4</span>
            <span className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
              {language === 'en' ? 'Secure Terminal' : 'Terminal Segura'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
