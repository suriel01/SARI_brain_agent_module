import { useState, useEffect } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import { permissionsFromToken, isTokenExpired } from './permissions';
import { AUTH_EXPIRED_EVENT } from './api';
import { LanguageProvider } from './i18n/LanguageContext';

function readSession(): { token: string | null; role: string | null } {
  const token = localStorage.getItem('sari_token');
  const role = localStorage.getItem('sari_role');
  if (token && role && !isTokenExpired(token)) {
    return { token, role };
  }
  if (token && isTokenExpired(token)) {
    sessionStorage.setItem('sari_session_msg', 'Sesión expirada. Vuelve a iniciar sesión.');
  }
  localStorage.removeItem('sari_token');
  localStorage.removeItem('sari_role');
  return { token: null, role: null };
}

function MainContent() {
  const initial = readSession();
  const [token, setToken] = useState<string | null>(initial.token);
  const [role, setRole] = useState<string | null>(initial.role);
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() => {
    return localStorage.getItem('sari_theme') === 'dark' || (!localStorage.getItem('sari_theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
  });

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('sari_theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('sari_theme', 'light');
    }
  }, [isDarkMode]);

  useEffect(() => {
    if (token && role) {
      localStorage.setItem('sari_token', token);
      localStorage.setItem('sari_role', role);
    } else {
      localStorage.removeItem('sari_token');
      localStorage.removeItem('sari_role');
    }
  }, [token, role]);

  useEffect(() => {
    const onExpired = () => {
      sessionStorage.setItem('sari_session_msg', 'Sesión expirada. Vuelve a iniciar sesión.');
      setToken(null);
      setRole(null);
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, []);

  const handleLogin = (newToken: string, newRole: string) => {
    sessionStorage.removeItem('sari_session_msg');
    setToken(newToken);
    setRole(newRole);
  };

  const handleLogout = () => {
    setToken(null);
    setRole(null);
  };

  const toggleTheme = () => setIsDarkMode(prev => !prev);

  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-900 dark:bg-black dark:text-zinc-100 font-sans transition-colors duration-200">
      {token && role ? (
        <Dashboard 
          token={token} 
          role={role} 
          permissions={permissionsFromToken(token, role)} 
          onLogout={handleLogout}
          isDarkMode={isDarkMode}
          toggleTheme={toggleTheme}
        />
      ) : (
        <Login onLogin={handleLogin} />
      )}
    </div>
  );
}

function App() {
  return (
    <LanguageProvider>
      <MainContent />
    </LanguageProvider>
  );
}

export default App;
