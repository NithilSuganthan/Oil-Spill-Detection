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
        "glow-pulse": {
          "0%, 100%": { boxShadow: "0 0 4px rgba(56,189,248,0.15)" },
          "50%": { boxShadow: "0 0 12px rgba(56,189,248,0.35)" },
        },
        "number-pop": {
          "0%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.15)" },
          "100%": { transform: "scale(1)" },
        },
        "slide-down": {
          from: { opacity: "0", transform: "translateY(-8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "pipeline-flow": {
          "0%": { backgroundPosition: "0% 50%" },
          "100%": { backgroundPosition: "200% 50%" },
        },
        "scan-sweep": {
          "0%": { transform: "translateY(-100%)", opacity: "0.7" },
          "50%": { opacity: "0.4" },
          "100%": { transform: "translateY(100%)", opacity: "0" },
        },
        "ring-pulse": {
          "0%": { transform: "scale(0.95)", opacity: "0.8" },
          "50%": { transform: "scale(1.05)", opacity: "0.4" },
          "100%": { transform: "scale(0.95)", opacity: "0.8" },
        },
        "particle-move": {
          "0%": { offsetDistance: "0%", opacity: "0" },
          "10%": { opacity: "1" },
          "90%": { opacity: "1" },
          "100%": { offsetDistance: "100%", opacity: "0" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        "radar-sweep": {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        "radar-ping": {
          "0%": { transform: "scale(1)", opacity: "0.6" },
          "100%": { transform: "scale(3)", opacity: "0" },
        },
        "card-highlight": {
          "0%": { boxShadow: "0 0 0 1px rgba(56,189,248,0.5)", backgroundColor: "rgba(56,189,248,0.1)" },
          "100%": { boxShadow: "none", backgroundColor: "transparent" },
        },
        "vessel-pulse": {
          "0%, 100%": { boxShadow: "0 0 4px rgba(245,158,11,0.3)" },
          "50%": { boxShadow: "0 0 10px rgba(245,158,11,0.5)" },
        },
        "status-blink": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "expand-in": {
          from: { maxHeight: "0px", opacity: "0" },
          to: { maxHeight: "600px", opacity: "1" },
        },
      },
      animation: {
        "pulse-dot": "pulse-dot 1.6s ease-in-out infinite",
        "fade-up": "fade-up 0.25s ease-out both",
        "fade-in": "fade-in 0.2s ease-out both",
        "slide-in-right": "slide-in-right 0.22s ease-out both",
        "slide-down": "slide-down 0.22s ease-out both",
        scan: "scan-line 3.2s linear infinite",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
        "number-pop": "number-pop 0.3s ease-out",
        "pipeline-flow": "pipeline-flow 2s linear infinite",
        "scan-sweep": "scan-sweep 2.5s ease-in-out infinite",
        "ring-pulse": "ring-pulse 2s ease-in-out infinite",
        shimmer: "shimmer 2s linear infinite",
        "radar-sweep": "radar-sweep 3s linear infinite",
        "radar-ping": "radar-ping 1.5s ease-out infinite",
        "card-highlight": "card-highlight 2s ease-out forwards",
        "vessel-pulse": "vessel-pulse 2s ease-in-out infinite",
        "status-blink": "status-blink 1s ease-in-out infinite",
        "expand-in": "expand-in 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
