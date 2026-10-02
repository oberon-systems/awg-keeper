import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The built assets are copied into the panel image and served by FastAPI, so
// the base is the site root. `npm run dev` proxies the api to a panel running
// on the host instead. stats.html is its own entry: the clients' page must not
// carry the admin panel's code.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: { input: { index: "index.html", stats: "stats.html" } },
  },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
