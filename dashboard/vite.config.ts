import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base: "./" so the built dashboard works when served from any sub-path.
export default defineConfig({
  plugins: [react()],
  base: "./",
});
