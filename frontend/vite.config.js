import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // Allows access from outside the container
    port: 5173,
    // Proxy removed: We will use the .env variable in our code instead
  },
});