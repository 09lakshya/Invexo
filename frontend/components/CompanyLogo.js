import { useState } from "react";
import { logoPath } from "../services/stocks";

// Renders a company's official logo (from /public/logos) and gracefully falls
// back to a styled initials badge when the asset is missing or fails to load.
export default function CompanyLogo({ symbol, size = 32, radius = 10, fontSize, style }) {
  const [err, setErr] = useState(false);
  const clean = symbol ? symbol.replace(/\.NS$/i, "").replace(/\.BO$/i, "") : "";
  const url = err ? null : logoPath(clean);
  const initials = clean ? clean.substring(0, 2).toUpperCase() : "??";

  if (url) {
    return (
      <img
        src={url}
        alt={`${clean} logo`}
        onError={() => setErr(true)}
        style={{
          width: size,
          height: size,
          borderRadius: radius,
          border: "1px solid var(--border-medium)",
          background: "#fff",
          objectFit: "contain",
          padding: 2,
          flexShrink: 0,
          ...style,
        }}
      />
    );
  }

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        background: "var(--accent-dim)",
        border: "1px solid var(--accent-glow)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: fontSize || Math.round(size * 0.4),
        fontWeight: 800,
        color: "var(--accent)",
        fontFamily: "'Space Grotesk', sans-serif",
        flexShrink: 0,
        ...style,
      }}
    >
      {initials}
    </div>
  );
}
