import { useEffect, useState } from 'react';
import { io } from 'socket.io-client';

const API_URL = import.meta.env.VITE_API_URL;

export const useLogs = (maxLines = 50) => {
  const [logs, setLogs] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isSystemActive, setIsSystemActive] = useState(false);

  useEffect(() => {
    // Connect to the Flask-SocketIO server
    const socket = io(API_URL, {
      transports: ['websocket', 'polling'],
      upgrade: true,
      reconnection: true,
      reconnectionAttempts: Infinity
    });

    socket.on('connect', () => setIsConnected(true));
    socket.on('disconnect', () => {
      setIsConnected(false);
      setIsSystemActive(false);
    });

    // Listen for the specific 'log_update' event
    socket.on('log_update', (payload) => {
      const line = payload.data;

      // If we see active loop logs, the system is definitely alive
      if (line.includes("Analysis Loop started") || line.includes("Saved AI Snapshot")) {
        setIsSystemActive(true);
      }

      setLogs((prev) => {
        const newLogs = [...prev, line];
        return newLogs.slice(-maxLines); // Keep only the last X lines
      });
    });

    return () => socket.disconnect();
  }, [maxLines]);

  return { logs, isConnected, isSystemActive };
};