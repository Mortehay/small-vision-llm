import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';

const API_URL = import.meta.env.VITE_API_URL;

export const useLatestFrame = () => {
  // We initialize with the base URL
  const [frameUrl, setFrameUrl] = useState(`${API_URL}/latest-frame`);
  const [lastCaptureTime, setLastCaptureTime] = useState(null);
  const [isCapturing, setIsCapturing] = useState(false);

  useEffect(() => {
    let timeoutId;
    const socket = io(API_URL, {
      transports: ['websocket', 'polling'], // Start with websocket
      upgrade: true,
      reconnection: true,
      reconnectionAttempts: Infinity
    });

    socket.on('log_update', (msg) => {
      // If the log contains our trigger phrase, we force an update
      if (msg.data.includes("Saved AI Snapshot")) {
        setLastCaptureTime(new Date());
        setIsCapturing(true);

        // Reset isCapturing after some time if no new frames come in
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => setIsCapturing(false), 10000);

        // We add a timestamp (?t=...) to force the browser to ignore its cache
        setTimeout(() => {
          setFrameUrl(`${API_URL}/latest-frame?t=${Date.now()}`);
        }, 200);
      }
    });

    return () => {
      socket.disconnect();
      clearTimeout(timeoutId);
    };
  }, []);

  return { frameUrl, lastCaptureTime, isCapturing };
};