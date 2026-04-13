import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        sidebar: {
          DEFAULT: "#1e293b",
          foreground: "#f8fafc",
        },
        primary: {
          DEFAULT: "#2563eb",
          foreground: "#ffffff",
        },
        success: {
          DEFAULT: "#22c55e",
          light: "#dcfce7",
        },
        warning: {
          DEFAULT: "#f59e0b",
          light: "#fef3c7",
        },
        danger: {
          DEFAULT: "#ef4444",
          light: "#fee2e2",
        },
        muted: {
          DEFAULT: "#64748b",
          foreground: "#94a3b8",
        },
      },
    },
  },
  plugins: [],
};

export default config;
