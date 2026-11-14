export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) || 'http://localhost:7000/api';

/**
 * Realtime socket URL, served by the same backend (host, port and path prefix) as `API_BASE`.
 * Browsers cannot set headers on a WebSocket, so the JWT travels as `?token=`.
 */
export function realtimeWsUrl(token: string): string {
  const api = new URL(API_BASE, window.location.href);
  const protocol = api.protocol === 'https:' ? 'wss:' : 'ws:';
  const prefix = api.pathname.replace(/\/api\/?$/, '');
  return `${protocol}//${api.host}${prefix}/ws?token=${encodeURIComponent(token)}`;
}
