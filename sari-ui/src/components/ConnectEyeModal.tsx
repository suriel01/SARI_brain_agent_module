import { useState } from 'react';
import { X, Wifi, Video, CheckCircle2, AlertCircle, Copy, Check, Terminal, ShieldCheck } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import { apiFetch } from '../api';

interface ConnectEyeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onEyeCreated: () => void;
  token: string;
}

export default function ConnectEyeModal({ isOpen, onClose, onEyeCreated, token }: ConnectEyeModalProps) {
  const { language, t } = useLanguage();
  const [activeTab, setActiveTab] = useState<'form' | 'script'>('form');

  const [nodeId, setNodeId] = useState('');
  const [name, setName] = useState('');
  const [ip, setIp] = useState('192.168.1.');
  const [streamUrl, setStreamUrl] = useState('');
  const [yoloThreshold, setYoloThreshold] = useState(0.70);

  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ reachable?: boolean; latency_ms?: number; error?: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleTestConnection = async () => {
    if (!streamUrl && !ip) return;
    setTesting(true);
    setTestResult(null);

    const target = streamUrl || `http://${ip}:8080/mjpeg`;
    try {
      const res = await apiFetch('/eyes/test-connection', token, {
        method: 'POST',
        body: JSON.stringify({ target_url: target })
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err: any) {
      setTestResult({ reachable: false, error: err.message || 'Error de red' });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nodeId || !name) {
      setSaveError(language === 'en' ? 'Node ID and Name are required' : 'El ID y el Nombre son obligatorios');
      return;
    }

    setSaving(true);
    setSaveError(null);

    const finalStream = streamUrl || `http://${ip}:8080/mjpeg`;

    try {
      const res = await apiFetch('/eyes', token, {
        method: 'POST',
        body: JSON.stringify({
          node_id: nodeId.trim(),
          name: name.trim(),
          ip: ip.trim(),
          stream_url: finalStream.trim(),
          yolo_threshold: yoloThreshold,
          is_active: true
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Error al crear nodo');
      }

      onEyeCreated();
      onClose();
    } catch (err: any) {
      setSaveError(err.message || 'Error de conexión');
    } finally {
      setSaving(false);
    }
  };

  const setupScript = `curl -sSL http://192.168.1.71:7000/install_jetson.sh | JETSON_NODE_ID="${nodeId || 'Jetson-PTZ_X'}" JETSON_NODE_IP="${ip || '192.168.1.X'}" bash`;

  const handleCopyScript = () => {
    navigator.clipboard.writeText(setupScript);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-zinc-900 border border-zinc-800 rounded-3xl p-6 shadow-2xl flex flex-col gap-5 relative text-zinc-100">
        
        {/* Header */}
        <div className="flex justify-between items-center pb-3 border-b border-zinc-800/80">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <Video size={18} />
            </div>
            <div>
              <h2 className="text-sm font-semibold tracking-tight leading-none text-white">
                {t('connectEyeModalTitle')}
              </h2>
              <p className="text-[11px] text-zinc-400 mt-1">
                {language === 'en' ? 'Register and link a new Jetson CV edge device' : 'Registra y enlaza un nuevo dispositivo Jetson perimetral'}
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-zinc-800/80 hover:bg-zinc-700 text-zinc-400 hover:text-white flex items-center justify-center transition-all"
          >
            <X size={15} />
          </button>
        </div>

        {/* Tab Toggle */}
        <div className="flex gap-1 bg-zinc-950 p-1 rounded-full border border-zinc-800">
          <button
            type="button"
            onClick={() => setActiveTab('form')}
            className={`flex-1 py-1.5 rounded-full text-xs font-semibold transition-all ${activeTab === 'form' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            {language === 'en' ? 'Node Parameters' : 'Parámetros del Nodo'}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('script')}
            className={`flex-1 py-1.5 rounded-full text-xs font-semibold transition-all ${activeTab === 'script' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'}`}
          >
            {language === 'en' ? 'Jetson Command' : 'Comando para Jetson'}
          </button>
        </div>

        {activeTab === 'form' ? (
          <form onSubmit={handleSave} className="flex flex-col gap-4">
            {saveError && (
              <div className="p-3 rounded-2xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center gap-2">
                <AlertCircle size={14} />
                <span>{saveError}</span>
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  {t('nodeId')} *
                </label>
                <input 
                  type="text" 
                  value={nodeId} 
                  onChange={e => setNodeId(e.target.value)} 
                  placeholder="Jetson-PTZ_2"
                  className="w-full bg-zinc-950 border border-zinc-800 px-3.5 py-2 rounded-xl text-xs text-white outline-none focus:border-zinc-500 transition-all font-mono"
                  required
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  {t('nodeName')} *
                </label>
                <input 
                  type="text" 
                  value={name} 
                  onChange={e => setName(e.target.value)} 
                  placeholder={language === 'en' ? 'North Gate PTZ' : 'Acceso Norte PTZ'}
                  className="w-full bg-zinc-950 border border-zinc-800 px-3.5 py-2 rounded-xl text-xs text-white outline-none focus:border-zinc-500 transition-all"
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  {t('ipAddress')}
                </label>
                <input 
                  type="text" 
                  value={ip} 
                  onChange={e => setIp(e.target.value)} 
                  placeholder="192.168.1.75"
                  className="w-full bg-zinc-950 border border-zinc-800 px-3.5 py-2 rounded-xl text-xs text-white outline-none focus:border-zinc-500 transition-all font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider block mb-1">
                  {t('streamUrl')}
                </label>
                <input 
                  type="text" 
                  value={streamUrl} 
                  onChange={e => { setStreamUrl(e.target.value); setTestResult(null); }} 
                  placeholder="http://192.168.1.75:8080/mjpeg"
                  className="w-full bg-zinc-950 border border-zinc-800 px-3.5 py-2 rounded-xl text-xs text-white outline-none focus:border-zinc-500 transition-all font-mono"
                />
              </div>
            </div>

            {/* YOLO Threshold Slider */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">
                  {t('yoloThreshold')}
                </label>
                <span className="text-xs font-mono font-bold text-emerald-400">{Math.round(yoloThreshold * 100)}%</span>
              </div>
              <input 
                type="range" 
                min="0.50" 
                max="0.95" 
                step="0.05"
                value={yoloThreshold} 
                onChange={e => setYoloThreshold(parseFloat(e.target.value))}
                className="w-full accent-emerald-400 bg-zinc-800 rounded-lg cursor-pointer"
              />
            </div>

            {/* Test Connection Button & Result */}
            <div className="flex items-center justify-between p-3 rounded-2xl bg-zinc-950 border border-zinc-800/80">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testing}
                className="px-3.5 py-1.5 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-200 hover:bg-zinc-700 hover:text-white transition-all flex items-center gap-1.5 active:scale-95 disabled:opacity-50"
              >
                <Wifi size={13} />
                {testing ? (language === 'en' ? 'Testing...' : 'Probando...') : t('testConnection')}
              </button>

              {testResult && (
                <div className="flex items-center gap-1.5 text-xs font-medium">
                  {testResult.reachable ? (
                    <>
                      <CheckCircle2 size={14} className="text-emerald-400" />
                      <span className="text-emerald-400">{t('connectionSuccess')} ({testResult.latency_ms}ms)</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle size={14} className="text-amber-400" />
                      <span className="text-amber-400">{t('connectionFailed')}</span>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Footer Buttons */}
            <div className="flex justify-end gap-2 pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-full text-xs font-semibold text-zinc-400 hover:text-white hover:bg-zinc-800 transition-all"
              >
                {language === 'en' ? 'Cancel' : 'Cancelar'}
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-5 py-2 rounded-full text-xs font-bold bg-white text-zinc-950 hover:bg-zinc-200 transition-all active:scale-95 shadow-md disabled:opacity-50"
              >
                {saving ? (language === 'en' ? 'Saving...' : 'Guardando...') : t('saveEye')}
              </button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-xs text-zinc-400 leading-relaxed">
              {language === 'en'
                ? 'Run this command on the new Jetson terminal to automatically configure the MQTT wireless telemetry daemon pointing to this Cerebro module:'
                : 'Ejecuta este comando en la terminal de la nueva Jetson para configurar automáticamente el daemon de telemetría inalámbrica MQTT hacia este módulo Cerebro:'}
            </p>

            <div className="relative bg-zinc-950 border border-zinc-800 p-4 rounded-2xl font-mono text-[11px] text-zinc-300 break-all">
              <div className="flex items-center gap-2 text-zinc-500 mb-2 text-[10px] uppercase font-bold">
                <Terminal size={13} />
                <span>Bash Setup One-Liner</span>
              </div>
              <code className="text-emerald-300 select-all">
                {setupScript}
              </code>
              <button
                type="button"
                onClick={handleCopyScript}
                className="absolute top-3 right-3 px-2.5 py-1 rounded-full bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-[10px] font-semibold flex items-center gap-1 transition-all"
              >
                {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                <span>{copied ? t('copied') : t('copyCommand')}</span>
              </button>
            </div>

            <div className="p-3.5 rounded-2xl bg-zinc-950 border border-zinc-800 text-[11px] text-zinc-400 flex flex-col gap-1.5">
              <div className="flex items-center gap-1.5 text-zinc-300 font-semibold">
                <ShieldCheck size={13} className="text-emerald-400" />
                <span>{language === 'en' ? 'Pre-requisites' : 'Requisitos Previos'}</span>
              </div>
              <ul className="list-disc list-inside space-y-0.5 text-zinc-400 pl-1">
                <li>{language === 'en' ? 'Jetson connected to Wi-Fi (192.168.1.X)' : 'Jetson conectada a la red Wi-Fi (192.168.1.X)'}</li>
                <li>{language === 'en' ? 'Streamer running on port 8080 or RTSP' : 'Streamer activo en puerto 8080 o RTSP'}</li>
                <li>{language === 'en' ? 'Python3 and pip3 installed' : 'Python3 y pip3 instalados'}</li>
              </ul>
            </div>

            <div className="flex justify-end pt-2 border-t border-zinc-800">
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2 rounded-full text-xs font-bold bg-white text-zinc-950 hover:bg-zinc-200 transition-all active:scale-95 shadow-md"
              >
                {language === 'en' ? 'Close' : 'Cerrar'}
              </button>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
