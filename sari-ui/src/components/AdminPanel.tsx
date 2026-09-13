import { useState, useEffect } from 'react';
import { UserPlus, Users, Trash2 } from 'lucide-react';
import { apiFetch, readErrorDetail } from '../api';
import { useLanguage } from '../i18n/LanguageContext';

interface AdminPanelProps {
  token: string;
}

export default function AdminPanel({ token }: AdminPanelProps) {
  const { language } = useLanguage();
  const [users, setUsers] = useState<any[]>([]);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('monitor');
  
  // Granular permissions
  const [canCreateChats, setCanCreateChats] = useState(false);
  const [canDeleteChats, setCanDeleteChats] = useState(false);
  const [canRenameChats, setCanRenameChats] = useState(false);
  const [canControlHardware, setCanControlHardware] = useState(false);
  const [canManageUsers, setCanManageUsers] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const fetchUsers = async () => {
    try {
      const res = await apiFetch('/users', token);
      if (res.ok) {
        setUsers(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [token]);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await apiFetch('/users', token, {
        method: 'POST',
        body: JSON.stringify({
          username: newUsername,
          password: newPassword,
          role: newRole,
          clearance_level: newRole === 'admin' ? 5 : 1,
          can_create_chats: newRole === 'admin' || canCreateChats,
          can_delete_chats: newRole === 'admin' || canDeleteChats,
          can_rename_chats: newRole === 'admin' || canRenameChats,
          can_control_hardware: newRole === 'admin' || canControlHardware,
          can_manage_users: newRole === 'admin' || canManageUsers
        })
      });

      if (res.ok) {
        setNewUsername('');
        setNewPassword('');
        setCanCreateChats(false);
        setCanDeleteChats(false);
        setCanRenameChats(false);
        setCanControlHardware(false);
        setCanManageUsers(false);
        fetchUsers();
      } else {
        setError(await readErrorDetail(res, language === 'en' ? 'Error creating user' : 'Error al crear operador'));
      }
    } catch (e) {
      setError(language === 'en' ? 'Network error' : 'Error de red');
    }
    setLoading(false);
  };

  const handleDeleteUser = async (userId: number, username: string) => {
    const confirmMsg = language === 'en' 
      ? `Are you sure you want to delete operator "${username}"?` 
      : `¿Estás seguro de que deseas eliminar al operador "${username}"?`;
    if (!confirm(confirmMsg)) return;
    try {
      const res = await apiFetch(`/users/${userId}`, token, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchUsers();
      } else {
        alert(await readErrorDetail(res, language === 'en' ? 'Error deleting operator' : 'Error al eliminar operador'));
      }
    } catch (e) {
      alert(language === 'en' ? 'Network error' : 'Error de red');
    }
  };

  return (
    <div className="p-6 h-full overflow-y-auto text-zinc-900 dark:text-zinc-100 transition-colors">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Create User Form */}
        <div className="lg:col-span-1 bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 shadow-sm transition-all">
          <h3 className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest mb-5 flex items-center gap-2">
            <UserPlus size={14} /> {language === 'en' ? 'Register New Operator' : 'Registrar Nuevo Operador'}
          </h3>
          
          <form onSubmit={handleCreateUser} className="flex flex-col gap-3.5">
            <input 
              type="text" 
              placeholder={language === 'en' ? 'Username' : 'Nombre de usuario'} 
              className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-full px-4 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 shadow-sm" 
              value={newUsername} 
              onChange={e => setNewUsername(e.target.value)} 
              required
            />
            <input 
              type="password" 
              placeholder={language === 'en' ? 'Password' : 'Contraseña'} 
              className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-full px-4 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all text-zinc-900 dark:text-zinc-100 placeholder-zinc-400 dark:placeholder-zinc-500 shadow-sm" 
              value={newPassword} 
              onChange={e => setNewPassword(e.target.value)} 
              required
            />
            <select 
              className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-full px-4 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all cursor-pointer text-zinc-900 dark:text-zinc-100 shadow-sm" 
              value={newRole} 
              onChange={e => setNewRole(e.target.value)}
            >
              <option value="monitor">{language === 'en' ? 'Monitor (Custom Permissions)' : 'Monitor (Permisos Personalizados)'}</option>
              <option value="admin">{language === 'en' ? 'Administrator (Full Access)' : 'Administrador (Control Total)'}</option>
            </select>

            {/* Permissions Matrix */}
            {newRole !== 'admin' && (
              <div className="bg-zinc-50 dark:bg-zinc-800/50 p-4 rounded-2xl text-xs border border-zinc-200/80 dark:border-zinc-700/60 mt-1 shadow-inner">
                <div className="text-zinc-500 dark:text-zinc-400 mb-3 font-semibold text-[11px] uppercase tracking-wide">
                  {language === 'en' ? 'Granular Permissions:' : 'Permisos Granulares:'}
                </div>
                <label className="flex items-center gap-2 mb-2 cursor-pointer text-zinc-700 dark:text-zinc-300 font-medium hover:text-zinc-950 dark:hover:text-white transition-colors">
                  <input type="checkbox" className="accent-zinc-900 dark:accent-white w-3.5 h-3.5" checked={canCreateChats} onChange={e => setCanCreateChats(e.target.checked)} />
                  {language === 'en' ? 'Create chat threads' : 'Crear conversaciones'}
                </label>
                <label className="flex items-center gap-2 mb-2 cursor-pointer text-zinc-700 dark:text-zinc-300 font-medium hover:text-zinc-950 dark:hover:text-white transition-colors">
                  <input type="checkbox" className="accent-zinc-900 dark:accent-white w-3.5 h-3.5" checked={canDeleteChats} onChange={e => setCanDeleteChats(e.target.checked)} />
                  {language === 'en' ? 'Delete chat threads' : 'Eliminar conversaciones'}
                </label>
                <label className="flex items-center gap-2 mb-2 cursor-pointer text-zinc-700 dark:text-zinc-300 font-medium hover:text-zinc-950 dark:hover:text-white transition-colors">
                  <input type="checkbox" className="accent-zinc-900 dark:accent-white w-3.5 h-3.5" checked={canRenameChats} onChange={e => setCanRenameChats(e.target.checked)} />
                  {language === 'en' ? 'Rename chat threads' : 'Renombrar conversaciones'}
                </label>
                <label className="flex items-center gap-2 mb-2 cursor-pointer text-zinc-700 dark:text-zinc-300 font-medium hover:text-zinc-950 dark:hover:text-white transition-colors">
                  <input type="checkbox" className="accent-zinc-900 dark:accent-white w-3.5 h-3.5" checked={canControlHardware} onChange={e => setCanControlHardware(e.target.checked)} />
                  {language === 'en' ? 'Tactical hardware control (Siren / Gates)' : 'Control de hardware táctico (Sirena / Accesos)'}
                </label>
                <label className="flex items-center gap-2 cursor-pointer text-zinc-700 dark:text-zinc-300 font-medium hover:text-zinc-950 dark:hover:text-white transition-colors">
                  <input type="checkbox" className="accent-zinc-900 dark:accent-white w-3.5 h-3.5" checked={canManageUsers} onChange={e => setCanManageUsers(e.target.checked)} />
                  {language === 'en' ? 'Manage operators' : 'Gestionar operadores'}
                </label>
              </div>
            )}

            {error && <div className="text-red-600 dark:text-red-400 text-xs font-semibold px-2">{error}</div>}

            <button 
              type="submit" 
              className="w-full bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 font-semibold py-2.5 px-5 rounded-full mt-2 shadow-sm hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all text-xs active:scale-95 disabled:opacity-50" 
              disabled={loading}
            >
              {loading ? (language === 'en' ? 'Registering...' : 'Registrando...') : (language === 'en' ? 'Register Operator' : 'Registrar Operador')}
            </button>
          </form>
        </div>

        {/* User List */}
        <div className="lg:col-span-2 bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 shadow-sm transition-all flex flex-col">
          <h3 className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest mb-5 flex items-center gap-2">
            <Users size={14} /> {language === 'en' ? 'Active Operators in the System' : 'Operadores Activos en el Sistema'}
          </h3>
          
          <div className="overflow-x-auto border border-zinc-200 dark:border-zinc-800 rounded-2xl">
            <table className="w-full border-collapse text-xs text-left">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/50">
                  <th className="p-3 font-semibold">ID</th>
                  <th className="p-3 font-semibold">{language === 'en' ? 'User' : 'Usuario'}</th>
                  <th className="p-3 font-semibold">{language === 'en' ? 'Role' : 'Rol'}</th>
                  <th className="p-3 font-semibold">{language === 'en' ? 'Assigned Permissions' : 'Permisos Asignados'}</th>
                  <th className="p-3 font-semibold text-right">{language === 'en' ? 'Action' : 'Acción'}</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="border-b border-zinc-100 dark:border-zinc-800/50 hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                    <td className="p-3 text-zinc-400 font-mono">#{u.id}</td>
                    <td className="p-3 text-zinc-900 dark:text-zinc-100 font-semibold">{u.username}</td>
                    <td className="p-3">
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                        u.role === 'admin' 
                          ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950' 
                          : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700'
                      }`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="p-3 text-zinc-500 dark:text-zinc-400 text-xs">
                      {u.role === 'admin' ? (
                        <span className="text-zinc-900 dark:text-zinc-100 font-semibold text-[11px]">
                          {language === 'en' ? 'Full Access (Superuser)' : 'Acceso Total (Superusuario)'}
                        </span>
                      ) : (
                        <div className="flex gap-1 flex-wrap">
                          {u.can_create_chats && <span className="bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-200 dark:border-zinc-700">Chats</span>}
                          {u.can_delete_chats && <span className="bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-200 dark:border-zinc-700">{language === 'en' ? 'Delete' : 'Borrar'}</span>}
                          {u.can_rename_chats && <span className="bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-200 dark:border-zinc-700">{language === 'en' ? 'Rename' : 'Renombrar'}</span>}
                          {u.can_control_hardware && <span className="bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-200 dark:border-zinc-700">Hardware</span>}
                          {u.can_manage_users && <span className="bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 px-2 py-0.5 rounded-full text-[10px] font-medium border border-zinc-200 dark:border-zinc-700">{language === 'en' ? 'Users' : 'Usuarios'}</span>}
                          {!u.can_create_chats && !u.can_delete_chats && !u.can_rename_chats && !u.can_control_hardware && !u.can_manage_users && <span className="italic text-[11px]">{language === 'en' ? 'Read-only' : 'Solo Lectura'}</span>}
                        </div>
                      )}
                    </td>
                    <td className="p-3 text-right">
                      {u.role !== 'admin' && (
                        <button 
                          onClick={() => handleDeleteUser(u.id, u.username)}
                          className="w-7 h-7 rounded-full flex items-center justify-center text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/30 transition-all ml-auto"
                          title={language === 'en' ? 'Delete Operator' : 'Eliminar Operador'}
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-zinc-400 dark:text-zinc-500 italic">
                      {language === 'en' ? 'No operators registered in database.' : 'No hay operadores registrados en la base de datos.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
