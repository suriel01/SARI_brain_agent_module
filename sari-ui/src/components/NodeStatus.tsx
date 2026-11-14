import { Server, Activity, Radio, Video, Wifi } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';

const UNKNOWN = '—';

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function show(value: number | null, unit: string, digits = 0): string {
  return value === null ? UNKNOWN : `${digits ? value.toFixed(digits) : Math.round(value)}${unit}`;
}

interface NodeStatusProps {
  nodes?: any[];
}

export default function NodeStatus({ nodes = [] }: NodeStatusProps) {
  const { t, language } = useLanguage();
  const primaryNode = nodes[0] || null;
  const isOnline = primaryNode ? primaryNode.is_online !== false : false;

  // Unknown values arrive as null and are shown as "—"; nothing is invented (S15).
  const ramUsed = num(primaryNode?.ram_used_gb);
  const ramTotal = num(primaryNode?.ram_total_gb);
  const ramPct = ramUsed !== null && ramTotal ? (ramUsed / ramTotal) * 100 : null;
  const npuLoad = num(primaryNode?.gpu_load_pct);
  const nodeTemp = num(primaryNode?.temp_c);
  const nodeFps = num(primaryNode?.fps);
  const nodeIp: string = primaryNode?.ip || UNKNOWN;
  const nodeId: string = primaryNode?.node_id || (language === 'en' ? 'No node reporting' : 'Ningún nodo reportando');
  const nodeLink: string = primaryNode?.link_status || UNKNOWN;

  return (
    <div className="flex flex-col gap-3 w-full">
      
      {/* Node Header Badge */}
      <div className="flex items-center justify-between px-3.5 py-1.5 rounded-xl bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 shadow-sm text-xs">
        <div className="flex items-center gap-2">
          <Radio size={14} className={isOnline ? 'text-emerald-500 animate-pulse' : 'text-zinc-400'} />
          <span className="font-bold text-zinc-900 dark:text-zinc-100 font-mono">
            {nodeId}
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
          isOnline 
            ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/20' 
            : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-400 border-zinc-500/20'
        }`}>
          {isOnline 
            ? (language === 'en' ? 'ONLINE (REAL-TIME)' : 'EN LÍNEA (TIEMPO REAL)') 
            : (language === 'en' ? 'STANDBY' : 'EN ESPERA')}
        </span>
      </div>

      {/* NPU / GPU AI Load & Temp */}
      <div>
        <div className="flex justify-between mb-1 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
            <Activity size={13} className="text-zinc-400" />
            {t('npuLoad')}
          </span>
          <div className="flex items-center gap-2 font-mono font-bold text-xs">
            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
              {show(nodeTemp, '°C', 1)}
            </span>
            <span className="text-zinc-900 dark:text-zinc-100">{show(npuLoad, '%')}</span>
          </div>
        </div>
        <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-zinc-200/60 dark:border-zinc-700/60">
          <div 
            className="h-full bg-emerald-500 rounded-full transition-all duration-500 shadow-sm"
            style={{ width: `${npuLoad === null ? 0 : Math.max(npuLoad, 6)}%` }}
          />
        </div>
      </div>

      {/* Jetson RAM Memory */}
      <div>
        <div className="flex justify-between mb-1 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
            <Server size={13} className="text-zinc-400" />
            {t('jetsonRam')}
          </span>
          <span className="text-zinc-900 dark:text-zinc-100 font-bold font-mono">
            {show(ramUsed, '', 2)} / {show(ramTotal, ' GB', 2)} ({show(ramPct, '%')})
          </span>
        </div>
        <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-zinc-200/60 dark:border-zinc-700/60">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              ramPct === null ? 'bg-zinc-400' : ramPct > 85 ? 'bg-red-500' : ramPct > 70 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${ramPct === null ? 0 : Math.max(ramPct, 10)}%` }}
          />
        </div>
      </div>

      {/* FPS & Network Link (Compact dual row) */}
      <div className="grid grid-cols-2 gap-3 pt-1 border-t border-zinc-100 dark:border-zinc-800/80">
        <div>
          <div className="flex justify-between text-[11px] mb-1">
            <span className="text-zinc-500 uppercase tracking-wider font-semibold flex items-center gap-1">
              <Video size={12} className="text-zinc-400" />
              {language === 'en' ? 'Inference' : 'Inferencia'}
            </span>
            <span className="font-bold font-mono text-zinc-900 dark:text-zinc-100">{show(nodeFps, ' FPS', 1)}</span>
          </div>
          <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-emerald-500 rounded-full transition-all duration-500" 
              style={{ width: `${nodeFps === null ? 0 : Math.min(nodeFps * 3.3, 100)}%` }} 
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[11px] mb-1">
            <span className="text-zinc-500 uppercase tracking-wider font-semibold flex items-center gap-1">
              <Wifi size={12} className="text-zinc-400" />
              {t('networkLink')}
            </span>
            <span className="font-bold font-mono text-[10px] text-zinc-900 dark:text-zinc-100 truncate">
              {nodeLink}
            </span>
          </div>
          <div className="text-[10px] font-mono text-zinc-600 dark:text-zinc-400 truncate bg-zinc-100 dark:bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-200/50 dark:border-zinc-700/50">
            {nodeIp}
          </div>
        </div>
      </div>

    </div>
  );
}
