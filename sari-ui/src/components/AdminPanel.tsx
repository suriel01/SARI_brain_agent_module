import { useState, useEffect } from 'react';
import { ShieldAlert, UserPlus, Users, Trash2 } from 'lucide-react';

interface AdminPanelProps {
  token: string;
}

export default function AdminPanel({ token }: AdminPanelProps) {
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
      const res = await fetch('http://localhost:7000/api/users', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
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
      const res = await fetch('http://localhost:7000/api/users', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
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
        const data = await res.json();
        setError(data.detail || 'Error creating user');
      }
    } catch (e) {
      setError('Network error');
    }
    setLoading(false);
  };

  const handleDeleteUser = async (userId: number, username: string) => {
    if (!confirm(`Are you sure you want to delete operator "${username}"?`)) return;
    try {
      const res = await fetch(`http://localhost:7000/api/users/${userId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        fetchUsers();
      } else {
        const data = await res.json();
        alert(data.detail || 'Error deleting operator');
      }
    } catch (e) {
      alert('Network error');
    }
  };

  return (
    <div style={{ padding: '2rem', height: '100%', overflowY: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <ShieldAlert size={24} color="var(--danger)" />
        <h2 style={{ margin: 0, color: 'var(--text-main)', letterSpacing: '1px' }}>
          User Management Panel (SOC)
        </h2>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
        {/* Create User Form */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <UserPlus size={16} /> Register Operator
          </h3>
          
          <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <input 
              type="text" 
              placeholder="Username" 
              className="input-field" 
              value={newUsername} 
              onChange={e => setNewUsername(e.target.value)} 
              required
            />
            <input 
              type="password" 
              placeholder="Password" 
              className="input-field" 
              value={newPassword} 
              onChange={e => setNewPassword(e.target.value)} 
              required
            />
            <select 
              className="input-field" 
              value={newRole} 
              onChange={e => setNewRole(e.target.value)}
            >
              <option value="monitor">Monitor (Custom Permissions)</option>
              <option value="admin">Administrator (Full Control)</option>
            </select>

            {/* Permissions Matrix */}
            {newRole !== 'admin' && (
              <div style={{ background: 'rgba(255,255,255,0.03)', padding: '0.8rem', borderRadius: '6px', fontSize: '0.8rem' }}>
                <div style={{ color: '#8b949e', marginBottom: '0.5rem', fontWeight: 600 }}>Granular Permissions:</div>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={canCreateChats} onChange={e => setCanCreateChats(e.target.checked)} />
                  Create Chats
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={canDeleteChats} onChange={e => setCanDeleteChats(e.target.checked)} />
                  Delete Chats
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={canRenameChats} onChange={e => setCanRenameChats(e.target.checked)} />
                  Rename Chats
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={canControlHardware} onChange={e => setCanControlHardware(e.target.checked)} />
                  Hardware / Alarm Control
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                  <input type="checkbox" checked={canManageUsers} onChange={e => setCanManageUsers(e.target.checked)} />
                  Manage Users
                </label>
              </div>
            )}

            {error && <div style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>{error}</div>}

            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Creating...' : 'Register Operator'}
            </button>
          </form>
        </div>

        {/* User List */}
        <div className="glass-panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ fontSize: '0.8rem', color: '#8b949e', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Users size={16} /> Active Operators
          </h3>
          
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #30363d', textAlign: 'left', color: '#8b949e' }}>
                <th style={{ padding: '0.8rem' }}>ID</th>
                <th style={{ padding: '0.8rem' }}>User</th>
                <th style={{ padding: '0.8rem' }}>Role</th>
                <th style={{ padding: '0.8rem' }}>Specific Permissions</th>
                <th style={{ padding: '0.8rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(48, 54, 61, 0.5)' }}>
                  <td style={{ padding: '0.8rem', color: 'var(--text-muted)' }}>#{u.id}</td>
                  <td style={{ padding: '0.8rem', color: 'var(--text-main)', fontWeight: 600 }}>{u.username}</td>
                  <td style={{ padding: '0.8rem' }}>
                    <span style={{ 
                      padding: '0.2rem 0.5rem', 
                      borderRadius: '4px', 
                      background: u.role === 'admin' ? 'var(--danger-glow)' : 'var(--primary-glow)',
                      color: u.role === 'admin' ? 'var(--danger)' : 'var(--primary)',
                      textTransform: 'uppercase',
                      fontSize: '0.75rem',
                      letterSpacing: '1px'
                    }}>
                      {u.role}
                    </span>
                  </td>
                  <td style={{ padding: '0.8rem', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                    {u.role === 'admin' ? (
                      <span style={{ color: 'var(--primary)' }}>Full Access</span>
                    ) : (
                      <div style={{ display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
                        {u.can_create_chats && <span className="badge">Create</span>}
                        {u.can_delete_chats && <span className="badge">Delete</span>}
                        {u.can_rename_chats && <span className="badge">Rename</span>}
                        {u.can_control_hardware && <span className="badge">Hardware</span>}
                        {!u.can_create_chats && !u.can_delete_chats && !u.can_rename_chats && !u.can_control_hardware && <span>Read-Only</span>}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '0.8rem' }}>
                    {u.role !== 'admin' && (
                      <Trash2 
                        size={16} 
                        onClick={() => handleDeleteUser(u.id, u.username)}
                        style={{ cursor: 'pointer', color: 'var(--danger)' }} 
                      />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
