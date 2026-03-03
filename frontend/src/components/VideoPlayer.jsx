import React, { useEffect, useRef, useState } from 'react';
import Hls from 'hls.js';

const VideoPlayer = ({ url, title, isOnline }) => {
    const videoRef = useRef(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        let hls;
        const video = videoRef.current;
        if (!video) return;

        setIsLoading(true);

        // 1. Monitor the 'playing' event to hide the loader
        // This is more reliable than HLS events because it confirms pixels are moving
        const handlePlaying = () => {
            console.log("[VideoPlayer] Playback started");
            setIsLoading(false);
        };

        video.addEventListener('playing', handlePlaying);

        if (video.canPlayType('application/vnd.apple.mpegurl')) {
            // Safari/iOS Native support
            video.src = url;
        } else if (Hls.isSupported()) {
            hls = new Hls({
                enableWorker: true,
                lowLatencyMode: true,
                // Automatically start loading fragments
                autoStartLoad: true,
            });

            hls.loadSource(url);
            hls.attachMedia(video);

            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                // Try to play as soon as manifest is ready
                video.play().catch(err => {
                    console.warn("[VideoPlayer] Autoplay blocked, waiting for interaction", err);
                });
            });

            hls.on(Hls.Events.ERROR, (event, data) => {
                if (data.fatal) {
                    switch (data.type) {
                        case Hls.ErrorTypes.NETWORK_ERROR:
                            hls.startLoad();
                            break;
                        case Hls.ErrorTypes.MEDIA_ERROR:
                            hls.recoverMediaError();
                            break;
                        default:
                            hls.destroy();
                            break;
                    }
                }
            });
        }

        return () => {
            video.removeEventListener('playing', handlePlaying);
            if (hls) hls.destroy();
        };
    }, [url]);

    return (
        <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center px-1">
                <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest">{title}</span>
                <span className="text-[9px] font-mono text-emerald-500/50 animate-pulse uppercase">Live</span>
            </div>
            
            <div className="bg-black rounded-lg overflow-hidden border border-slate-800 shadow-lg aspect-video relative group">
                {/* 2. Style: We use 'opacity-100' instead of deleting the element to keep the blur effect smooth */}
         
                <video
                    ref={videoRef}
                    muted // Crucial for Autoplay to work!
                    playsInline
                    autoPlay
                    controls
                    className={`w-full h-full object-contain transition-all duration-1000 ${
                        !isOnline && isLoading ? 'blur-2xl scale-110' : 'blur-0 scale-100'
                    }`}
                />

                {(!isOnline || isLoading) && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/20 backdrop-blur-sm z-10 transition-opacity duration-500">
                        <div className="w-8 h-8 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mb-2" />
                        <span className="text-[10px] font-mono text-white animate-pulse">
                            Establishing Connection...
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default VideoPlayer;