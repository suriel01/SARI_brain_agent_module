import { useLanguage } from '../i18n/LanguageContext';

interface RadarMapProps {
  nodes?: any[];
  nodesCount?: number;
  onSelectNode?: (nodeId: string) => void;
}

export default function RadarMap({ nodes = [], nodesCount = 0, onSelectNode }: RadarMapProps) {
  const { language } = useLanguage();

  // Positions for nodes on the radar screen (polar offset percentages around center 50%, 50%)
  const nodePositions = [
    { x: 68, y: 32 }, // North-East
    { x: 30, y: 65 }, // South-West
    { x: 72, y: 68 }, // South-East
    { x: 28, y: 35 }, // North-West
    { x: 50, y: 22 }, // North
  ];

  return (
    <div className="w-full flex flex-col items-center">
      {/* Radar Disc Container */}
      <div className="w-full aspect-square max-w-[260px] mx-auto bg-zinc-100/90 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-full relative overflow-hidden flex items-center justify-center shadow-inner">
        {/* Crosshair grid lines */}
        <div className="absolute w-full h-[1px] bg-zinc-300/60 dark:bg-zinc-800/80" />
        <div className="absolute w-[1px] h-full bg-zinc-300/60 dark:bg-zinc-800/80" />
        
        {/* Concentric distance range rings */}
        <div className="absolute w-[75%] h-[75%] border border-zinc-300/60 dark:border-zinc-800/80 rounded-full" />
        <div className="absolute w-[45%] h-[45%] border border-zinc-300/60 dark:border-zinc-800/80 rounded-full" />
        <div className="absolute w-[15%] h-[15%] border border-dashed border-zinc-300/60 dark:border-zinc-800/80 rounded-full" />

        {/* Sweeping Radar beam */}
        <div 
          className="radar-sweep absolute top-1/2 left-1/2 w-1/2 h-1/2 origin-top-left pointer-events-none" 
          style={{
            background: 'conic-gradient(from 0deg, transparent 0deg, rgba(16,185,129,0.25) 90deg, transparent 90deg)'
          }} 
        />

        {/* Only Display Actively Connected / Online Jetson Node Blips */}
        {(() => {
          const onlineNodes = nodes.filter((n) => n.is_online === true);

          if (onlineNodes.length === 0) {
            return (
              <div className="z-10 text-[10px] text-zinc-400 dark:text-zinc-600 font-mono text-center px-4">
                {language === 'en' ? 'Scanning perimeter for online Jetson nodes...' : 'Buscando nodos Jetson conectados...'}
              </div>
            );
          }

          return onlineNodes.map((node, i) => {
            const pos = nodePositions[i % nodePositions.length];

            return (
              <button 
                key={node.node_id || i} 
                type="button"
                onClick={() => onSelectNode?.(node.node_id)}
                title={language === 'en' ? `Open Eye Module: ${node.node_id}` : `Abrir Módulo Ojo: ${node.node_id}`}
                className="absolute z-10 flex flex-col items-center group cursor-pointer transition-all duration-300 hover:scale-110 active:scale-95 focus:outline-none"
                style={{
                  left: `${pos.x}%`,
                  top: `${pos.y}%`,
                  transform: 'translate(-50%, -50%)'
                }}
              >
                {/* Outer pulsing ping wave */}
                <div className="absolute w-7 h-7 rounded-full bg-emerald-500/30 animate-ping pointer-events-none" />
                
                {/* Core Node Marker (Green Online) */}
                <div className="w-3.5 h-3.5 rounded-full flex items-center justify-center shadow-lg transition-transform hover:scale-125 border bg-emerald-500 border-emerald-300 text-black shadow-emerald-500/50">
                  <div className="w-1.5 h-1.5 rounded-full bg-white" />
                </div>

                {/* Node Tag Pill */}
                <div className="mt-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold tracking-tight bg-black/80 text-white backdrop-blur-sm border border-white/20 whitespace-nowrap shadow-sm">
                  {node.node_id || `Node-${i+1}`}
                </div>
              </button>
            );
          });
        })()}
      </div>

      {/* Dynamic Status Counter Footer */}
      <div 
        onClick={() => {
          const firstOnline = nodes.find((n) => n.is_online === true);
          if (firstOnline && onSelectNode) {
            onSelectNode(firstOnline.node_id);
          }
        }}
        className={`mt-3 flex items-center gap-2 px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800/80 border border-zinc-200/80 dark:border-zinc-700/80 shadow-sm text-xs font-semibold ${nodes.length > 0 ? 'cursor-pointer hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-colors' : ''}`}
        title={nodes.length > 0 ? (language === 'en' ? 'Click to open in Eyes module' : 'Clic para abrir en módulo Ojos') : undefined}
      >
        <div className={`w-2 h-2 rounded-full ${nodesCount > 0 ? 'bg-emerald-500 animate-pulse' : 'bg-zinc-400'}`} />
        <span className="text-zinc-800 dark:text-zinc-200 font-mono">
          {nodesCount} {nodesCount === 1 
            ? (language === 'en' ? 'Jetson Node Online' : 'Jetson Conectado')
            : (language === 'en' ? 'Jetson Nodes Online' : 'Jetsons Conectados')}
        </span>
        {nodesCount > 0 && (
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">
            1080p LIVE
          </span>
        )}
      </div>
    </div>
  );
}
