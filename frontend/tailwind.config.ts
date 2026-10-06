import type { Config } from "tailwindcss";

// Palette taken from The Date Crew site: warm cream + sand, espresso, bronze/gold accents, deep forest buttons.
// Red / amber / green stay reserved for RED-AMBER-GREEN status (the brand forest is a much darker teal-green).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#faf6ee",
        sand: "#efe6d6",
        espresso: "#1c1815",
        ink: { DEFAULT: "#221c17", soft: "#4a4239", muted: "#7a6f63", faint: "#a99d8e" },
        line: { DEFAULT: "#e9dfce", strong: "#d8cab3" },
        gold: { DEFAULT: "#d3a869", deep: "#9a6a1d" },
        forest: { DEFAULT: "#1f4a3f", dark: "#163830" },
        state: {
          red: { fg: "#9b1c1c", bg: "#fdf0ef", border: "#f3c9c6", solid: "#c62828" },
          amber: { fg: "#8a4b00", bg: "#fff6e5", border: "#f2d9a6", solid: "#d98200" },
          green: { fg: "#14633a", bg: "#eef8f1", border: "#bfe3cc", solid: "#1f8a50" },
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(34,28,23,0.04), 0 4px 14px rgba(34,28,23,0.04)",
        pop: "0 8px 28px rgba(34,28,23,0.10)",
      },
      fontFamily: {
        sans: ['"Inter Variable"', "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        serif: ['"Playfair Display Variable"', "Georgia", "Times New Roman", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
