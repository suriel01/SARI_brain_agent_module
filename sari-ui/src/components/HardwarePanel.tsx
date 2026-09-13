import { useState } from 'react';
import { BellRing, Lock, Search, Clock, Download, Trash2, Expand, Minimize2 } from 'lucide-react';
import RadarMap from './RadarMap';
import Telemetry from './Telemetry';
import { apiFetch, readErrorDetail } from '../api';
import type { Permissions } from '../permissions';
import { useLanguage } from '../i18n/LanguageContext';

interface HardwarePanelProps {
  token: string;
  permissions: Permissions;
  requestPin: (actionName: string, callback: (pin: string) => void) => void;
  state: any;
  fetchState: () => void;
  onNavigateToEye?: (nodeId: string) => void;
}

export default function HardwarePanel({ token, permissions, requestPin, state, fetchState, onNavigateToEye }: HardwarePanelProps) {
  const { t } = useLanguage();
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState('ALL');
  const [moduleFilter, setModuleFilter] = useState('ALL');
  const [isLogsExpanded, setIsLogsExpanded] = useState(false);
  
  const handleManualAction = (actionName: string) => {
    if (!permissions.canControlHardware) {
      alert(t('pinRequiredAction'));
      return;
    }
    requestPin(actionName, async (pin) => {
      try {
        const res = await apiFetch('/manual_action', token, {
          method: 'POST',
          body: JSON.stringify({ action: actionName, pin })
        });
        if (!res.ok) {
          alert(await readErrorDetail(res, 'Error executing hardware action.'));
        }
        fetchState();
      } catch (e) {
        console.error('Error executing manual action', e);
      }
    });
  };

  // Filter logs based on query, level, module and non-expired TTL
  const filteredLogs = (state?.logs || []).filter((log: any) => {
    // Check level
    if (levelFilter !== 'ALL' && log.level !== levelFilter) return false;

    // Check module
    const mod = log.camera_module || 'SYS_CORE';
    if (moduleFilter !== 'ALL' && mod !== moduleFilter) return false;

    // Check search query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchMsg = (log.message || '').toLowerCase().includes(q);
      const matchMod = mod.toLowerCase().includes(q);
      const matchLevel = (log.level || '').toLowerCase().includes(q);
      const matchTs = (log.timestamp || '').toLowerCase().includes(q);
      if (!matchMsg && !matchMod && !matchLevel && !matchTs) return false;
    }

    if (log.expires_at) {
      const exp = new Date(String(log.expires_at).replace(' ', 'T'));
      if (!Number.isNaN(exp.getTime()) && exp.getTime() <= Date.now()) return false;
    }

    return true;
  });

  return (
    <div className="p-6 h-full overflow-y-auto text-zinc-900 dark:text-zinc-100 transition-colors">
      
      {/* Top Section: Radar and Telemetry */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 flex flex-col items-center shadow-sm transition-all">
          <div className="w-full flex justify-between items-center mb-4">
            <h3 className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest">{t('perimeterScan')}</h3>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>
          <RadarMap nodes={state?.nodes || []} nodesCount={state?.nodes_count || 0} onSelectNode={onNavigateToEye} />
        </div>

        <div className="bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 flex flex-col shadow-sm transition-all">
          <div className="w-full flex justify-between items-center mb-4">
            <h3 className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest">{t('systemTelemetry')}</h3>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          </div>
          <Telemetry systemTelemetry={state?.system_telemetry} />
        </div>
      </div>

      {/* Middle Section: Manual Controls (Pill Toggles) */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 mb-6 shadow-sm transition-all">
        <h3 className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest mb-4">{t('physicalControls')}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          
          {/* Siren Pill Toggle Button */}
          <button 
            className={`px-6 py-3.5 rounded-full flex items-center justify-center gap-2.5 font-semibold text-xs transition-all active:scale-95 shadow-sm ${
              state?.siren_active 
                ? 'bg-red-600 text-white border border-red-600 shadow-md shadow-red-600/30 animate-pulse' 
                : 'bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700'
            } ${!permissions.canControlHardware ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            onClick={() => handleManualAction('toggle_sirena')}
            disabled={!permissions.canControlHardware}
          >
            <BellRing size={16} /> 
            <span>{state?.siren_active ? t('tacticalSirenActive') : t('tacticalSirenInactive')}</span>
          </button>

          {/* Gates Pill Toggle Button */}
          <button 
            className={`px-6 py-3.5 rounded-full flex items-center justify-center gap-2.5 font-semibold text-xs transition-all active:scale-95 shadow-sm ${
              state?.gates_locked 
                ? 'bg-amber-600 text-white border border-amber-600 shadow-md shadow-amber-600/30' 
                : 'bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700'
            } ${!permissions.canControlHardware ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            onClick={() => handleManualAction('toggle_accesos')}
            disabled={!permissions.canControlHardware}
          >
            <Lock size={16} /> 
            <span>{state?.gates_locked ? t('gatesLocked') : t('gatesUnlocked')}</span>
          </button>

        </div>
      </div>

      {/* Bottom Section: Event Table with Filters & TTL Expiration */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-6 shadow-sm transition-all">
        
        {/* Header & Filter Controls Bar */}
        <div className="flex justify-between items-center mb-5 flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <h3 className="text-[11px] font-bold text-zinc-400 dark:text-zinc-500 uppercase tracking-widest m-0">{t('eventLogsAndAudit')}</h3>
            <span className="text-[11px] bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 px-3 py-1 rounded-full border border-zinc-200/60 dark:border-zinc-700/60 font-semibold shadow-sm">
              {t('ttl24Hours')}
            </span>
          </div>

          {/* Filters Bar (Pill Elements) */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {/* Search Input Pill */}
            <div className="relative flex items-center">
              <Search size={13} className="absolute left-3.5 text-zinc-400" />
              <input
                type="text"
                placeholder={t('searchEventsPlaceholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4 py-2 bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-full text-zinc-900 dark:text-zinc-100 text-xs w-48 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all shadow-sm"
              />
            </div>

            {/* Level Filter Dropdown Pill */}
            <div className="flex items-center gap-1.5">
              <select
                value={levelFilter}
                onChange={(e) => setLevelFilter(e.target.value)}
                className="px-3.5 py-2 bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-full text-zinc-900 dark:text-zinc-100 text-xs cursor-pointer focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all shadow-sm"
              >
                <option value="ALL">{t('allLevels')}</option>
                <option value="INFO">INFO</option>
                <option value="WARN">WARN</option>
                <option value="ERROR">ERROR</option>
              </select>
            </div>

            {/* Module Filter Dropdown Pill */}
            <select
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="px-3.5 py-2 bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 rounded-full text-zinc-900 dark:text-zinc-100 text-xs cursor-pointer focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all shadow-sm"
            >
              <option value="ALL">{t('allModules')}</option>
              <option value="SYS_CORE">SYS_CORE</option>
              <option value="CHAT_USER">CHAT_USER</option>
              <option value="CHAT_AGENT">CHAT_AGENT</option>
              <option value="CHAT_MGMT">CHAT_MGMT</option>
              <option value="HARDWARE_CTRL">HARDWARE_CTRL</option>
              <option value="AUTH_SYS">AUTH_SYS</option>
              <option value="JETSON_CV">JETSON_CV</option>
            </select>
            
            {/* Export and Clear buttons */}
            <div className="flex items-center gap-2 ml-auto">
              <button 
                onClick={() => {
                  const blob = new Blob([JSON.stringify(filteredLogs, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `sari_event_logs_${new Date().toISOString().split('T')[0]}.json`;
                  a.click();
                }}
                className="bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 px-4 py-2 rounded-full flex items-center gap-1.5 cursor-pointer text-xs font-semibold hover:bg-zinc-200 dark:hover:bg-zinc-700 shadow-sm transition-all active:scale-95"
                title="Export Logs"
              >
                <Download size={13} /> {t('export')}
              </button>
              
              <button 
                onClick={() => alert("Función 'Clear Logs' requiere persistencia en la base de datos.")}
                className="bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 text-zinc-500 hover:text-red-600 dark:hover:text-red-400 px-4 py-2 rounded-full flex items-center gap-1.5 cursor-pointer text-xs font-semibold hover:bg-zinc-200 dark:hover:bg-zinc-700 shadow-sm transition-all active:scale-95"
                title="Clear Logs"
              >
                <Trash2 size={13} /> {t('clear')}
              </button>
            </div>
          </div>
        </div>

        {/* Expand / Collapse Control */}
        <div className="flex justify-end mb-2">
          <button 
            onClick={() => setIsLogsExpanded(!isLogsExpanded)}
            className="text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white text-xs font-medium cursor-pointer flex items-center gap-1.5 transition-colors"
          >
            {isLogsExpanded ? <><Minimize2 size={12} /> {t('collapseView')}</> : <><Expand size={12} /> {t('expandAll')} ({filteredLogs.length})</>}
          </button>
        </div>

        {/* Logs Table with Rounded Corners */}
        <div className={`overflow-y-auto border border-zinc-200 dark:border-zinc-800 rounded-2xl ${isLogsExpanded ? '' : 'max-h-[400px]'}`}>
        <table className="w-full border-collapse text-xs text-left">
          <thead>
            <tr className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-800/50">
              <th className="p-3 font-semibold">{t('timestamp')}</th>
              <th className="p-3 font-semibold">{t('level')}</th>
              <th className="p-3 font-semibold">{t('module')}</th>
              <th className="p-3 font-semibold">{t('eventDescription')}</th>
              <th className="p-3 font-semibold">{t('ttlExpiration')}</th>
            </tr>
          </thead>
          <tbody>
            {(isLogsExpanded ? filteredLogs : filteredLogs.slice(0, 20)).map((log: any, idx: number) => (
              <tr key={idx} className="border-b border-zinc-100 dark:border-zinc-800/50 last:border-0 hover:bg-zinc-50 dark:hover:bg-zinc-800/30 transition-colors">
                <td className="p-3 text-zinc-500 dark:text-zinc-400 whitespace-nowrap text-xs">{log.timestamp}</td>
                <td className="p-3">
                  <span className={`px-2 py-0.5 rounded-md text-xs font-bold ${
                    log.level === 'WARN' ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-500' : 
                    log.level === 'ERROR' ? 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-500' : 
                    'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700'
                  }`}>
                    {log.level}
                  </span>
                </td>
                <td className="p-3">
                  <span className="bg-zinc-100 dark:bg-zinc-800 px-2 py-0.5 rounded-md text-zinc-700 dark:text-zinc-300 text-xs font-mono border border-zinc-200 dark:border-zinc-700">
                    {log.camera_module || 'SYS_CORE'}
                  </span>
                </td>
                <td className="p-3 text-zinc-700 dark:text-zinc-300 font-medium">{log.message}</td>
                <td className="p-3 text-zinc-500 dark:text-zinc-400 text-xs whitespace-nowrap">
                  <span className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-500 font-semibold">
                    <Clock size={12} /> {log.expires_at ? log.expires_at : '24h Auto-Purge'}
                  </span>
                </td>
              </tr>
            ))}
            {filteredLogs.length === 0 && (
              <tr>
                <td colSpan={5} className="p-6 text-center text-zinc-400 dark:text-zinc-500 italic">
                  {t('noLogsFound')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
      </div>

    </div>
  );
}
