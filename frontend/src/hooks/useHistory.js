import { useState } from 'react';

const API_URL = import.meta.env.VITE_API_URL;

export const useHistory = () => {
  const [isClearing, setIsClearing] = useState(false);
  const [error, setError] = useState(null);

  const clearHistory = async () => {
    // Confirmation dialog before proceeding
    if (!window.confirm("Are you sure you want to delete all logs and images?")) {
      return false;
    }

    setIsClearing(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/system/clear-history`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to clear history on the server');
      }

      alert("History cleared successfully");
      return true;
    } catch (err) {
      console.error("History Clear Error:", err);
      setError(err.message);
      alert(`Error: ${err.message}`);
      return false;
    } finally {
      setIsClearing(false);
    }
  };

  return { clearHistory, isClearing, error };
};