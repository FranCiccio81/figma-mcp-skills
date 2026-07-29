/**
 * Configuration des tests front.
 *
 * `web/` n'avait aucun runner : zéro test, et donc aucun filet sur les
 * rendus qui portent des garanties produit — l'affichage des critères
 * rédhibitoires, celui des dimensions non évaluées, la provenance des
 * données du profil. Ce sont précisément les endroits où une régression se
 * traduit par une information fausse montrée à un candidat.
 */
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
