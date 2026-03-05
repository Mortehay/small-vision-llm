import React, { useState, useEffect } from 'react';
import { useStreamControl } from '../hooks/useStream';
import { useLogs } from '../hooks/useLogs';
import { useLatestFrame } from '../hooks/useLatestFrame';
import { useHistory } from '../hooks/useHistory';
import VideoPlayer from '../components/VideoPlayer';


const API_URL = import.meta.env.VITE_API_URL;
const API_URL_FALLBACK = API_URL + "/latest-frame-fallback";

// We serve HLS streams from the frontend dist/streams folder (or proxied)
// For dev mode, we need to know where the streams are.
// Since we are running in a container, the frontend is served at :5173
// and the streams are written to dist/streams.
const RAW_STREAM_URL = `${API_URL}/hls-streams/raw/live.m3u8`;
const PROC_STREAM_URL = `${API_URL}/hls-streams/processed/live.m3u8`;

export default function Dashboard() {
    const [isOnline, setIsOnline] = useState(false);
    const [streams, setStreams] = useState([]);
    const [selectedStreamId, setSelectedStreamId] = useState('local');
    const [showAddModal, setShowAddModal] = useState(false);
    const [newStream, setNewStream] = useState({ display_name: '', url: '', type: 'external', username: '', password: '' });

    const { logs, isConnected } = useLogs(100);
    const { startStream, stopStream, fetchStreams, addStream, deleteStream, loading } = useStreamControl();
    const { frameUrl, isCapturing, lastCaptureTime } = useLatestFrame();
    const { clearHistory, isClearing } = useHistory();

    useEffect(() => {
        loadStreams();
    }, []);

    const loadStreams = async () => {
        const data = await fetchStreams();
        setStreams(data);
        if (data.length > 0 && !selectedStreamId) {
            setSelectedStreamId(data[0].id);
        }
    };

    const handleToggle = async () => {
        if (isOnline) {
            await stopStream();
            setIsOnline(false);
        } else {
            await startStream(selectedStreamId);
            setIsOnline(true);
        }
    };

    const handleAddStream = async (e) => {
        e.preventDefault();
        await addStream(newStream);
        await loadStreams();
        setShowAddModal(false);
        setNewStream({ display_name: '', url: '', type: 'external', username: '', password: '' });
    };

    const handleDeleteStream = async (id) => {
        if (window.confirm('Are you sure you want to delete this stream?')) {
            await deleteStream(id);
            await loadStreams();
            if (selectedStreamId === id) setSelectedStreamId(streams[0]?.id);
        }
    };

    const handleStreamSwitch = async (id) => {
        if (isOnline) {
            await stopStream();
            setIsOnline(false);
        }
        setSelectedStreamId(id);
    };

    return (
        <div className="min-h-screen bg-slate-900 text-white p-8">
            <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-xl gap-6">
                <div className="flex-1">
                    <h1 className="text-3xl font-extrabold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">AI Stream Multi-Source</h1>
                    <p className="text-slate-400 text-sm mt-1">Status: {isOnline ? 'Active' : 'Standby'}</p>
                </div>

                {/* Stream Source Selector */}
                <div className="flex flex-col gap-3 min-w-[300px]">
                    <div className="flex justify-between items-center bg-slate-900/50 p-3 rounded-xl border border-slate-700">
                        <div className="flex flex-col flex-1 mr-4">
                            <span className="text-[10px] text-slate-500 uppercase font-bold tracking-widest mb-1">Source Pipeline</span>
                            <select
                                value={selectedStreamId}
                                onChange={(e) => handleStreamSwitch(e.target.value)}
                                className="bg-transparent text-sm font-bold text-emerald-400 focus:outline-none cursor-pointer"
                            >
                                {streams.map(s => (
                                    <option key={s.id} value={s.id} className="bg-slate-800">{s.display_name}</option>
                                ))}
                            </select>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setShowAddModal(true)}
                                className="p-2 hover:bg-slate-700 rounded-lg transition-colors text-slate-400"
                                title="Add New Stream"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                                    <path fillRule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clipRule="evenodd" />
                                </svg>
                            </button>
                            <button
                                onClick={handleToggle}
                                disabled={loading}
                                className={`relative w-14 h-7 rounded-full transition-all duration-300 ${isOnline ? 'bg-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.4)]' : 'bg-slate-600 shadow-inner'}`}
                            >
                                <div className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full transition-transform duration-300 transform shadow-md ${isOnline ? 'translate-x-7' : 'translate-x-0'}`} />
                            </button>
                        </div>
                    </div>
                </div>

                <div className="bg-slate-900/30 p-3 rounded-xl border border-slate-700/50">
                    <button
                        onClick={clearHistory}
                        disabled={isClearing}
                        className={`px-4 py-2 rounded-lg text-xs font-bold transition-all ${isClearing ? 'bg-slate-700 text-slate-500' : 'bg-rose-600/20 text-rose-400 hover:bg-rose-600 hover:text-white border border-rose-500/30 active:scale-95'}`}
                    >
                        {isClearing ? 'Clearing...' : 'Wipe Data'}
                    </button>
                </div>
            </header>

            <main className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2 space-y-6">
                    <div className={`bg-slate-950 rounded-3xl overflow-hidden border border-slate-700/50 shadow-2xl relative group transition-all duration-700 ${!isOnline ? 'grayscale opacity-50 blur-sm scale-[0.98]' : 'grayscale-0 opacity-100 blur-0 scale-100'}`}>
                        <img src={frameUrl} className="w-full aspect-video object-cover" alt="AI Focus" onError={(e) => e.target.src = API_URL_FALLBACK} />
                        <div className="absolute top-4 right-4 flex gap-2">
                            <div className="bg-black/60 backdrop-blur-md px-3 py-1 rounded-full border border-white/10 text-[10px] uppercase font-bold tracking-widest text-emerald-400 flex items-center gap-1.5">
                                <span className={`h-1.5 w-1.5 rounded-full ${isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`}></span>
                                {isOnline ? 'Analyzing' : 'Standby'}
                            </div>
                        </div>
                        {lastCaptureTime && (
                            <div className="absolute bottom-4 left-4 bg-black/40 backdrop-blur-xl px-4 py-2 rounded-2xl border border-white/5 text-[10px] font-mono text-slate-300 shadow-lg">
                                DETECTED AT: {lastCaptureTime.toLocaleTimeString()}
                            </div>
                        )}
                        {!isOnline && (
                            <div className="absolute inset-0 flex items-center justify-center">
                                <div className="text-center space-y-2">
                                    <p className="text-slate-400 font-medium tracking-wide">System is currently offline</p>
                                    <button onClick={handleToggle} className="text-xs bg-emerald-500/10 text-emerald-400 px-4 py-1.5 rounded-full border border-emerald-500/20 hover:bg-emerald-500/20 transition-all font-bold">Wake System</button>
                                </div>
                            </div>
                        )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <VideoPlayer isOnline={isOnline} url={RAW_STREAM_URL} title="Raw Input Feed" />
                        <VideoPlayer isOnline={isOnline} url={PROC_STREAM_URL} title="Inference Output" />
                    </div>
                </div>

                <div className="flex flex-col h-[700px] bg-slate-900/50 backdrop-blur-sm rounded-3xl border border-slate-800 shadow-2xl overflow-hidden">
                    <div className="p-4 bg-slate-800/80 border-b border-slate-700 flex justify-between items-center">
                        <div className="flex items-center gap-2">
                            <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></div>
                            <span className="text-xs font-bold text-slate-300 uppercase tracking-widest">Neural Logs</span>
                        </div>
                        <span className="text-[10px] font-mono text-slate-500">{isConnected ? 'LIVE' : 'RECONNECTING'}</span>
                    </div>

                    <div className="p-6 overflow-y-auto font-mono text-[11px] leading-relaxed flex flex-col-reverse h-full scrollbar-hide">
                        <div className="space-y-3">
                            {logs.map((log, i) => (
                                <div key={i} className="group flex gap-3 border-l border-emerald-500/30 pl-4 hover:border-emerald-400 transition-colors">
                                    <span className="text-emerald-400/80 whitespace-pre-wrap">{log}</span>
                                </div>
                            ))}
                            {logs.length === 0 && <p className="text-slate-600 italic animate-pulse">Waiting for neural connection...</p>}
                        </div>
                    </div>
                </div>
            </main>

            {/* Add Stream Modal */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <div className="bg-slate-800 border border-slate-700 rounded-3xl p-8 max-w-md w-full shadow-2xl">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">New Observation Source</h3>
                            <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-white">&times;</button>
                        </div>
                        <form onSubmit={handleAddStream} className="space-y-4">
                            <div>
                                <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5 ml-1">Friendly Name</label>
                                <input required value={newStream.display_name} onChange={e => setNewStream({ ...newStream, display_name: e.target.value })} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 outline-none transition-all" placeholder="Living Room ESP32" />
                            </div>
                            <div>
                                <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5 ml-1">Source URL / Device</label>
                                <input required value={newStream.url} onChange={e => setNewStream({ ...newStream, url: e.target.value })} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 outline-none transition-all" placeholder="/dev/video0 or http://.../stream" />
                                <p className="text-[10px] text-slate-600 mt-1.5 ml-1">Tip: Use /dev/video0 for local. For ESP32-CAM, use the direct stream endpoint (e.g. /stream).</p>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5 ml-1">Auth: User</label>
                                    <input value={newStream.username} onChange={e => setNewStream({ ...newStream, username: e.target.value })} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 outline-none transition-all" placeholder="Optional" />
                                </div>
                                <div>
                                    <label className="block text-[10px] font-bold text-slate-500 uppercase mb-1.5 ml-1">Auth: Pass</label>
                                    <input type="password" value={newStream.password} onChange={e => setNewStream({ ...newStream, password: e.target.value })} className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-sm focus:border-emerald-500 outline-none transition-all" placeholder="Optional" />
                                </div>
                            </div>
                            <button type="submit" className="w-full bg-gradient-to-r from-emerald-500 to-cyan-500 text-white font-bold py-4 rounded-xl shadow-lg hover:shadow-emerald-500/20 transition-all active:scale-95 mt-4">Initialize Source</button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}