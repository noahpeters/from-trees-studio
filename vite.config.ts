import { cloudflare } from "@cloudflare/vite-plugin";
import { defineConfig } from "vite";
import vinext from "vinext";
import { sites } from "./build/sites-vite-plugin";

export default defineConfig({
  publicDir: process.env.CALIBRATION_ONLY === "1" ? false : "public",
  plugins: [
    vinext(),
    cloudflare({
      viteEnvironment: { name: "rsc", childEnvironments: ["ssr"] },
    }),
    sites(),
  ],
});
