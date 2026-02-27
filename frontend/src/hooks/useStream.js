import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL;

export const useStreamControl = () => {
  const [loading, setLoading] = useState(false);

  const startStream = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/system/start`, { method: 'POST' });
      return await response.json();
    } finally {
      setLoading(false);
    }
  };

  const stopStream = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/system/stop`, { method: 'POST' });
      return await response.json();
    } finally {
      setLoading(false);
    }
  };

  return { startStream, stopStream, loading };
};