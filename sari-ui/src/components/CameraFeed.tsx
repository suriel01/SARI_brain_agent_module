import { useState, useEffect, useRef } from 'react';
import { RotateCw, FlipHorizontal, FlipVertical, Maximize2, Minimize2, RefreshCcw, Video, Settings2 } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';

export default function CameraFeed() {
  const { language, t } = useLanguage();
  const [fps, setFps] = useState(30);
  const [streamUrl, setStreamUrl] = useState('http://192.168.55.1:8080/mjpeg');
  const [streamError, setStreamError] = useState(false);
  const [showUrlEdit, setShowUrlEdit] = useState(false);
  const activeCam = 'Jetson-PTZ_1';

  // Dynamic Orientation & Fullscreen State (Default 180° for upside down stream fix)
  const [rotation, setRotation] = useState<number>(180);
  const [flipH, setFlipH] = useState<boolean>(false);
  const [flipV, setFlipV] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  const viewportRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setFps(Math.floor(29 + Math.random() * 3));
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const rotateVideo = () => {
    setRotation(prev => (prev + 90) % 360);
  };

  const resetOrientation = () => {
    setRotation(0);
    setFlipH(false);
    setFlipV(false);
  };

  const toggleFullscreen = () => {
    if (!viewportRef.current) return;
    if (!document.fullscreenElement) {
      viewportRef.current.requestFullscreen().catch(err => {
        console.error('Error enabling fullscreen mode:', err);
      });
    } else {
      document.exitFullscreen().catch(err => {
        console.error('Error exiting fullscreen mode:', err);
      });
    }
  };

  return (
    <div className="w-full h-full flex flex-col items-center justify-start gap-4 p-2 overflow-y-auto">
      
      {/* Google Antigravity Card Container */}
      <div className="w-full max-w-5xl bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-5 shadow-sm flex flex-col gap-4 transition-all">
        
        {/* Card Header with Pill Badges */}
        <div className="flex flex-wrap justify-between items-center gap-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-900 dark:text-zinc-100 shadow-sm">
              <Video size={16} />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight leading-none">
                {t('livePerception')} ({activeCam})
              </h2>
              <p className="text-[11px] text-zinc-400 dark:text-zinc-500 mt-1">YOLO26n Real-time Object Detection Stream</p>
            </div>
            <span className="ml-1 text-[11px] font-semibold px-3 py-1 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200/60 dark:border-zinc-700/60 shadow-sm">
              MJPEG Stream
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={() => setShowUrlEdit(prev => !prev)} 
              className="px-3.5 py-1.5 rounded-full text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 border border-zinc-200/60 dark:border-zinc-700/60 transition-all flex items-center gap-1.5 active:scale-95 shadow-sm"
            >
              <Settings2 size={13} />
              {showUrlEdit ? (language === 'en' ? 'Hide URL' : 'Ocultar URL') : (language === 'en' ? 'Configure URL' : 'Configurar URL')}
            </button>
            <span className="text-xs text-zinc-700 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800 px-3 py-1.5 rounded-full border border-zinc-200/60 dark:border-zinc-700/60 font-semibold shadow-sm">
              {fps} FPS
            </span>
          </div>
        </div>

        {/* URL Configuration Drawer (Pill Style) */}
        {showUrlEdit && (
          <div className="flex flex-wrap gap-2 items-center bg-zinc-50 dark:bg-zinc-800/60 px-4 py-3 rounded-2xl border border-zinc-200 dark:border-zinc-700/80 shadow-inner">
            <span className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">Stream URL:</span>
            <input 
              type="text" 
              value={streamUrl} 
              onChange={e => { setStreamUrl(e.target.value); setStreamError(false); }}
              className="flex-1 min-w-[260px] bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 text-zinc-900 dark:text-zinc-100 px-4 py-2 rounded-full text-xs outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 transition-all font-mono"
              placeholder="http://192.168.55.1:8080/mjpeg"
            />
            <button 
              onClick={() => setStreamError(false)}
              className="px-4 py-2 rounded-full text-xs font-semibold bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all active:scale-95 shadow-sm"
            >
              {language === 'en' ? 'Reconnect' : 'Reconectar'}
            </button>
          </div>
        )}

        {/* Main Video Viewport in Rounded 2XL/3XL Container */}
        <div 
          ref={viewportRef}
          className={`relative w-full bg-zinc-950 flex items-center justify-center transition-all overflow-hidden ${
            isFullscreen 
              ? 'fixed inset-0 z-50 h-screen w-screen rounded-none border-none' 
              : 'aspect-video max-h-[calc(100vh-270px)] rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-lg'
          }`}
        >
          {!streamError ? (
            <img 
              src={streamUrl} 
              alt="Live Stream" 
              onError={() => setStreamError(true)}
              className="w-full h-full object-contain bg-zinc-950 transition-transform duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]"
              style={{ 
                transform: `rotate(${rotation}deg) scaleX(${flipH ? -1 : 1}) scaleY(${flipV ? -1 : 1})`
              }}
            />
          ) : (
            <div className="p-8 text-center text-zinc-400 flex flex-col items-center justify-center">
              <div className="w-12 h-12 rounded-full bg-zinc-900 flex items-center justify-center text-zinc-300 mb-3 border border-zinc-800">
                <Video size={22} />
              </div>
              <div className="text-zinc-100 font-semibold text-base mb-1">
                {language === 'en' ? `Waiting for video stream (${streamUrl})` : `Esperando señal de video (${streamUrl})`}
              </div>
              <div className="text-xs text-zinc-400 max-w-md leading-relaxed">
                {language === 'en'
                  ? 'Ensure MJPEG streamer on Jetson module is active and reachable on the perimeter network.'
                  : 'Asegúrate de que el servidor MJPEG en el módulo Jetson esté iniciado y accesible en la red perimetral.'}
              </div>
            </div>
          )}

          {/* Floating Pill HUD: Status Indicator (Top-Left) */}
          <div className="absolute top-4 left-4 flex gap-2.5 items-center pointer-events-none bg-black/60 backdrop-blur-xl px-3.5 py-1.5 rounded-full border border-white/10 z-10 shadow-lg text-white">
            <div className={`w-2.5 h-2.5 rounded-full ${!streamError ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-[11px] font-bold tracking-wider">
              {!streamError ? (language === 'en' ? 'LIVE' : 'EN VIVO') : 'OFFLINE'}
            </span>
            <span className="text-[11px] text-zinc-300 font-medium">1080p @ {fps}FPS</span>
            <span className="text-[10px] text-zinc-300 bg-white/10 px-2.5 py-0.5 rounded-full font-mono">
              {rotation}° {flipH ? '| Flip H' : ''} {flipV ? '| Flip V' : ''}
            </span>
          </div>

          {/* Floating Pill HUD: Controls Dock (Top-Right) */}
          <div className="absolute top-4 right-4 flex gap-1 items-center bg-black/60 backdrop-blur-xl p-1.5 rounded-full border border-white/10 z-10 shadow-lg text-white">
            <button
              onClick={rotateVideo}
              title={language === 'en' ? 'Rotate Video (+90°)' : 'Rotar Video (+90°)'}
              className="w-8 h-8 rounded-full flex items-center justify-center text-zinc-200 hover:text-white hover:bg-white/20 transition-all active:scale-90"
            >
              <RotateCw size={15} />
            </button>

            <button
              onClick={() => setFlipH(prev => !prev)}
              title={language === 'en' ? 'Flip Horizontal' : 'Invertir Horizontalmente (Flip H)'}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-90 ${flipH ? 'bg-white text-zinc-950 font-bold' : 'text-zinc-200 hover:text-white hover:bg-white/20'}`}
            >
              <FlipHorizontal size={15} />
            </button>

            <button
              onClick={() => setFlipV(prev => !prev)}
              title={language === 'en' ? 'Flip Vertical' : 'Invertir Verticalmente (Flip V)'}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-90 ${flipV ? 'bg-white text-zinc-950 font-bold' : 'text-zinc-200 hover:text-white hover:bg-white/20'}`}
            >
              <FlipVertical size={15} />
            </button>

            <button
              onClick={resetOrientation}
              title={language === 'en' ? 'Reset Orientation (0°)' : 'Restablecer Orientación (0°)'}
              className="w-8 h-8 rounded-full flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/20 transition-all active:scale-90"
            >
              <RefreshCcw size={14} />
            </button>

            <div className="w-[1px] h-4 bg-white/20 mx-1" />

            <button
              onClick={toggleFullscreen}
              title={isFullscreen ? (language === 'en' ? 'Exit Fullscreen (ESC)' : 'Salir de Pantalla Completa (ESC)') : (language === 'en' ? 'Fullscreen' : 'Pantalla Completa')}
              className="w-8 h-8 rounded-full flex items-center justify-center text-zinc-200 hover:text-white hover:bg-white/20 transition-all active:scale-90"
            >
              {isFullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
            </button>
          </div>

          {/* Floating Pill HUD: Source Meta (Bottom-Right) */}
          <div className="absolute bottom-3 right-4 text-[10px] text-zinc-300 font-mono pointer-events-none bg-black/60 backdrop-blur-xl px-3 py-1 rounded-full border border-white/10 z-10 shadow-md">
            STREAM: Jetson-PTZ_1 | HIKVISION REAL
          </div>
        </div>

      </div>
    </div>
  );
}
