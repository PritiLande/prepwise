import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// defineConfig gives us autocomplete and type checking in editors.
export default defineConfig({
  plugins: [react()],
  server: {
    // host: '0.0.0.0' tells Vite's dev server to listen on ALL network
    // interfaces inside the container, not just localhost.
    // WHY needed for Docker? Without this, Vite only accepts connections
    // from inside the container itself. Docker maps the container port to
    // the host machine, so the connection comes from "outside" — it would
    // be refused. 0.0.0.0 means "accept from anywhere that can reach this port".
    host: '0.0.0.0',
    port: 5173,
  },
  // Vitest configuration lives here alongside Vite so we only need one config file.
  test: {
    // jsdom simulates a browser DOM so React components can render in Node.js.
    environment: 'jsdom',
    // Import the jest-dom matchers (toBeInTheDocument, etc.) before every test.
    setupFiles: './src/__tests__/setup.js',
    globals: true,
  },
})
