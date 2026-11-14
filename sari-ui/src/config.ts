export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) || 'http://localhost:7000/api';

/** Realtime socket URL. Browsers cannot set headers on a WebSocket, so the JWT travels as `?token=`. */
export function realtimeWsUrl(token: string): string {
  return `ws://${window.location.hostname}:8000/ws?token=${encodeURIComponent(token)}`;
}
