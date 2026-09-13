import { API_BASE } from './config';

export const AUTH_EXPIRED_EVENT = 'sari-auth-expired';

export function notifyAuthExpired(detail = 'Token expirado') {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail }));
}

export async function apiFetch(path: string, token: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    let detail = 'Token expirado';
    try {
      const body = await res.clone().json();
      if (typeof body?.detail === 'string') {
        detail = body.detail;
      }
    } catch {
      /* ignore parse errors */
    }
    if (detail !== 'PIN de seguridad inválido' && detail !== 'Invalid security PIN') {
      notifyAuthExpired(detail);
    }
  }
  return res;
}

export async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === 'string' && body.detail) {
      return body.detail;
    }
  } catch {
    /* ignore */
  }
  return fallback;
}
