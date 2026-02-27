import { useState, useEffect } from 'react';
import { io } from 'socket.io-client';

const API_URL = import.meta.env.VITE_API_URL;

export const useLatestFrame = () => {
  // We initialize with the base URL
  const [frameUrl, setFrameUrl] = useState(`${API_URL}/latest-frame`);

  useEffect(() => {
    const socket = io(API_URL, { transports: ['websocket'] });

    socket.on('log_update', (msg) => {
      // If the log contains our trigger phrase, we force an update
      if (msg.data.includes("Saved AI Snapshot")) {
        // We add a timestamp (?t=...) to force the browser to ignore its cache
        setFrameUrl(`${API_URL}/latest-frame?t=${Date.now()}`);
      }
    });

    return () => socket.disconnect();
  }, []);

  return frameUrl;
};