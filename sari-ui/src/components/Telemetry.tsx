import { useLanguage } from '../i18n/LanguageContext';
import { Cpu, Zap, HardDrive } from 'lucide-react';

const UNKNOWN = '—';

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function show(value: number | null, unit: string, digits = 0): string {
  return value === null ? UNKNOWN : `${digits ? value.toFixed(digits) : Math.round(value)}${unit}`;
}

interface TelemetryProps {
  systemTelemetry?: any;
}

export default function Telemetry({ systemTelemetry }: TelemetryProps) {
  const { t, language } = useLanguage();

  // Unknown values arrive as null and are shown as "—"; nothing is invented (S15).
  const gpuLoad = num(systemTelemetry?.gpu_load_pct);
  const gpuTemp = num(systemTelemetry?.gpu_temp_c);
  const cpuTemp = num(systemTelemetry?.cpu_temp_c);
  const vramUsed = num(systemTelemetry?.vram_used_gb);
  const vramTotal = num(systemTelemetry?.vram_total_gb);
  const vramPct = num(systemTelemetry?.vram_pct)
    ?? (vramUsed !== null && vramTotal ? (vramUsed / vramTotal) * 100 : null);
  const cpuLoad = num(systemTelemetry?.cpu_load_pct);
  const modelName = systemTelemetry?.model_name || UNKNOWN;
  const modelStatus = systemTelemetry?.model_status || (language === 'en' ? 'Unknown' : 'Desconocido');
  const gpuName: string = systemTelemetry?.gpu_name || UNKNOWN;

  return (
    <div className="flex flex-col gap-3 w-full">
      
      {/* AI Model Pill Header */}
      <div className="flex items-center justify-between px-3.5 py-1.5 rounded-xl bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 shadow-sm text-xs">
        <div className="flex items-center gap-2">
          <Zap size={14} className="text-amber-500 fill-amber-500/20" />
          <span className="font-bold text-zinc-900 dark:text-zinc-100 font-mono">
            {modelName}
          </span>
        </div>
        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
          {modelStatus}
        </span>
      </div>

      {/* Host GPU load & temperature */}
      <div>
        <div className="flex justify-between mb-1 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
            <Cpu size={13} className="text-zinc-400" />
            {language === 'en' ? 'GPU Load' : 'Carga GPU'} ({gpuName.replace('NVIDIA GeForce ', '').replace('NVIDIA ', '')})
          </span>
          <div className="flex items-center gap-2 font-mono font-bold text-xs">
            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
              {show(gpuTemp, '°C')}
            </span>
            <span className="text-zinc-900 dark:text-zinc-100">{show(gpuLoad, '%')}</span>
          </div>
        </div>
        <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-zinc-200/60 dark:border-zinc-700/60">
          <div 
            className="h-full bg-emerald-500 rounded-full transition-all duration-500 shadow-sm"
            style={{ width: `${gpuLoad === null ? 0 : Math.max(gpuLoad, 6)}%` }}
          />
        </div>
      </div>

      {/* VRAM Memory */}
      <div>
        <div className="flex justify-between mb-1 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
            <HardDrive size={13} className="text-zinc-400" />
            {language === 'en' ? 'VRAM Memory' : 'Memoria VRAM'}
          </span>
          <span className="text-zinc-900 dark:text-zinc-100 font-bold font-mono">
            {show(vramUsed, '', 2)} / {show(vramTotal, ' GB', 2)} ({show(vramPct, '%')})
          </span>
        </div>
        <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-zinc-200/60 dark:border-zinc-700/60">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              vramPct === null ? 'bg-zinc-400' : vramPct > 85 ? 'bg-red-500' : vramPct > 70 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${vramPct === null ? 0 : Math.max(vramPct, 10)}%` }}
          />
        </div>
      </div>

      {/* CPU Load, CPU Temp & Network TX/RX (Compact dual row) */}
      <div className="grid grid-cols-2 gap-3 pt-1 border-t border-zinc-100 dark:border-zinc-800/80">
        <div>
          <div className="flex justify-between text-[11px] mb-1">
            <span className="text-zinc-500 uppercase tracking-wider font-semibold">{t('cpuLoad')}</span>
            <div className="flex items-center gap-1.5 font-mono">
              <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
                {show(cpuTemp, '°C')}
              </span>
              <span className="font-bold text-zinc-900 dark:text-zinc-100">{show(cpuLoad, '%')}</span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-zinc-700 dark:bg-zinc-300 rounded-full transition-all duration-500" 
              style={{ width: `${cpuLoad ?? 0}%` }} 
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[11px] mb-1">
            <span className="text-zinc-500 uppercase tracking-wider font-semibold">{t('networkTxRx')}</span>
            {/* No network throughput source is wired yet: report it as unknown instead of a random graph. */}
            <span className="font-bold font-mono text-zinc-900 dark:text-zinc-100">{UNKNOWN}</span>
          </div>
          <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden" />
        </div>
      </div>

    </div>
  );
}
