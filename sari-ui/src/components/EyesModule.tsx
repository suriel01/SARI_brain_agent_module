import { useState, useEffect, useRef } from 'react';
import { 
  Video, Eye, Plus, RotateCw, FlipHorizontal, FlipVertical, 
  Maximize2, Minimize2, RefreshCcw, Settings2, Cpu, 
  Activity, Thermometer, HardDrive, ShieldAlert, Download, 
  Play, Circle, Trash2, Camera, Lock, CheckCircle2, AlertCircle, X,
  ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Focus, ZoomIn, Target
} from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import ConnectEyeModal from './ConnectEyeModal';
import { apiFetch } from '../api';
import type { Permissions } from '../permissions';

interface EyeNode {
  id: number;
  node_id: string;
  name: string;
  ip: string;
  stream_url: string;
  yolo_threshold: number;
  is_active: boolean;
  is_online?: boolean;
  fps?: number;
  ram_used_gb?: number;
  ram_total_gb?: number;
  cpu_load_pct?: number;
  gpu_load_pct?: number;
  temp_c?: number;
  link_status?: string;
  tracking_enabled?: boolean;
}

interface RecordingItem {
  id: number;
  timestamp: string;
  content: string;
  snapshot: string;
  thread_id: number;
}

interface EyesModuleProps {
  token: string;
  permissions?: Permissions;
  requestPin?: (actionName: string, callback: (pin: string) => void) => void;
  initialSelectedNodeId?: string | null;
}

export default function EyesModule({ token, permissions, requestPin: _requestPin, initialSelectedNodeId }: EyesModuleProps) {
  const { language, t } = useLanguage();

  const [eyes, setEyes] = useState<EyeNode[]>([]);
  const [selectedEyeId, setSelectedEyeId] = useState<string>(initialSelectedNodeId || 'Jetson-PTZ_1');

  const syncedEyeIdRef = useRef<string | null>(null);
  useEffect(() => {
    if (syncedEyeIdRef.current !== selectedEyeId && eyes.length > 0) {
      const active = eyes.find(e => e.node_id === selectedEyeId);
      if (active && active.tracking_enabled !== undefined) {
        setTrackingEnabled(active.tracking_enabled);
      }
      syncedEyeIdRef.current = selectedEyeId;
    }
  }, [selectedEyeId, eyes]);

  useEffect(() => {
    if (initialSelectedNodeId) {
      setSelectedEyeId(initialSelectedNodeId);
    }
  }, [initialSelectedNodeId]);
  const [recordings, setRecordings] = useState<RecordingItem[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Active Stream State
  const [streamError, setStreamError] = useState(false);
  const [showUrlEdit] = useState(false);
  const [customStreamUrl, setCustomStreamUrl] = useState('');

  // Node Configuration Modal State
  const [isConfigModalOpen, setIsConfigModalOpen] = useState(false);
  const [editName, setEditName] = useState('');
  const [editIp, setEditIp] = useState('');
  const [editStreamUrl, setEditStreamUrl] = useState('');
  const [editThreshold, setEditThreshold] = useState(0.70);
  const [editPin, setEditPin] = useState('');
  const [configSaving, setConfigSaving] = useState(false);
  const [configSuccess, setConfigSuccess] = useState('');
  const [configError, setConfigError] = useState('');
  const [isCapturingSnapshot, setIsCapturingSnapshot] = useState(false);

  // Video Orientation & Fullscreen
  const [rotation, setRotation] = useState<number>(180);
  const [flipH, setFlipH] = useState<boolean>(false);
  const [flipV, setFlipV] = useState<boolean>(false);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Live Recording (MediaRecorder on Stream)
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<any>(null);

  // Snapshot Preview Modal
  const [previewSnapshot, setPreviewSnapshot] = useState<string | null>(null);

  // Human Auto-Tracking & Manual PTZ State
  const [trackingEnabled, setTrackingEnabled] = useState<boolean>(true);
  const [ptzAction, setPtzAction] = useState<string | null>(null);
  const [ptzFeedback, setPtzFeedback] = useState<string | null>(null);

  // Zoom Level (Percentage)
  const [zoomLevel, setZoomLevel] = useState<number>(100);

  // Click-and-Drag Pan/Tilt State (no ghost drag)
  const isDraggingRef = useRef<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const lastDragSentRef = useRef<number>(0);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const holdIntervalRef = useRef<any>(null);

  const viewportRef = useRef<HTMLDivElement>(null);
  const streamImgRef = useRef<HTMLImageElement>(null);

  const fetchEyes = async () => {
    try {
      const res = await apiFetch('/eyes', token);
      if (res.ok) {
        const data = await res.json();
        setEyes(data);
        if (data.length > 0 && !data.some((e: EyeNode) => e.node_id === selectedEyeId)) {
          setSelectedEyeId(data[0].node_id);
        }
      }
    } catch (err) {
      console.error('Error fetching eyes:', err);
    }
  };

  const fetchRecordings = async () => {
    try {
      const res = await apiFetch('/eyes/recordings', token);
      if (res.ok) {
        const data = await res.json();
        // Filter out any dummy mock SVG or empty recordings
        const valid = data.filter((r: RecordingItem) => 
          r.snapshot && r.snapshot.length > 500 && !r.snapshot.includes('<svg')
        );
        setRecordings(valid);
      }
    } catch (err) {
      console.error('Error fetching recordings:', err);
    }
  };

  const openConfigModal = () => {
    setEditName(selectedEye.name || '');
    setEditIp(selectedEye.ip || '');
    setEditStreamUrl(selectedEye.stream_url || '');
    setEditThreshold(selectedEye.yolo_threshold || 0.70);
    setEditPin('');
    setConfigSuccess('');
    setConfigError('');
    setIsConfigModalOpen(true);
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (permissions && !permissions.canControlHardware) {
      setConfigError(language === 'en' ? 'Unauthorized: clearance level insufficient' : 'Acción no autorizada para su nivel de acceso');
      return;
    }
    setConfigSaving(true);
    setConfigError('');
    setConfigSuccess('');

    try {
      const res = await apiFetch(`/eyes/${selectedEye.node_id}`, token, {
        method: 'PUT',
        body: JSON.stringify({
          name: editName,
          ip: editIp,
          stream_url: editStreamUrl,
          yolo_threshold: editThreshold,
          pin: editPin || undefined
        })
      });

      if (res.ok) {
        setConfigSuccess(language === 'en' ? 'Configuration saved and synchronized!' : '¡Configuración guardada y sincronizada!');
        fetchEyes();
        setTimeout(() => {
          setIsConfigModalOpen(false);
          setConfigSuccess('');
        }, 1200);
      } else {
        const data = await res.json();
        setConfigError(data.detail || (language === 'en' ? 'Error saving configuration' : 'Error al guardar configuración'));
      }
    } catch (err: any) {
      setConfigError(err.message || 'Error de conexión');
    } finally {
      setConfigSaving(false);
    }
  };

  const handleTakeManualSnapshot = async () => {
    setIsCapturingSnapshot(true);
    try {
      await apiFetch('/alerts/event', token, {
        method: 'POST',
        body: JSON.stringify({
          module_name: selectedEye.node_id,
          camara_id: selectedEye.node_id,
          event_type: 'manual_snapshot',
          severity: 'low',
          message: `Captura manual de evidencia solicitada desde Módulo Ojos`,
          confidence: 0.99
        })
      });
      fetchRecordings();
    } catch (err) {
      console.error('Error taking snapshot:', err);
    } finally {
      setIsCapturingSnapshot(false);
    }
  };

  useEffect(() => {
    fetchEyes();
    fetchRecordings();
    const interval = setInterval(() => {
      fetchEyes();
      fetchRecordings();
    }, 3000);
    return () => clearInterval(interval);
  }, [token]);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const selectedEye = eyes.find(e => e.node_id === selectedEyeId) || eyes[0] || {
    node_id: 'Jetson-PTZ_1',
    name: 'Jetson Orin Nano (PTZ 1)',
    ip: '192.168.55.1',
    stream_url: 'http://192.168.55.1:8080/mjpeg',
    yolo_threshold: 0.70,
    is_active: true,
    is_online: true,
    fps: 30.0,
    ram_used_gb: 3.8,
    ram_total_gb: 7.44,
    cpu_load_pct: 35.0,
    gpu_load_pct: 55.0,
    temp_c: 52.0,
    link_status: 'USB Direct (1Gbps)'
  };

  const currentStreamUrl = customStreamUrl || selectedEye.stream_url || 'http://192.168.55.1:8080/mjpeg';

  // Rotation controls
  const rotateVideo = () => setRotation(prev => (prev + 90) % 360);
  const resetOrientation = () => {
    setRotation(0);
    setFlipH(false);
    setFlipV(false);
  };

  const toggleFullscreen = () => {
    if (!viewportRef.current) return;
    if (!document.fullscreenElement) {
      viewportRef.current.requestFullscreen().catch(console.error);
    } else {
      document.exitFullscreen().catch(console.error);
    }
  };

  // Recording Engine
  const startRecording = () => {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = 1280;
      canvas.height = 720;
      const ctx = canvas.getContext('2d');
      if (!ctx || !streamImgRef.current) return;

      const stream = canvas.captureStream(25);
      const recorder = new MediaRecorder(stream, { mimeType: 'video/webm' });
      recordedChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          recordedChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `sari_clip_${selectedEye.node_id}_${new Date().toISOString().replace(/[:.]/g, '-')}.webm`;
        document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 100);
      };

      recorder.start(500);
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordingSeconds(0);

      const drawLoop = setInterval(() => {
        if (streamImgRef.current && ctx) {
          try {
            ctx.drawImage(streamImgRef.current, 0, 0, canvas.width, canvas.height);
          } catch (e) {
            // ignore cross-origin draw issues if any
          }
        }
      }, 40);

      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);

      recorder.addEventListener('stop', () => {
        clearInterval(drawLoop);
      }, { once: true });

    } catch (err) {
      console.warn('MediaRecorder on canvas fallback, initiating clip timer:', err);
      setIsRecording(true);
      setRecordingSeconds(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    clearInterval(recordingTimerRef.current);
    setIsRecording(false);
  };

  const handleDeleteEye = async (nodeId: string) => {
    if (!window.confirm(language === 'en' ? `Delete eye node ${nodeId}?` : `¿Eliminar el módulo ojo ${nodeId}?`)) return;
    try {
      const res = await apiFetch(`/eyes/${nodeId}`, token, { method: 'DELETE' });
      if (res.ok) {
        fetchEyes();
      }
    } catch (err) {
      console.error('Error deleting eye:', err);
    }
  };

  const handleToggleTracking = async () => {
    const nextState = !trackingEnabled;
    setTrackingEnabled(nextState);
    setEyes(prev => prev.map(e => e.node_id === selectedEye.node_id ? { ...e, tracking_enabled: nextState } : e));
    try {
      await apiFetch(`/eyes/${selectedEye.node_id}/tracking`, token, {
        method: 'POST',
        body: JSON.stringify({ enabled: nextState })
      });
    } catch (err) {
      console.error('Error toggling tracking:', err);
    }
  };

  const handleSendPtz = async (action: string, panDelta = 0, tiltDelta = 0, zoomDelta = 0) => {
    setPtzAction(action);
    const label = action === 'drag' 
      ? `PAN: ${panDelta > 0 ? '+' : ''}${Math.round(panDelta)} | TILT: ${tiltDelta > 0 ? '+' : ''}${Math.round(tiltDelta)}` 
      : action.toUpperCase();
    setPtzFeedback(`PTZ: ${label}`);
    
    setTimeout(() => setPtzAction(null), 300);
    setTimeout(() => setPtzFeedback(null), 1200);

    try {
      await apiFetch(`/eyes/${selectedEye.node_id}/ptz`, token, {
        method: 'POST',
        body: JSON.stringify({
          action,
          pan_delta: panDelta,
          tilt_delta: tiltDelta,
          zoom_delta: zoomDelta
        })
      });
    } catch (err) {
      console.error('Error sending PTZ command:', err);
    }
  };

  // D-Pad Continuous Hold while pressing buttons
  const startContinuousHold = (action: string, pan: number, tilt: number, zoom = 0) => {
    handleSendPtz(action, pan, tilt, zoom);
    if (holdIntervalRef.current) clearInterval(holdIntervalRef.current);
    holdIntervalRef.current = setInterval(() => {
      handleSendPtz(action, pan, tilt, zoom);
    }, 140);
  };

  const stopContinuousHold = () => {
    if (holdIntervalRef.current) {
      clearInterval(holdIntervalRef.current);
      holdIntervalRef.current = null;
    }
  };

  // Click-and-Drag Pan/Tilt on Viewport (with native drag prevention)
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('button, input, .ptz-overlay-control')) return;
    e.preventDefault();
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX, y: e.clientY };
    setIsDragging(true);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDraggingRef.current) return;
    e.preventDefault();
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    const dist = Math.hypot(dx, dy);

    if (dist >= 6) {
      const now = Date.now();
      if (now - lastDragSentRef.current > 80) {
        const panDelta = Math.round(dx * 0.45);
        const tiltDelta = Math.round(-dy * 0.45);
        handleSendPtz('drag', panDelta, tiltDelta);
        lastDragSentRef.current = now;
        dragStartRef.current = { x: e.clientX, y: e.clientY };
      }
    }
  };

  const handleMouseUp = () => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      setIsDragging(false);
    }
  };

  const formatSeconds = (sec: number) => {
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  return (
    <div className="w-full h-full flex flex-col gap-4 overflow-y-auto p-1 custom-scrollbar">
      
      {/* Top Bar: Eye Nodes Carousel / Selector + Connect Eye Button */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white dark:bg-zinc-900/90 border border-zinc-200/80 dark:border-zinc-800/80 p-3 rounded-2xl shadow-sm">
        <div className="flex items-center gap-2 overflow-x-auto py-1 max-w-[calc(100%-170px)]">
          <div className="flex items-center gap-1.5 text-xs font-bold text-zinc-900 dark:text-zinc-100 uppercase tracking-wider px-2 border-r border-zinc-200 dark:border-zinc-800">
            <Eye size={14} className="text-emerald-500" />
            <span>{t('eyes')}</span>
            <span className="ml-1 text-[11px] px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 font-mono">
              {eyes.length}
            </span>
          </div>

          {eyes.map(eye => {
            const isSelected = eye.node_id === selectedEyeId;
            return (
              <button
                key={eye.node_id}
                onClick={() => {
                  setSelectedEyeId(eye.node_id);
                  setCustomStreamUrl('');
                  setStreamError(false);
                }}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-semibold transition-all shrink-0 active:scale-95 shadow-sm border ${
                  isSelected 
                    ? 'bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 border-zinc-900 dark:border-white shadow-md' 
                    : 'bg-zinc-100 dark:bg-zinc-800/80 text-zinc-700 dark:text-zinc-300 border-zinc-200/80 dark:border-zinc-700/80 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                }`}
              >
                <div className={`w-2 h-2 rounded-full ${eye.is_online ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-400'}`} />
                <span>{eye.name}</span>
                <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${isSelected ? 'bg-white/20 dark:bg-zinc-900/20' : 'bg-zinc-200/60 dark:bg-zinc-700/60'}`}>
                  {eye.is_online ? `${Math.round(eye.fps || 30)} FPS` : 'STANDBY'}
                </span>
              </button>
            );
          })}
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 rounded-full text-xs font-bold bg-emerald-500 hover:bg-emerald-600 text-white shadow-sm flex items-center gap-1.5 transition-all active:scale-95 shrink-0"
        >
          <Plus size={14} />
          <span>{t('connectNewEye')}</span>
        </button>
      </div>

      {/* Main Section: Left (Video Stream) & Right (Tactical Telemetry Card) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        
        {/* Left Col (2 cols): Stream Viewport Card */}
        <div className="lg:col-span-2 bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-4 shadow-sm flex flex-col gap-3">
          
          {/* Header of Active Eye */}
          <div className="flex flex-wrap justify-between items-center gap-2">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-900 dark:text-white">
                <Video size={16} />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
                  <span>{selectedEye.name}</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-400">
                    {selectedEye.node_id}
                  </span>
                </h3>
                <p className="text-[11px] text-zinc-400 dark:text-zinc-500">
                  {selectedEye.ip} • YOLO26n Tactical Detection Stream
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">

              <button
                onClick={handleTakeManualSnapshot}
                disabled={isCapturingSnapshot}
                title={language === 'en' ? 'Capture snapshot from camera' : 'Tomar captura de la cámara'}
                className="px-3 py-1.5 rounded-full text-xs font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 hover:bg-zinc-200 dark:hover:bg-zinc-700 border border-zinc-200/60 dark:border-zinc-700/60 flex items-center gap-1.5 transition-all shadow-sm disabled:opacity-50"
              >
                <Camera size={13} />
                <span>{isCapturingSnapshot ? 'Capturando...' : (language === 'en' ? 'Snapshot' : 'Capturar')}</span>
              </button>

              <button
                onClick={openConfigModal}
                className="px-3 py-1.5 rounded-full text-xs font-semibold bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 hover:bg-zinc-800 dark:hover:bg-zinc-200 flex items-center gap-1.5 transition-all shadow-sm active:scale-95"
              >
                <Settings2 size={13} />
                <span>{language === 'en' ? 'Configure Jetson' : 'Configurar Jetson'}</span>
              </button>
            </div>
          </div>

          {/* Quick URL Config Drawer */}
          {showUrlEdit && (
            <div className="flex gap-2 items-center bg-zinc-50 dark:bg-zinc-800/60 p-2.5 rounded-2xl border border-zinc-200 dark:border-zinc-700 text-xs">
              <span className="text-zinc-500 font-medium">URL:</span>
              <input
                type="text"
                value={customStreamUrl || selectedEye.stream_url}
                onChange={e => { setCustomStreamUrl(e.target.value); setStreamError(false); }}
                className="flex-1 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 px-3 py-1.5 rounded-full text-xs font-mono outline-none text-zinc-900 dark:text-zinc-100"
                placeholder="http://192.168.1.75:8080/mjpeg"
              />
              <button
                onClick={() => setStreamError(false)}
                className="px-3.5 py-1.5 rounded-full font-semibold bg-zinc-900 text-white dark:bg-white dark:text-zinc-950 text-xs"
              >
                Reconectar
              </button>
            </div>
          )}

          {/* Viewport Container with Click & Drag PTZ Support */}
          <div
            ref={viewportRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onTouchStart={(e) => {
              if ((e.target as HTMLElement).closest('button, input, .ptz-overlay-control')) return;
              const touch = e.touches[0];
              isDraggingRef.current = true;
              dragStartRef.current = { x: touch.clientX, y: touch.clientY };
              setIsDragging(true);
            }}
            onTouchMove={(e) => {
              if (!isDraggingRef.current) return;
              const touch = e.touches[0];
              const dx = touch.clientX - dragStartRef.current.x;
              const dy = touch.clientY - dragStartRef.current.y;
              const dist = Math.hypot(dx, dy);
              if (dist >= 6) {
                const now = Date.now();
                if (now - lastDragSentRef.current > 80) {
                  const panDelta = Math.round(dx * 0.45);
                  const tiltDelta = Math.round(-dy * 0.45);
                  handleSendPtz('drag', panDelta, tiltDelta);
                  lastDragSentRef.current = now;
                  dragStartRef.current = { x: touch.clientX, y: touch.clientY };
                }
              }
            }}
            onTouchEnd={() => {
              isDraggingRef.current = false;
              setIsDragging(false);
            }}
            draggable={false}
            onDragStart={(e) => e.preventDefault()}
            className={`relative w-full bg-zinc-950 flex items-center justify-center transition-all overflow-hidden ${isDragging ? "cursor-grabbing" : "cursor-grab"} select-none ${
              isFullscreen 
                ? 'fixed inset-0 z-50 h-screen w-screen rounded-none' 
                : 'aspect-video rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-inner'
            }`}
          >
            {/* On-Screen PTZ Feedback Badge */}
            {ptzFeedback && (
              <div className="absolute top-14 left-1/2 -translate-x-1/2 z-20 pointer-events-none bg-zinc-900/90 text-white border border-zinc-700 px-3 py-1 rounded-full text-[11px] font-mono shadow-xl flex items-center gap-1.5 animate-[fadeIn_0.2s_ease-out]">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                <span>{ptzFeedback}</span>
              </div>
            )}

            {/* Bottom Left Drag-to-Pan Hint */}
            <div className="absolute bottom-3 left-3 text-[10px] text-zinc-300 font-mono pointer-events-none bg-zinc-950/90 px-3 py-1 rounded-full border border-zinc-700/80 z-10 shadow-md flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span>{language === 'en' ? 'Click & drag video to pan/tilt' : 'Clic y arrastrar video para mover cámara'}</span>
            </div>

            {/* Gamepad D-Pad Cruceta & Zoom Controls Overlay (Inside Video & Fullscreen) */}
            <div className="absolute bottom-3 right-3 z-20 ptz-overlay-control flex flex-col items-center gap-1.5 bg-zinc-950 border-2 border-zinc-700/90 shadow-2xl p-3 rounded-2xl select-none">
              
              {/* Zoom Bar with Percentage */}
              <div className="flex flex-col gap-1 w-full pb-2 mb-1 border-b border-zinc-800 text-white">
                <div className="flex items-center justify-between text-[10px] font-mono px-0.5">
                  <span className="flex items-center gap-1 text-zinc-300 font-bold">
                    <ZoomIn size={11} className="text-emerald-400" />
                    <span>ZOOM</span>
                  </span>
                  <span className="text-emerald-400 font-bold bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-700/80 text-[10px]">
                    {zoomLevel}%
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = Math.max(100, zoomLevel - 20);
                      setZoomLevel(next);
                      handleSendPtz('zoom', 0, 0, (next - 100) / 100);
                    }}
                    title="Reducir Zoom"
                    className="w-5 h-5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 flex items-center justify-center text-xs font-bold active:scale-95 transition-all border border-zinc-700"
                  >
                    -
                  </button>
                  <input
                    type="range"
                    min="100"
                    max="400"
                    step="5"
                    value={zoomLevel}
                    onChange={(e) => {
                      const val = parseInt(e.target.value);
                      setZoomLevel(val);
                      handleSendPtz('zoom', 0, 0, (val - 100) / 100);
                    }}
                    className="w-24 accent-emerald-500 h-1.5 bg-zinc-800 rounded-lg cursor-pointer"
                  />
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      const next = Math.min(400, zoomLevel + 20);
                      setZoomLevel(next);
                      handleSendPtz('zoom', 0, 0, (next - 100) / 100);
                    }}
                    title="Aumentar Zoom"
                    className="w-5 h-5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 flex items-center justify-center text-xs font-bold active:scale-95 transition-all border border-zinc-700"
                  >
                    +
                  </button>
                </div>
              </div>

              {/* Real Gamepad Cruceta (Plus Shape) - Solid Background & Continuous Hold */}
              <div className="relative w-28 h-28 flex items-center justify-center">
                
                {/* Up Wing */}
                <button
                  onMouseDown={(e) => { e.stopPropagation(); startContinuousHold('up', 0, 10); }}
                  onMouseUp={stopContinuousHold}
                  onMouseLeave={stopContinuousHold}
                  onTouchStart={(e) => { e.stopPropagation(); startContinuousHold('up', 0, 10); }}
                  onTouchEnd={stopContinuousHold}
                  onTouchCancel={stopContinuousHold}
                  title="Arriba / Tilt Up (Mantener presionado)"
                  className={`absolute top-0 w-9 h-10 rounded-t-xl flex items-center justify-center transition-all active:scale-95 border border-zinc-700 shadow-md ${
                    ptzAction === 'up'
                      ? 'bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.5)]'
                      : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                  }`}
                >
                  <ArrowUp size={16} />
                </button>

                {/* Left Wing */}
                <button
                  onMouseDown={(e) => { e.stopPropagation(); startContinuousHold('left', -10, 0); }}
                  onMouseUp={stopContinuousHold}
                  onMouseLeave={stopContinuousHold}
                  onTouchStart={(e) => { e.stopPropagation(); startContinuousHold('left', -10, 0); }}
                  onTouchEnd={stopContinuousHold}
                  onTouchCancel={stopContinuousHold}
                  title="Izquierda / Pan Left (Mantener presionado)"
                  className={`absolute left-0 w-10 h-9 rounded-l-xl flex items-center justify-center transition-all active:scale-95 border border-zinc-700 shadow-md ${
                    ptzAction === 'left'
                      ? 'bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.5)]'
                      : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                  }`}
                >
                  <ArrowLeft size={16} />
                </button>

                {/* Center Button (Reset / Center) */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleSendPtz('center'); }}
                  title="Recentrar Posición"
                  className={`w-9 h-9 z-10 rounded-lg flex items-center justify-center transition-all active:scale-90 border border-zinc-700 shadow-inner ${
                    ptzAction === 'center'
                      ? 'bg-emerald-500 text-white'
                      : 'bg-zinc-900 text-zinc-400 hover:text-white hover:bg-zinc-800'
                  }`}
                >
                  <Focus size={14} />
                </button>

                {/* Right Wing */}
                <button
                  onMouseDown={(e) => { e.stopPropagation(); startContinuousHold('right', 10, 0); }}
                  onMouseUp={stopContinuousHold}
                  onMouseLeave={stopContinuousHold}
                  onTouchStart={(e) => { e.stopPropagation(); startContinuousHold('right', 10, 0); }}
                  onTouchEnd={stopContinuousHold}
                  onTouchCancel={stopContinuousHold}
                  title="Derecha / Pan Right (Mantener presionado)"
                  className={`absolute right-0 w-10 h-9 rounded-r-xl flex items-center justify-center transition-all active:scale-95 border border-zinc-700 shadow-md ${
                    ptzAction === 'right'
                      ? 'bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.5)]'
                      : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                  }`}
                >
                  <ArrowRight size={16} />
                </button>

                {/* Down Wing */}
                <button
                  onMouseDown={(e) => { e.stopPropagation(); startContinuousHold('down', 0, -10); }}
                  onMouseUp={stopContinuousHold}
                  onMouseLeave={stopContinuousHold}
                  onTouchStart={(e) => { e.stopPropagation(); startContinuousHold('down', 0, -10); }}
                  onTouchEnd={stopContinuousHold}
                  onTouchCancel={stopContinuousHold}
                  title="Abajo / Tilt Down (Mantener presionado)"
                  className={`absolute bottom-0 w-9 h-10 rounded-b-xl flex items-center justify-center transition-all active:scale-95 border border-zinc-700 shadow-md ${
                    ptzAction === 'down'
                      ? 'bg-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.5)]'
                      : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200'
                  }`}
                >
                  <ArrowDown size={16} />
                </button>
              </div>
            </div>
            {!streamError ? (
              <img
                ref={streamImgRef}
                src={currentStreamUrl}
                alt="Live Stream"
                draggable={false}
                onDragStart={(e) => e.preventDefault()}
                onError={() => setStreamError(true)}
                crossOrigin="anonymous"
                className="w-full h-full object-contain bg-zinc-950 transition-transform duration-300 pointer-events-none select-none"
                style={{
                  transform: `scale(${zoomLevel / 100}) rotate(${rotation}deg) scaleX(${flipH ? -1 : 1}) scaleY(${flipV ? -1 : 1})`
                }}
              />
            ) : (
              <div className="p-8 text-center text-zinc-400 flex flex-col items-center justify-center">
                <div className="w-12 h-12 rounded-full bg-zinc-900 flex items-center justify-center text-zinc-300 mb-3 border border-zinc-800">
                  <Video size={22} />
                </div>
                <div className="text-zinc-100 font-semibold text-sm mb-1">
                  {language === 'en' ? `Signal lost (${currentStreamUrl})` : `Señal no disponible (${currentStreamUrl})`}
                </div>
                <div className="text-xs text-zinc-400 max-w-sm">
                  {language === 'en'
                    ? 'Verify that the Jetson streamer daemon is online and transmitting.'
                    : 'Verifica que el daemon streamer en la Jetson esté iniciado y transmitiendo.'}
                </div>
              </div>
            )}

            {/* Floating Top-Left HUD (Pill) */}
            <div className="absolute top-3 left-3 flex gap-2 items-center pointer-events-none bg-black/65 backdrop-blur-xl px-3 py-1.5 rounded-full border border-white/10 z-10 shadow-lg text-white">
              <div className={`w-2 h-2 rounded-full ${!streamError ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-[10px] font-bold tracking-wider">
                {!streamError ? (language === 'en' ? 'LIVE' : 'EN VIVO') : 'OFFLINE'}
              </span>
              <span className="text-[10px] text-zinc-300 font-mono">
                {selectedEye.fps || 30} FPS
              </span>
              <span className="text-[9px] text-zinc-300 bg-white/10 px-2 py-0.5 rounded-full font-mono">
                {rotation}° {flipH ? '| Flip H' : ''} {flipV ? '| Flip V' : ''}
              </span>
            </div>

            {/* Floating Top-Right Controls HUD (Pill Dock) */}
            <div className="absolute top-3 right-3 flex gap-1.5 items-center bg-black/65 backdrop-blur-xl p-1.5 rounded-full border border-white/10 z-20 shadow-lg text-white ptz-overlay-control">
              
              {/* Human Auto-Tracking Button (Inside Viewport / Fullscreen) */}
              <button
                onClick={handleToggleTracking}
                title={trackingEnabled ? (language === 'en' ? 'Disable Human Auto-Tracking' : 'Desactivar Seguimiento de Humanos') : (language === 'en' ? 'Enable Human Auto-Tracking' : 'Activar Seguimiento de Humanos')}
                className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95 ${
                  trackingEnabled 
                    ? 'bg-emerald-500 text-white shadow-[0_0_12px_rgba(16,185,129,0.4)] animate-pulse' 
                    : 'bg-white/15 hover:bg-white/25 text-zinc-300'
                }`}
              >
                <Target size={11} className={trackingEnabled ? 'animate-pulse' : ''} />
                <span>{trackingEnabled ? (language === 'en' ? 'TRACKING: ON' : 'SEGUIMIENTO: ON') : (language === 'en' ? 'TRACKING: OFF' : 'SEGUIMIENTO: OFF')}</span>
              </button>

              <div className="w-px h-4 bg-white/20 mx-0.5" />

              {/* Interactive Live REC Button */}
              <button
                onClick={isRecording ? stopRecording : startRecording}
                title={isRecording ? t('stopRec') : t('startRec')}
                className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1.5 transition-all shadow-sm active:scale-95 ${
                  isRecording 
                    ? 'bg-red-600 text-white animate-pulse' 
                    : 'bg-white/15 hover:bg-red-500/80 text-zinc-200 hover:text-white'
                }`}
              >
                <Circle size={10} className={isRecording ? 'fill-white text-white' : 'fill-red-500 text-red-500'} />
                <span>{isRecording ? `REC ${formatSeconds(recordingSeconds)}` : 'REC'}</span>
              </button>

              <div className="w-px h-4 bg-white/20 mx-0.5" />

              <button
                onClick={rotateVideo}
                title={language === 'en' ? 'Rotate (+90°)' : 'Rotar (+90°)'}
                className="w-7 h-7 rounded-full flex items-center justify-center text-zinc-200 hover:text-white hover:bg-white/20 transition-all"
              >
                <RotateCw size={13} />
              </button>

              <button
                onClick={() => setFlipH(prev => !prev)}
                title="Invertir Horizontalmente"
                className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${flipH ? 'bg-white text-zinc-950 font-bold' : 'text-zinc-200 hover:text-white hover:bg-white/20'}`}
              >
                <FlipHorizontal size={13} />
              </button>

              <button
                onClick={() => setFlipV(prev => !prev)}
                title="Invertir Verticalmente"
                className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${flipV ? 'bg-white text-zinc-950 font-bold' : 'text-zinc-200 hover:text-white hover:bg-white/20'}`}
              >
                <FlipVertical size={13} />
              </button>

              <button
                onClick={resetOrientation}
                title="Restablecer"
                className="w-7 h-7 rounded-full flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/20 transition-all"
              >
                <RefreshCcw size={12} />
              </button>

              <div className="w-px h-4 bg-white/20 mx-0.5" />

              <button
                onClick={toggleFullscreen}
                title={isFullscreen ? 'Salir de Pantalla Completa' : 'Pantalla Completa'}
                className="w-7 h-7 rounded-full flex items-center justify-center text-zinc-200 hover:text-white hover:bg-white/20 transition-all"
              >
                {isFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              </button>
            </div>


          </div>



        </div>

        {/* Right Col (1 col): Selected Eye Telemetry Card */}
        <div className="bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-5 shadow-sm flex flex-col gap-4">
          
          <div className="flex items-center justify-between pb-3 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                <Activity size={15} />
              </div>
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-900 dark:text-zinc-100">
                  {t('systemTelemetry')}
                </h4>
                <p className="text-[10px] text-zinc-400 font-mono">{selectedEye.node_id}</p>
              </div>
            </div>

            <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${
              selectedEye.is_online 
                ? 'bg-emerald-500/15 text-emerald-500 border border-emerald-500/30' 
                : 'bg-zinc-500/15 text-zinc-400 border border-zinc-500/30'
            }`}>
              {selectedEye.is_online ? 'ONLINE (1080p)' : 'STANDBY'}
            </span>
          </div>

          {/* Metric 1: NPU / GPU Load */}
          <div className="flex flex-col gap-1.5 p-3 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-700/60">
            <div className="flex justify-between items-center text-xs">
              <span className="text-zinc-500 dark:text-zinc-400 font-medium flex items-center gap-1.5">
                <Cpu size={13} /> {t('npuLoad')}
              </span>
              <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">
                {selectedEye.gpu_load_pct !== undefined ? `${Math.round(selectedEye.gpu_load_pct)}%` : '58%'}
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
              <div 
                className="h-full bg-emerald-500 rounded-full transition-all duration-500" 
                style={{ width: `${Math.min(100, selectedEye.gpu_load_pct || 58)}%` }}
              />
            </div>
          </div>

          {/* Metric 2: Jetson RAM */}
          <div className="flex flex-col gap-1.5 p-3 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-700/60">
            <div className="flex justify-between items-center text-xs">
              <span className="text-zinc-500 dark:text-zinc-400 font-medium flex items-center gap-1.5">
                <HardDrive size={13} /> {t('jetsonRam')}
              </span>
              <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">
                {selectedEye.ram_used_gb || 3.77} / {selectedEye.ram_total_gb || 7.44} GB ({Math.round(((selectedEye.ram_used_gb || 3.77)/(selectedEye.ram_total_gb || 7.44))*100)}%)
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
              <div 
                className="h-full bg-blue-500 rounded-full transition-all duration-500" 
                style={{ width: `${Math.min(100, Math.round(((selectedEye.ram_used_gb || 3.77)/(selectedEye.ram_total_gb || 7.44))*100))}%` }}
              />
            </div>
          </div>

          {/* Metric 3: Core Temp & CPU load */}
          <div className="grid grid-cols-2 gap-2.5">
            <div className="p-3 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-700/60 flex flex-col gap-1">
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400 font-medium flex items-center gap-1">
                <Thermometer size={12} /> {t('coreTemp')}
              </span>
              <span className={`text-base font-mono font-bold ${
                (selectedEye.temp_c || 52) > 70 ? 'text-red-400' : (selectedEye.temp_c || 52) > 60 ? 'text-amber-400' : 'text-emerald-400'
              }`}>
                {selectedEye.temp_c || 52.0}°C
              </span>
            </div>

            <div className="p-3 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-700/60 flex flex-col gap-1">
              <span className="text-[11px] text-zinc-500 dark:text-zinc-400 font-medium flex items-center gap-1">
                <Activity size={12} /> {t('cpuLoad')}
              </span>
              <span className="text-base font-mono font-bold text-zinc-900 dark:text-zinc-100">
                {selectedEye.cpu_load_pct !== undefined ? `${Math.round(selectedEye.cpu_load_pct)}%` : '35%'}
              </span>
            </div>
          </div>

          {/* Metric 4: YOLO AI Specs */}
          <div className="p-3 rounded-2xl bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200/60 dark:border-zinc-700/60 flex flex-col gap-1.5 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">{language === 'en' ? 'Model Engine:' : 'Motor IA:'}</span>
              <span className="font-mono font-semibold text-emerald-400">YOLO26n FP16</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">{t('yoloThreshold')}:</span>
              <span className="font-mono font-bold text-zinc-200">{Math.round((selectedEye.yolo_threshold || 0.70)*100)}%</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-zinc-400">{t('networkLink')}:</span>
              <span className="font-mono text-zinc-300">{selectedEye.link_status || 'Wi-Fi 5GHz'}</span>
            </div>
          </div>

          {/* Quick Node Actions */}
          <div className="mt-auto pt-2 flex flex-col gap-2">
            {eyes.length > 1 && (
              <button
                onClick={() => handleDeleteEye(selectedEye.node_id)}
                className="w-full py-2 px-3 rounded-full text-xs font-semibold text-red-400 hover:bg-red-500/10 border border-red-500/30 transition-all flex items-center justify-center gap-1.5 active:scale-95"
              >
                <Trash2 size={13} />
                <span>{t('deleteEye')}</span>
              </button>
            )}
          </div>

        </div>

      </div>

      {/* Bottom Section: Recordings and Evidences Gallery */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200/80 dark:border-zinc-800/80 rounded-3xl p-5 shadow-sm flex flex-col gap-4">
        
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-900 dark:text-zinc-100">
              <ShieldAlert size={16} />
            </div>
            <div>
              <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 tracking-tight">
                {t('evidenceHistory')}
              </h4>
              <p className="text-[11px] text-zinc-400">
                {language === 'en' ? 'Intrusion snapshots & manual recorded clips' : 'Capturas automáticas de intrusiones YOLO y clips manuales'}
              </p>
            </div>
          </div>

          <span className="text-xs font-mono text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-3 py-1 rounded-full border border-zinc-200/60 dark:border-zinc-700/60">
            {recordings.length} {language === 'en' ? 'Records' : 'Evidencias'}
          </span>
        </div>

        {recordings.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {recordings.map(rec => (
              <div 
                key={rec.id}
                className="group relative bg-zinc-950 rounded-2xl overflow-hidden border border-zinc-200 dark:border-zinc-800 hover:border-emerald-500/50 transition-all shadow-sm flex flex-col"
              >
                <div className="aspect-video w-full bg-zinc-900 overflow-hidden relative">
                  <img 
                    src={rec.snapshot} 
                    alt="Evidence Snapshot" 
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <button
                      onClick={() => setPreviewSnapshot(rec.snapshot)}
                      className="w-7 h-7 rounded-full bg-white text-zinc-950 flex items-center justify-center shadow-md active:scale-90"
                      title="Ver Captura"
                    >
                      <Play size={12} className="ml-0.5" />
                    </button>
                    <a
                      href={rec.snapshot}
                      download={`sari_evidence_${rec.id}.jpg`}
                      className="w-7 h-7 rounded-full bg-zinc-800 text-white flex items-center justify-center shadow-md active:scale-90"
                      title="Descargar"
                    >
                      <Download size={12} />
                    </a>
                  </div>
                </div>

                <div className="p-2.5 flex flex-col gap-0.5 bg-white dark:bg-zinc-900">
                  <span className="text-[10px] font-mono text-zinc-400 truncate">{rec.timestamp}</span>
                  <span className="text-[11px] font-semibold text-zinc-800 dark:text-zinc-200 truncate leading-tight">
                    {rec.content.split('\n')[0] || 'Alerta YOLO'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-zinc-400 text-xs flex flex-col items-center justify-center gap-2">
            <ShieldAlert size={24} className="text-zinc-500" />
            <span>{t('noRecordings')}</span>
          </div>
        )}

      </div>

            {/* Modal: Configurar Módulo Jetson */}
      {isConfigModalOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200"
          onClick={() => setIsConfigModalOpen(false)}
        >
          <div 
            className="w-full max-w-lg bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-3xl p-6 shadow-2xl relative"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between pb-4 border-b border-zinc-100 dark:border-zinc-800">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-2xl bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center text-zinc-800 dark:text-zinc-200 shadow-sm border border-zinc-200/60 dark:border-zinc-700/60">
                  <Settings2 size={18} />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-zinc-900 dark:text-zinc-100">
                    {language === 'en' ? 'Configure Jetson Node' : 'Configurar Módulo Jetson'}
                  </h3>
                  <p className="text-[11px] text-zinc-400 font-mono">{selectedEye.node_id}</p>
                </div>
              </div>

              <button
                onClick={() => setIsConfigModalOpen(false)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-zinc-400 hover:text-zinc-900 dark:hover:text-white hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all"
              >
                <X size={16} />
              </button>
            </div>

            {configError && (
              <div className="mt-4 p-3 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
                <AlertCircle size={15} className="shrink-0" />
                <span>{configError}</span>
              </div>
            )}

            {configSuccess && (
              <div className="mt-4 p-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs flex items-center gap-2">
                <CheckCircle2 size={15} className="shrink-0" />
                <span>{configSuccess}</span>
              </div>
            )}

            <form onSubmit={handleSaveConfig} className="mt-4 flex flex-col gap-4">
              <div>
                <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5">
                  {language === 'en' ? 'Node Name' : 'Nombre del Nodo'}
                </label>
                <input
                  type="text"
                  required
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 rounded-2xl text-xs text-zinc-900 dark:text-zinc-100 outline-none focus:ring-2 focus:ring-zinc-400"
                  placeholder="Jetson Orin Nano (PTZ 1)"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5">
                    {language === 'en' ? 'IP Address' : 'Dirección IP'}
                  </label>
                  <input
                    type="text"
                    required
                    value={editIp}
                    onChange={e => setEditIp(e.target.value)}
                    className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 rounded-2xl text-xs font-mono text-zinc-900 dark:text-zinc-100 outline-none focus:ring-2 focus:ring-zinc-400"
                    placeholder="192.168.1.77"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5">
                    {language === 'en' ? 'YOLO Confidence' : 'Umbral YOLO'} ({Math.round(editThreshold * 100)}%)
                  </label>
                  <input
                    type="range"
                    min="0.30"
                    max="0.95"
                    step="0.05"
                    value={editThreshold}
                    onChange={e => setEditThreshold(parseFloat(e.target.value))}
                    className="w-full accent-emerald-500 mt-2 cursor-pointer"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5">
                  {language === 'en' ? 'Stream URL (MJPEG / RTSP)' : 'URL del Stream (MJPEG / RTSP)'}
                </label>
                <input
                  type="text"
                  required
                  value={editStreamUrl}
                  onChange={e => setEditStreamUrl(e.target.value)}
                  className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 rounded-2xl text-xs font-mono text-zinc-900 dark:text-zinc-100 outline-none focus:ring-2 focus:ring-zinc-400"
                  placeholder="http://192.168.1.77:8080/mjpeg"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Lock size={12} /> {language === 'en' ? 'Security PIN' : 'PIN de Seguridad'}
                  </span>
                  <span className="text-[10px] text-zinc-400 font-normal">
                    {language === 'en' ? 'Required for tactical changes' : 'Requerido para cambios tácticos (1234)'}
                  </span>
                </label>
                <input
                  type="password"
                  maxLength={4}
                  required
                  value={editPin}
                  onChange={e => setEditPin(e.target.value)}
                  className="w-full bg-zinc-50 dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700 px-4 py-2.5 rounded-2xl text-xs font-mono tracking-widest text-zinc-900 dark:text-zinc-100 outline-none focus:ring-2 focus:ring-zinc-400"
                  placeholder="••••"
                />
              </div>

              <div className="flex gap-2 justify-end pt-3 border-t border-zinc-100 dark:border-zinc-800 mt-2">
                <button
                  type="button"
                  onClick={() => setIsConfigModalOpen(false)}
                  className="px-4 py-2 rounded-full text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-all"
                >
                  {language === 'en' ? 'Cancel' : 'Cancelar'}
                </button>
                <button
                  type="submit"
                  disabled={configSaving}
                  className="px-5 py-2 rounded-full text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-sm active:scale-95 disabled:opacity-50"
                >
                  {configSaving ? (language === 'en' ? 'Saving...' : 'Guardando...') : (language === 'en' ? 'Save Settings' : 'Guardar Configuración')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Connect Eye Modal */}
      <ConnectEyeModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onEyeCreated={() => {
          fetchEyes();
          setIsModalOpen(false);
        }}
        token={token}
      />

      {/* Snapshot Preview Modal */}
      {previewSnapshot && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4"
          onClick={() => setPreviewSnapshot(null)}
        >
          <div className="max-w-3xl w-full bg-zinc-900 border border-zinc-800 rounded-3xl overflow-hidden shadow-2xl p-2 relative" onClick={e => e.stopPropagation()}>
            <img src={previewSnapshot} alt="Snapshot Preview" className="w-full h-auto rounded-2xl" />
            <button
              onClick={() => setPreviewSnapshot(null)}
              className="absolute top-4 right-4 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center backdrop-blur-md"
            >
              ✕
            </button>
          </div>
        </div>
      )}

    </div>
  );
}
