import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    // Windows + Docker: file events don't reach the container (./hack dev sets this).
    watch: process.env.WATCH_POLLING
      ? { usePolling: true, interval: 300 }
      : undefined,
    // Same-origin /api in dev and prod, so no CORS setup is needed.
    proxy: {
      "/api": process.env.API_PROXY_TARGET ?? "http://localhost:8000",
    },
  },
})
