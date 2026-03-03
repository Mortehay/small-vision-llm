import React, { useState, useEffect } from 'react';
import { useStreamControl } from '../hooks/useStream';
import { useLogs } from '../hooks/useLogs';
import { useLatestFrame } from '../hooks/useLatestFrame';
import { useHistory } from '../hooks/useHistory';


const API_URL = import.meta.env.VITE_API_URL;
const API_URL_FALLBACK = API_URL + "/latest-frame-fallback";


export default function Dashboard() {
    const [isOnline, setIsOnline] = useState(false);
    const { logs, isConnected, isSystemActive } = useLogs(100);
    const { startStream, stopStream, loading } = useStreamControl();
    const { frameUrl, isCapturing, lastCaptureTime } = useLatestFrame();
    const { clearHistory, isClearing } = useHistory();

    // 1. Initial & Periodic Status Check


    //2. Sync isOnline with active log signals
    useEffect(() => {
        // 1. Create a timer variable
        if (isSystemActive || isCapturing || frameUrl || lastCaptureTime) {
            setIsOnline(true);
        } else {
            setIsOnline(false);
        }
    }, [isSystemActive, isCapturing, frameUrl, lastCaptureTime]);


    const handleToggle = async () => {
        if (isOnline) {
            await stopStream();
            setIsOnline(false);
        } else {
            await startStream();
            setIsOnline(true);
        }
    };

    return (
        <div className="min-h-screen bg-slate-900 text-white p-8">
            <header className="flex justify-between items-center mb-8 bg-slate-800 p-6 rounded-2xl border border-slate-700 shadow-xl">
                <div>
                    <h1 className="text-2xl font-bold">AI Stream Control</h1>
                    <p className="text-slate-400 text-sm">Backend: {API_URL}</p>
                </div>

                <div className="flex flex-col gap-6">
                    {/* First Row: System Toggler */}
                    <div className="flex items-center justify-between bg-slate-800/50 p-4 rounded-xl border border-slate-700">
                        <div className="flex flex-col">
                            <span className={`font-bold ${isOnline ? 'text-emerald-400' : 'text-slate-500'}`}>
                                {isOnline ? 'SYSTEM LIVE' : 'SYSTEM OFFLINE'}
                            </span>
                            {isCapturing && (
                                <span className="text-[10px] text-emerald-500/80 animate-pulse flex items-center gap-1">
                                    <span className="h-1.5 w-1.5 bg-emerald-500 rounded-full"></span>
                                    CAPTURING DATA
                                </span>
                            )}
                        </div>

                        <button
                            onClick={handleToggle}
                            disabled={loading}
                            className={`relative w-16 h-8 rounded-full transition-colors duration-300 focus:outline-none ${isOnline ? 'bg-emerald-500' : 'bg-slate-600'
                                } ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
                        >
                            <div className={`absolute top-1 left-1 w-6 h-6 bg-white rounded-full transition-transform duration-300 ${isOnline ? 'translate-x-8' : 'translate-x-0'
                                }`} />
                        </button>
                    </div>

                    {/* Second Row: Maintenance / Clear History */}
                    <div className="bg-slate-800 p-4 rounded-xl border border-slate-700">
                        <h3 className="text-sm font-semibold mb-3 text-slate-400 uppercase tracking-wider">Maintenance</h3>
                        <button
                            onClick={clearHistory}
                            disabled={isClearing}
                            className={`w-full py-2 px-4 rounded-lg font-bold transition-all shadow-lg
                ${isClearing
                                    ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                                    : 'bg-rose-600 hover:bg-rose-500 text-white active:scale-95'
                                }`}
                        >
                            {isClearing ? 'Clearing Files...' : 'Clear All History'}
                        </button>

                        {isClearing && (
                            <p className="text-xs text-rose-400 mt-2 text-center animate-pulse">
                                Wiping image and log directories...
                            </p>
                        )}
                    </div>
                </div>

            </header>

            <main className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Stream Window (2/3 width) */}
                <div className="lg:col-span-2 space-y-4">
                    <div className="bg-black rounded-2xl overflow-hidden border border-slate-700 shadow-2xl relative">
                        <img
                            src={frameUrl}
                            className="w-full aspect-video object-cover"
                            alt="AI Processing Stream"
                            onError={(e) => {
                                // If the image fails to load, we show a placeholder
                                e.target.src = API_URL_FALLBACK;
                            }}
                        />
                        {lastCaptureTime && (
                            <div className="absolute bottom-4 left-4 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10 text-[10px] font-mono text-slate-300">
                                LAST SNAPSHOT: {lastCaptureTime.toLocaleTimeString()}
                            </div>
                        )}
                    </div>
                </div>

                {/* Log Terminal (1/3 width) */}
                <div className="flex flex-col h-[600px] bg-slate-950 rounded-2xl border border-slate-800 shadow-inner overflow-hidden">
                    <div className="p-3 bg-slate-800 border-b border-slate-700 flex justify-between items-center">
                        <span className="text-xs font-mono text-slate-400 uppercase tracking-widest">System Console</span>
                        <span className={`h-2 w-2 rounded-full ${isConnected ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' : 'bg-red-500'}`}></span>
                    </div>

                    <div className="p-4 overflow-y-auto font-mono text-xs flex flex-col-reverse h-full scrollbar-thin scrollbar-thumb-slate-700">
                        <div className="space-y-1">
                            {logs.map((log, i) => (
                                <div key={i} className="flex gap-2 border-l-2 border-slate-800 pl-2 hover:bg-slate-900/50">
                                    <span className="text-slate-600">[{i}]</span>
                                    <span className={log.includes('error') ? 'text-red-400' : 'text-emerald-400/90'}>
                                        {log}
                                    </span>
                                </div>
                            ))}
                            {logs.length === 0 && <p className="text-slate-700 italic">Awaiting logs...</p>}
                        </div>
                    </div>

                </div>

            </main>
        </div>
    );
}