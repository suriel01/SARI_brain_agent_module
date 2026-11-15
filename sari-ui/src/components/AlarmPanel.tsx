import { useCallback, useEffect, useState } from 'react';
import { DoorOpen, House, Moon, ShieldAlert, ShieldCheck, ShieldOff, Timer, TriangleAlert, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { apiFetch } from '../api';
import type { Permissions } from '../permissions';
import { useLanguage } from '../i18n/LanguageContext';
import type { TranslationKey } from '../i18n/translations';

// -- Backend contract (GET /api/alarm, POST /api/alarm/arm|disarm, GET /api/alarm/timeline) --------

type ArmMode = 'away' | 'home' | 'night';

interface AlarmFault {
  device_id: string;
  kind: string;
  since: number | null;
  reason: string | null;
}

interface AlarmView {
  state: string;
  mode: ArmMode | null;
  since: number | null;
  deadline: number | null;
  cause: string | null;
  remaining_seconds: number | null;
  faults?: AlarmFault[];
}

interface AlarmEvent {
  id: number;
  at: number | null;
  kind: string;
  from_state: string | null;
  to_state: string | null;
  cause: string | null;
  actor: string | null;
}

type CommandOutcome = { ok: true } | { ok: false; status: string | null; message: string };

const POLL_MS = 5000;
const TIMELINE_LIMIT = 50;
const DASH = '—';
const ARM_MODES: ArmMode[] = ['away', 'home', 'night'];

const STATE_LABELS: Record<string, TranslationKey> = {
  disarmed: 'alarmStateDisarmed',
  arming: 'alarmStateArming',
  armed_away: 'alarmStateArmedAway',
  armed_home: 'alarmStateArmedHome',
  armed_night: 'alarmStateArmedNight',
  pending: 'alarmStatePending',
  triggered: 'alarmStateTriggered',
};

const MODE_LABELS: Record<ArmMode, TranslationKey> = { away: 'alarmModeAway', home: 'alarmModeHome', night: 'alarmModeNight' };
const ARM_LABELS: Record<ArmMode, TranslationKey> = { away: 'alarmArmAway', home: 'alarmArmHome', night: 'alarmArmNight' };
const ARM_ICONS: Record<ArmMode, LucideIcon> = { away: DoorOpen, home: House, night: Moon };

const EVENT_LABELS: Record<string, TranslationKey> = {
  transition: 'alarmEventTransition',
  detection_ignored: 'alarmEventDetectionIgnored',
  failed_to_arm: 'alarmEventFailedToArm',
  fault: 'alarmEventFault',
  fault_cleared: 'alarmEventFaultCleared',
};

type Tone = 'alert' | 'warn' | 'armed' | 'neutral';

const TONE_BANNER: Record<Tone, string> = {
  alert: 'bg-red-600 text-white border border-red-600 shadow-md shadow-red-600/30 animate-pulse',
  warn: 'bg-amber-500 text-white border border-amber-500 shadow-md shadow-amber-500/30',
  armed: 'bg-emerald-600 text-white border border-emerald-600 shadow-md shadow-emerald-600/20',
  neutral: 'bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700',
};
const TONE_ICON: Record<Tone, LucideIcon> = { alert: ShieldAlert, warn: Timer, armed: ShieldCheck, neutral: ShieldOff };

const CARD = 'bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 shadow-sm transition-all';
const CARD_TITLE = 'text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest';
const PILL = 'px-4 py-3 rounded-full flex items-center justify-center gap-2 font-semibold text-xs transition-all shadow-sm';
const PILL_IDLE = 'bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700';

// -- Pure helpers ---------------------------------------------------------------------------------

function toneOf(state: string | undefined): Tone {
  if (state === 'pending' || state === 'triggered') return 'alert';
  if (state === 'arming') return 'warn';
  if (state?.startsWith('armed_')) return 'armed';
  return 'neutral';
}

function orDash(value: string | null | undefined): string {
  return value ? value : DASH;
}

function formatTime(seconds: number | null | undefined, locale: string): string {
  if (typeof seconds !== 'number' || !Number.isFinite(seconds)) return DASH;
  return new Date(seconds * 1000).toLocaleString(locale);
}

function formatCountdown(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, '0')}`;
}

/** Seconds left on the current delay, ticked locally from the server's own count (no clock skew). */
function secondsLeft(status: AlarmView | null, receivedAt: number, now: number): number | null {
  if (!status) return null;
  if (typeof status.remaining_seconds === 'number') {
    return Math.max(0, Math.ceil(status.remaining_seconds - Math.max(0, now - receivedAt) / 1000));
  }
  if (typeof status.deadline === 'number') return Math.max(0, Math.ceil(status.deadline - now / 1000));
  return null;
}

async function postAlarm(token: string, path: string, body: Record<string, unknown>): Promise<CommandOutcome> {
  const res = await apiFetch(path, token, { method: 'POST', body: JSON.stringify(body) });
  const payload = await res.json().catch(() => null);
  if (res.ok && payload?.status === 'success') return { ok: true };
  // FastAPI errors: {detail: "<text>"} for PIN checks, {detail: {status, message, faults?}} for alarm rules.
  const detail = payload?.detail ?? payload;
  if (typeof detail === 'string') return { ok: false, status: null, message: detail };
  return { ok: false, status: detail?.status ?? null, message: typeof detail?.message === 'string' ? detail.message : '' };
}

// -- Container ------------------------------------------------------------------------------------

interface AlarmPanelProps {
  token: string;
  permissions: Permissions;
  requestPin: (actionName: string, callback: (pin: string) => void) => void;
  /** Bumped by the dashboard WebSocket on `alarm_state` / `alarm_fault`. */
  realtimeTick: number;
}

export default function AlarmPanel({ token, permissions, requestPin, realtimeTick }: AlarmPanelProps) {
  const { t, language } = useLanguage();
  const locale = language === 'en' ? 'en-US' : 'es-ES';
  const [status, setStatus] = useState<AlarmView | null>(null);
  const [timeline, setTimeline] = useState<AlarmEvent[] | null>(null);
  const [receivedAt, setReceivedAt] = useState(0);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await apiFetch('/alarm', token);
      const data = res.ok ? await res.json() : null;
      const at = Date.now();
      setStatus(data);
      setReceivedAt(at);
      setNow(at);
    } catch (e) {
      console.error('Error fetching alarm status', e);
      setStatus(null);
    }
  }, [token]);

  const fetchTimeline = useCallback(async () => {
    try {
      const res = await apiFetch(`/alarm/timeline?limit=${TIMELINE_LIMIT}`, token);
      setTimeline(res.ok ? await res.json() : null);
    } catch (e) {
      console.error('Error fetching alarm timeline', e);
      setTimeline(null);
    }
  }, [token]);

  // Initial load and every realtime notification.
  useEffect(() => {
    fetchStatus();
    fetchTimeline();
  }, [realtimeTick, fetchStatus, fetchTimeline]);

  // Fallback poll in case the WebSocket is down.
  useEffect(() => {
    const id = setInterval(fetchStatus, POLL_MS);
    return () => clearInterval(id);
  }, [fetchStatus]);

  // A transition or fault change seen by the poll also refreshes the timeline.
  const changeKey = status
    ? `${status.state}|${status.since}|${(status.faults ?? []).map((f) => f.device_id).join(',')}`
    : '';
  useEffect(() => {
    if (changeKey) fetchTimeline();
  }, [changeKey, fetchTimeline]);

  const counting = typeof status?.remaining_seconds === 'number' || typeof status?.deadline === 'number';
  useEffect(() => {
    if (!counting) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [counting]);

  const runCommand = (label: string, path: string, body: Record<string, unknown>) => {
    requestPin(label, async (pin) => {
      setBusy(true);
      setNotice(null);
      try {
        let outcome = await postAlarm(token, path, { ...body, pin });
        if (!outcome.ok && outcome.status === 'failed_to_arm'
          && window.confirm(`${outcome.message}\n\n${t('alarmForceConfirm')}`)) {
          outcome = await postAlarm(token, path, { ...body, pin, force: true });
        }
        if (!outcome.ok) setNotice(outcome.message || t('alarmActionFailed'));
      } catch (e) {
        console.error('Alarm command failed', e);
        setNotice(t('alarmActionFailed'));
      } finally {
        setBusy(false);
        fetchStatus();
        fetchTimeline();
      }
    });
  };

  const canControl = permissions.canControlHardware;

  return (
    <div className="p-6 pb-0 text-zinc-900 dark:text-zinc-100 transition-colors">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className={CARD}>
          <CardHeader title={t('alarmPanelTitle')} />
          <AlarmStatusSummary status={status} remaining={secondsLeft(status, receivedAt, now)} locale={locale} />
          <AlarmControls
            status={status}
            canControl={canControl}
            busy={busy}
            onArm={(mode) => runCommand(t(ARM_LABELS[mode]), '/alarm/arm', { mode })}
            onDisarm={() => runCommand(t('alarmDisarm'), '/alarm/disarm', {})}
          />
          {notice && <Notice text={notice} onDismiss={() => setNotice(null)} />}
          <FaultList faults={status ? status.faults ?? null : null} locale={locale} />
        </section>

        <section className={CARD}>
          <CardHeader title={t('alarmTimelineTitle')} />
          <AlarmTimeline events={timeline} locale={locale} />
        </section>
      </div>
    </div>
  );
}

// -- Presentational -------------------------------------------------------------------------------

function CardHeader({ title }: { title: string }) {
  return <h3 className={`${CARD_TITLE} mb-4`}>{title}</h3>;
}

function AlarmStatusSummary({ status, remaining, locale }: { status: AlarmView | null; remaining: number | null; locale: string }) {
  const { t } = useLanguage();
  const tone = toneOf(status?.state);
  const Icon = TONE_ICON[tone];
  const stateKey = status ? STATE_LABELS[status.state] : undefined;
  const stateText = status?.state ? (stateKey ? t(stateKey) : status.state) : DASH;
  const countdownLabel = status?.state === 'arming' ? t('alarmExitDelay')
    : status?.state === 'pending' ? t('alarmEntryDelay') : t('alarmTimeLeft');
  const modeKey = status?.mode ? MODE_LABELS[status.mode] : undefined;

  return (
    <>
      <div role="status" aria-live="polite" className={`rounded-2xl px-5 py-4 flex items-center justify-between gap-4 ${TONE_BANNER[tone]}`}>
        <div className="flex items-center gap-3">
          <Icon size={22} />
          <div>
            <div className="text-[10px] uppercase tracking-widest font-bold opacity-75">{t('alarmStateLabel')}</div>
            <div className="text-lg font-bold leading-tight">{stateText}</div>
          </div>
        </div>
        {remaining !== null && (
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-widest font-bold opacity-75">{countdownLabel}</div>
            <div className="text-2xl font-mono font-bold tabular-nums leading-tight">{formatCountdown(remaining)}</div>
          </div>
        )}
      </div>
      {!status && <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400 italic">{t('alarmUnavailable')}</p>}
      <dl className="grid grid-cols-3 gap-3 mt-4 text-xs">
        <Field label={t('alarmModeLabel')} value={modeKey ? t(modeKey) : orDash(status?.mode)} />
        <Field label={t('alarmSinceLabel')} value={formatTime(status?.since, locale)} />
        <Field label={t('alarmCauseLabel')} value={orDash(status?.cause)} />
      </dl>
    </>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-wider">{label}</dt>
      <dd className="mt-0.5 font-medium text-zinc-700 dark:text-zinc-300 truncate" title={value}>{value}</dd>
    </div>
  );
}

interface AlarmControlsProps {
  status: AlarmView | null;
  canControl: boolean;
  busy: boolean;
  onArm: (mode: ArmMode) => void;
  onDisarm: () => void;
}

function AlarmControls({ status, canControl, busy, onArm, onDisarm }: AlarmControlsProps) {
  const { t } = useLanguage();
  const disabled = !canControl || busy;
  const lock = disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer active:scale-95';
  const urgent = toneOf(status?.state) === 'alert';
  const isCurrent = (mode: ArmMode) => status?.mode === mode && status.state !== 'disarmed';

  return (
    <div className="mt-5">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {ARM_MODES.map((mode) => {
          const Icon = ARM_ICONS[mode];
          const active = isCurrent(mode) ? 'bg-zinc-900 text-white border border-zinc-900 dark:bg-white dark:text-zinc-950 dark:border-white' : PILL_IDLE;
          return (
            <button key={mode} type="button" className={`${PILL} ${active} ${lock}`} disabled={disabled}
              title={canControl ? undefined : t('alarmReadOnly')} onClick={() => onArm(mode)}>
              <Icon size={14} /> <span>{t(ARM_LABELS[mode])}</span>
            </button>
          );
        })}
        <button type="button" disabled={disabled} title={canControl ? undefined : t('alarmReadOnly')} onClick={onDisarm}
          className={`${PILL} ${urgent ? 'bg-red-600 text-white border border-red-600 shadow-md shadow-red-600/30' : PILL_IDLE} ${lock}`}>
          <ShieldOff size={14} /> <span>{t('alarmDisarm')}</span>
        </button>
      </div>
      {!canControl && <p className="mt-2.5 text-[11px] text-zinc-500 dark:text-zinc-400">{t('alarmReadOnly')}</p>}
    </div>
  );
}

function Notice({ text, onDismiss }: { text: string; onDismiss: () => void }) {
  return (
    <div role="alert" className="mt-4 rounded-2xl border border-red-200 dark:border-red-900/60 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-400 px-4 py-2.5 text-xs flex items-start justify-between gap-3">
      <span className="whitespace-pre-line">{text}</span>
      <button type="button" onClick={onDismiss} className="shrink-0 opacity-70 hover:opacity-100 cursor-pointer"><X size={13} /></button>
    </div>
  );
}

function FaultList({ faults, locale }: { faults: AlarmFault[] | null; locale: string }) {
  const { t } = useLanguage();
  return (
    <div className="mt-6">
      <div className="flex items-center gap-2 mb-2.5">
        <h4 className={CARD_TITLE}>{t('alarmFaultsTitle')}</h4>
        {faults && faults.length > 0 && (
          <span className="text-[10px] font-bold bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-500 px-2 py-0.5 rounded-full">{faults.length}</span>
        )}
      </div>
      {faults === null ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{DASH}</p>
      ) : faults.length === 0 ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{t('alarmNoFaults')}</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {faults.map((fault) => (
            <li key={`${fault.device_id}:${fault.kind}`} className="flex items-start gap-2.5 p-3 rounded-2xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200/70 dark:border-amber-800/50 text-xs">
              <TriangleAlert size={14} className="text-amber-600 dark:text-amber-500 mt-0.5 shrink-0" />
              <div className="min-w-0">
                <div className="font-semibold text-zinc-800 dark:text-zinc-200">
                  {orDash(fault.device_id)}
                  <span className="ml-2 font-mono text-[10px] text-amber-700 dark:text-amber-500">{orDash(fault.kind)}</span>
                </div>
                <div className="text-zinc-600 dark:text-zinc-400 break-words">{orDash(fault.reason)}</div>
              </div>
              <div className="ml-auto text-zinc-500 dark:text-zinc-400 whitespace-nowrap">{formatTime(fault.since, locale)}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function eventBadge(kind: string): string {
  if (kind === 'fault' || kind === 'failed_to_arm') return 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-500';
  if (kind === 'fault_cleared') return 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-500';
  return 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700';
}

function AlarmTimeline({ events, locale }: { events: AlarmEvent[] | null; locale: string }) {
  const { t } = useLanguage();
  const stateText = (state: string | null) => (state ? (STATE_LABELS[state] ? t(STATE_LABELS[state]) : state) : DASH);
  const kindText = (kind: string) => (EVENT_LABELS[kind] ? t(EVENT_LABELS[kind]) : orDash(kind));

  return (
    <div className="overflow-y-auto max-h-[360px] border border-zinc-200 dark:border-zinc-800 rounded-2xl">
      <table className="w-full border-collapse text-xs text-left">
        <thead>
          <tr className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/50">
            <th className="p-3 font-semibold">{t('timestamp')}</th>
            <th className="p-3 font-semibold">{t('alarmColEvent')}</th>
            <th className="p-3 font-semibold">{t('alarmColChange')}</th>
            <th className="p-3 font-semibold">{t('alarmCauseLabel')}</th>
            <th className="p-3 font-semibold">{t('alarmColActor')}</th>
          </tr>
        </thead>
        <tbody>
          {(events ?? []).map((event) => (
            <tr key={event.id} className="border-b border-zinc-100 dark:border-zinc-800/50 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors">
              <td className="p-3 text-zinc-500 dark:text-zinc-400 whitespace-nowrap">{formatTime(event.at, locale)}</td>
              <td className="p-3">
                <span className={`px-2 py-0.5 rounded-md font-bold whitespace-nowrap ${eventBadge(event.kind)}`}>{kindText(event.kind)}</span>
              </td>
              <td className="p-3 text-zinc-700 dark:text-zinc-300 whitespace-nowrap">
                {event.from_state || event.to_state ? `${stateText(event.from_state)} → ${stateText(event.to_state)}` : DASH}
              </td>
              <td className="p-3 text-zinc-700 dark:text-zinc-300 break-words">{orDash(event.cause)}</td>
              <td className="p-3 text-zinc-500 dark:text-zinc-400 font-mono whitespace-nowrap">{orDash(event.actor)}</td>
            </tr>
          ))}
          {(events === null || events.length === 0) && (
            <tr>
              <td colSpan={5} className="p-6 text-center text-zinc-400 dark:text-zinc-500 italic">
                {events === null ? DASH : t('alarmNoEvents')}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
