import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          950: "#04070d",
          900: "#070c16",
          850: "#0a1120",
          800: "#0d1626",
          700: "#132038",
          600: "#1a2b47",
        },
        line: {
          DEFAULT: "#1b2a44",
          bright: "#27405f",
        },
        ink: {
          DEFAULT: "#e6edf5",
          dim: "#93a4bd",
          faint: "#5c718f",
        },
        signal: {
          cyan: "#38bdf8",
          teal: "#2dd4bf",
          green: "#34d399",
          amber: "#fbbf24",
          orange: "#fb923c",
          red: "#f87171",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 0 0 1px rgba(56,189,248,0.04), 0 12px 32px rgba(2,6,16,0.55)",
      },
      keyframes: {
        "pulse-dot": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.35" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "scan-line": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(220%)" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
        "fade-up": "fade-up 0.25s ease-out both",
        "fade-in": "fade-in 0.2s ease-out both",
        "slide-in-right": "slide-in-right 0.22s ease-out both",
        scan: "scan-line 3.2s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
