import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Sprint 94 M4: tsconfig yolları (@/…) Vite'ın kendi çözümüyle — vite-tsconfig-paths eklentisi gereksizdi
  resolve: { tsconfigPaths: true },
  test: {
    environment: "jsdom",
    include: ["__tests__/**/*.test.{ts,tsx}"],
    testTimeout: 15000,
  },
});
