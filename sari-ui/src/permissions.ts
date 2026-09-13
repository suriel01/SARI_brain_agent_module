export interface Permissions {
  canCreateChats: boolean;
  canDeleteChats: boolean;
  canRenameChats: boolean;
  canControlHardware: boolean;
  canManageUsers: boolean;
}

export function permissionsFromToken(token: string, role: string): Permissions {
  const isAdmin = role === 'admin';
  const defaults: Permissions = {
    canCreateChats: isAdmin,
    canDeleteChats: isAdmin,
    canRenameChats: isAdmin,
    canControlHardware: isAdmin,
    canManageUsers: isAdmin,
  };

  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return {
      canCreateChats: isAdmin || !!payload.can_create_chats,
      canDeleteChats: isAdmin || !!payload.can_delete_chats,
      canRenameChats: isAdmin || !!payload.can_rename_chats,
      canControlHardware: isAdmin || !!payload.can_control_hardware,
      canManageUsers: isAdmin || !!payload.can_manage_users,
    };
  } catch {
    return defaults;
  }
}

export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (!payload.exp) return true;
    return Number(payload.exp) * 1000 <= Date.now() + 5000;
  } catch {
    return true;
  }
}
