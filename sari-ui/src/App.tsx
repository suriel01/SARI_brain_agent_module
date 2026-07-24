import { useState, useEffect } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('sari_token'));
  const [role, setRole] = useState<string | null>(localStorage.getItem('sari_role'));

  useEffect(() => {
    if (token && role) {
      localStorage.setItem('sari_token', token);
      localStorage.setItem('sari_role', role);
    } else {
      localStorage.removeItem('sari_token');
      localStorage.removeItem('sari_role');
    }
  }, [token, role]);

  const handleLogin = (newToken: string, newRole: string) => {
    setToken(newToken);
    setRole(newRole);
  };

  const handleLogout = () => {
    setToken(null);
    setRole(null);
  };

  return (
    <div className="app-container">
      {token && role ? (
        <Dashboard token={token} role={role} onLogout={handleLogout} />
      ) : (
        <Login onLogin={handleLogin} />
      )}
    </div>
  );
}

export default App;
