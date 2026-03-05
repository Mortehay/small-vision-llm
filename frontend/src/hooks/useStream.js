import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL;

export const useStreamControl = () => {
  const [loading, setLoading] = useState(false);

  const fetchStreams = async () => {
    const response = await fetch(`${API_URL}/streams`);
    return await response.json();
  };

  const startStream = async (streamId = 'local') => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/system/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stream_id: streamId })
      });
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

  const addStream = async (streamData) => {
    const response = await fetch(`${API_URL}/streams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(streamData)
    });
    return await response.json();
  };

  const deleteStream = async (streamId) => {
    await fetch(`${API_URL}/streams/${streamId}`, { method: 'DELETE' });
  };

  return { startStream, stopStream, fetchStreams, addStream, deleteStream, loading };
};