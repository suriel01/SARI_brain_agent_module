import { ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Video, ZoomIn, ZoomOut } from 'lucide-react';
import { useState } from 'react';

export default function CameraControl() {
  const [activeCam, setActiveCam] = useState(1);
  const [isPowerOn, setIsPowerOn] = useState(true);
  const [action, setAction] = useState<string | null>(null);

  const simulateAction = (act: string) => {
    setAction(act);
    setTimeout(() => setAction(null), 300);
  };

  return (
    <div className="flex flex-col gap-4 w-full items-center">
      
      {/* Cam Selector (Pills) */}
      <div className="flex gap-2 w-full">
        {[1, 2, 3, 4].map(num => (
          <button 
            key={num}
            onClick={() => setActiveCam(num)}
            className={`flex-1 py-2 text-xs font-semibold rounded-full border transition-all active:scale-95 shadow-sm ${
              activeCam === num 
                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                : 'bg-zinc-100 dark:bg-zinc-800/80 border-zinc-200 dark:border-zinc-700/80 text-zinc-600 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-white'
            }`}
          >
            CAM 0{num}
          </button>
        ))}
      </div>

      <div className="flex gap-6 mt-3 items-center justify-center">
        
        {/* PTZ D-Pad */}
        <div className={`grid grid-cols-3 gap-2 transition-opacity duration-300 ${isPowerOn ? 'opacity-100' : 'opacity-40'}`}>
          <div />
          <button 
            onClick={() => simulateAction('UP')} 
            className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
              action === 'UP' 
                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
            }`} 
            disabled={!isPowerOn}
            title="Pan Up"
          >
            <ArrowUp size={18} />
          </button>
          <div />
          
          <button 
            onClick={() => simulateAction('LEFT')} 
            className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
              action === 'LEFT' 
                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
            }`} 
            disabled={!isPowerOn}
            title="Pan Left"
          >
            <ArrowLeft size={18} />
          </button>

          <button 
            onClick={() => setIsPowerOn(!isPowerOn)} 
            className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
              isPowerOn 
                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                : 'bg-red-500/10 text-red-500 border-red-500/30 hover:bg-red-500/20'
            }`}
            title={isPowerOn ? "Desconectar Cámara" : "Conectar Cámara"}
          >
            <Video size={18} />
          </button>

          <button 
            onClick={() => simulateAction('RIGHT')} 
            className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
              action === 'RIGHT' 
                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
            }`} 
            disabled={!isPowerOn}
            title="Pan Right"
          >
            <ArrowRight size={18} />
          </button>
          
          <div />
          <button 
            onClick={() => simulateAction('DOWN')} 
            className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
              action === 'DOWN' 
                ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
            }`} 
            disabled={!isPowerOn}
            title="Pan Down"
          >
            <ArrowDown size={18} />
          </button>
          <div />
        </div>

        {/* Zoom Controls */}
        <div className={`flex flex-col gap-2 transition-opacity duration-300 ${isPowerOn ? 'opacity-100' : 'opacity-40'}`}>
           <button 
             onClick={() => simulateAction('ZOOM_IN')} 
             className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
               action === 'ZOOM_IN' 
                 ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                 : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
             }`} 
             disabled={!isPowerOn}
             title="Zoom In"
           >
             <ZoomIn size={18} />
           </button>
           <button 
             onClick={() => simulateAction('ZOOM_OUT')} 
             className={`w-11 h-11 rounded-2xl border transition-all flex items-center justify-center active:scale-90 shadow-sm ${
               action === 'ZOOM_OUT' 
                 ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white' 
                 : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700 hover:bg-zinc-200 dark:hover:bg-zinc-700'
             }`} 
             disabled={!isPowerOn}
             title="Zoom Out"
           >
             <ZoomOut size={18} />
           </button>
        </div>
      </div>
      
      <div className="text-xs text-zinc-500 dark:text-zinc-400 mt-2 font-medium">
        {isPowerOn ? `Conectado a CAM 0${activeCam} — Protocolo PTZ Listo` : 'Cámara Desconectada'}
      </div>
    </div>
  );
}
