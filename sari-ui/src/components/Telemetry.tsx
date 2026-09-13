import { useEffect, useState } from 'react';
import { useLanguage } from '../i18n/LanguageContext';
import { Cpu, Zap, HardDrive } from 'lucide-react';

interface TelemetryProps {
  systemTelemetry?: any;
}

export default function Telemetry({ systemTelemetry }: TelemetryProps) {
  const { t, language } = useLanguage();
  const [netLoad, setNetLoad] = useState<number[]>(Array(10).fill(12));

  useEffect(() => {
    const interval = setInterval(() => {
      setNetLoad(prev => {
        const next = [...prev.slice(1), Math.random() * 60 + 15];
        return next;
      });
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  const gpuLoad = Math.round(systemTelemetry?.gpu_load_pct ?? 0);
  const gpuTemp = Math.round(systemTelemetry?.gpu_temp_c ?? 44);
  const cpuTemp = Math.round(systemTelemetry?.cpu_temp_c ?? 54);
  const vramUsed = systemTelemetry?.vram_used_gb ?? 4.95;
  const vramTotal = systemTelemetry?.vram_total_gb ?? 8.0;
  const vramPct = Math.round(systemTelemetry?.vram_pct ?? (vramUsed / vramTotal) * 100);
  const cpuLoad = Math.round(systemTelemetry?.cpu_load_pct ?? 24);
  const modelName = systemTelemetry?.model_name || 'qwen2.5:7b';
  const modelStatus = systemTelemetry?.model_status || (language === 'en' ? 'Active in VRAM' : 'Activo en VRAM');
  const gpuName = systemTelemetry?.gpu_name || 'NVIDIA RTX 4070';

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

      {/* GPU Load & GPU Temp (RTX 4070) */}
      <div>
        <div className="flex justify-between mb-1 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400 uppercase tracking-wider font-semibold flex items-center gap-1.5">
            <Cpu size={13} className="text-zinc-400" />
            {language === 'en' ? 'GPU Load' : 'Carga GPU'} ({gpuName.replace('NVIDIA GeForce ', '').replace('NVIDIA ', '')})
          </span>
          <div className="flex items-center gap-2 font-mono font-bold text-xs">
            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
              {gpuTemp}°C
            </span>
            <span className="text-zinc-900 dark:text-zinc-100">{gpuLoad}%</span>
          </div>
        </div>
        <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-zinc-200/60 dark:border-zinc-700/60">
          <div 
            className="h-full bg-emerald-500 rounded-full transition-all duration-500 shadow-sm"
            style={{ width: `${Math.max(gpuLoad, 6)}%` }}
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
            {vramUsed} / {vramTotal} GB ({vramPct}%)
          </span>
        </div>
        <div className="w-full h-2 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden border border-zinc-200/60 dark:border-zinc-700/60">
          <div 
            className={`h-full rounded-full transition-all duration-500 ${
              vramPct > 85 ? 'bg-red-500' : vramPct > 70 ? 'bg-amber-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${Math.max(vramPct, 10)}%` }}
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
                {cpuTemp}°C
              </span>
              <span className="font-bold text-zinc-900 dark:text-zinc-100">{cpuLoad}%</span>
            </div>
          </div>
          <div className="w-full h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-zinc-700 dark:bg-zinc-300 rounded-full transition-all duration-500" 
              style={{ width: `${cpuLoad}%` }} 
            />
          </div>
        </div>

        <div>
          <div className="flex justify-between text-[11px] mb-1">
            <span className="text-zinc-500 uppercase tracking-wider font-semibold">{t('networkTxRx')}</span>
            <span className="font-bold font-mono text-zinc-900 dark:text-zinc-100">
              {Math.round(netLoad[netLoad.length - 1])} MB/s
            </span>
          </div>
          <div className="flex gap-0.5 h-1.5 items-end">
            {netLoad.map((val, idx) => (
              <div 
                key={idx} 
                className="flex-1 bg-zinc-400 dark:bg-zinc-600 rounded-sm"
                style={{ height: `${Math.max(val, 15)}%` }}
              />
            ))}
          </div>
        </div>
      </div>

    </div>
  );
}
