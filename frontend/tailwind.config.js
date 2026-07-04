/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./pages/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Space Grotesk', 'system-ui', 'sans-serif'],
        display: ['Space Grotesk', 'Inter', 'sans-serif'],
      },
      colors: {
        primary: "#0b0e11",
        secondary: "#181a20",
        accent: "#f5f5f7",
        "accent-light": "#ffffff",
        "green-premium": "#00e676",
        "red-premium": "#ff1744",
        "gold": "#f5f5f7",
        "purple-premium": "#f5f5f7",
        "blue-premium": "#f5f5f7",
      },
      backgroundImage: {
        "gradient-premium": "linear-gradient(135deg, #0b0e11 0%, #181a20 100%)",
        "gradient-card": "linear-gradient(135deg, rgba(24,26,32,0.9) 0%, rgba(11,14,17,0.9) 100%)",
        "gradient-accent": "linear-gradient(135deg, #ffffff 0%, #f5f5f7 100%)",
        "gradient-green": "linear-gradient(135deg, #00e676 0%, #69f0ae 100%)",
        "gradient-red": "linear-gradient(135deg, #ff1744 0%, #ff5252 100%)",
        "gradient-purple": "linear-gradient(135deg, #f5f5f7 0%, #ffffff 100%)",
        "radial-glow": "radial-gradient(ellipse at center, rgba(245, 245, 247,0.15) 0%, transparent 70%)",
      },
      boxShadow: {
        premium: "0 8px 32px rgba(245, 245, 247, 0.08)",
        "premium-lg": "0 20px 64px rgba(245, 245, 247, 0.12)",
        glow: "0 0 20px rgba(245, 245, 247, 0.25)",
        "glow-lg": "0 0 40px rgba(245, 245, 247, 0.35)",
        "glow-green": "0 0 20px rgba(0, 230, 118, 0.3)",
        "glow-red": "0 0 20px rgba(255, 23, 68, 0.3)",
        card: "0 4px 24px rgba(0,0,0,0.5)",
      },
      backdropBlur: {
        xs: "2px",
        card: "20px",
      },
      animation: {
        float: "float 6s ease-in-out infinite",
        "pulse-glow": "pulseGlow 2s ease-in-out infinite",
        "slide-in": "fadeInUp 0.5s ease forwards",
        "fade-in": "fadeIn 0.3s ease forwards",
        "scale-in": "scaleIn 0.3s ease forwards",
        shimmer: "shimmer 1.5s infinite",
        spin: "spin 0.7s linear infinite",
        ticker: "ticker 40s linear infinite",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%":       { transform: "translateY(-10px)" },
        },
        pulseGlow: {
          "0%, 100%": { opacity: "1" },
          "50%":       { opacity: "0.6" },
        },
        fadeInUp: {
          from: { opacity: "0", transform: "translateY(24px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        scaleIn: {
          from: { opacity: "0", transform: "scale(0.95)" },
          to:   { opacity: "1", transform: "scale(1)" },
        },
        shimmer: {
          "0%":   { backgroundPosition: "-800px 0" },
          "100%": { backgroundPosition: "800px 0" },
        },
        ticker: {
          "0%":   { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      transitionTimingFunction: {
        premium: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      borderRadius: {
        card: "20px",
        xl: "16px",
        "2xl": "20px",
        "3xl": "28px",
      },
    },
  },
  plugins: [],
};
