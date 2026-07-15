import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist" },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
} as Parameters<typeof defineConfig>[0]);
