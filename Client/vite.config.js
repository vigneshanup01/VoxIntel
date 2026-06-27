import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    watch: {
      // Native filesystem change events from a Windows host don't reliably
      // propagate through Docker's bind-mount layer into the container's
      // file watcher -- without polling, the dev server can silently keep
      // serving stale code indefinitely after host-side edits.
      usePolling: true,
      interval: 300,
    },
  },
});
