import type { Config } from "tailwindcss";

/**
 * Design tokens Bridge — mapping Tailwind → variables CSS sémantiques.
 *
 * `theme.colors` est volontairement REMPLACÉ (pas étendu) : aucune couleur
 * hardcodée n'est utilisable dans les composants. Les valeurs réelles
 * (light/dark) vivent dans `app/globals.css`.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      inherit: "inherit",
      surface: {
        DEFAULT: "var(--color-surface-default)",
        muted: "var(--color-surface-muted)",
      },
      content: {
        DEFAULT: "var(--color-text-primary)",
        secondary: "var(--color-text-secondary)",
        // ⚠️ jamais pour du texte porteur d'information (contraste insuffisant)
        disabled: "var(--color-text-disabled)",
        inverse: "var(--color-text-inverse)",
        "on-action": "var(--color-text-on-action)",
      },
      border: {
        DEFAULT: "var(--color-border-default)",
        strong: "var(--color-border-strong)",
      },
      action: {
        primary: "var(--color-action-primary)",
        "primary-hover": "var(--color-action-primary-hover)",
      },
      feedback: {
        error: "var(--color-feedback-error)",
        "error-surface": "var(--color-feedback-error-surface)",
        success: "var(--color-feedback-success)",
        "success-surface": "var(--color-feedback-success-surface)",
        warning: "var(--color-feedback-warning)",
        "warning-surface": "var(--color-feedback-warning-surface)",
        info: "var(--color-feedback-info)",
        "info-surface": "var(--color-feedback-info-surface)",
      },
      focus: "var(--color-focus-ring)",
    },
    extend: {
      fontFamily: {
        sans: [
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        "input-focus": "var(--shadow-input-focus)",
      },
    },
  },
  plugins: [],
};

export default config;
