/**
 * Icon — Invexo's line-icon set.
 *
 * A single, consistent set of stroke-based SVG icons (Lucide/Feather style)
 * that replaces the emoji previously scattered through the UI. Every icon
 * draws with `currentColor`, so it inherits the surrounding text color
 * (accent gold, green, red, muted, …) and both themes automatically.
 *
 * Usage:  <Icon name="target" />            // 1em, inherits color
 *         <Icon name="bell" size={18} />
 *         <Icon name="star" filled color="var(--accent)" />
 */

// Each entry is the inner markup of a 24×24 viewBox icon.
const PATHS = {
  // ── Markets / analytics ──────────────────────────────────────────
  "bar-chart": <><line x1="6" y1="20" x2="6" y2="12" /><line x1="12" y1="20" x2="12" y2="6" /><line x1="18" y1="20" x2="18" y2="14" /></>,
  "trending-up": <><polyline points="3 17 9 11 13 15 21 7" /><polyline points="15 7 21 7 21 13" /></>,
  "trending-down": <><polyline points="3 7 9 13 13 9 21 17" /><polyline points="15 17 21 17 21 11" /></>,
  activity: <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />,
  target: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" /></>,
  rocket: <><path d="M5 15c-1.5 1.5-2 5-2 5s3.5-.5 5-2c.8-.8.8-2.2 0-3s-2.2-.8-3 0Z" /><path d="M9 12a12 12 0 0 1 8-8 12 12 0 0 1 2 8 12 12 0 0 1-8 8" /><path d="M9 12 6.5 9.5M12 15l2.5 2.5" /><circle cx="14.5" cy="9.5" r="1.5" /></>,
  fire: <path d="M12 2s4 3.5 4 8a4 4 0 0 1-8 0c0-1 .3-1.8.8-2.5C8 9 7 11 7 13a5 5 0 0 0 10 0c0-4.5-5-11-5-11Z" />,
  gauge: <><path d="M12 14 15 9" /><circle cx="12" cy="14" r="1" /><path d="M4 18a8 8 0 1 1 16 0" /></>,

  // ── Finance ──────────────────────────────────────────────────────
  wallet: <><path d="M3 7a2 2 0 0 1 2-2h13a1 1 0 0 1 1 1v3" /><path d="M3 7v10a2 2 0 0 0 2 2h14a1 1 0 0 0 1-1v-3" /><path d="M20 10h-4a2 2 0 0 0 0 4h4a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1Z" /></>,
  briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /><line x1="3" y1="12" x2="21" y2="12" /></>,
  coins: <><circle cx="9" cy="9" r="6" /><path d="M15.5 3.6a6 6 0 0 1 0 10.8" /><path d="M8 21h8" /></>,
  shield: <path d="M12 3 5 6v5c0 4 3 7.5 7 9 4-1.5 7-5 7-9V6l-7-3Z" />,

  // ── Goals ────────────────────────────────────────────────────────
  graduation: <><path d="M12 4 2 9l10 5 10-5-10-5Z" /><path d="M6 11v4c0 1.5 3 3 6 3s6-1.5 6-3v-4" /></>,
  umbrella: <><path d="M12 3a9 9 0 0 1 9 9H3a9 9 0 0 1 9-9Z" /><path d="M12 12v6a2.5 2.5 0 0 0 5 0" /></>,
  calendar: <><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="16" y1="2" x2="16" y2="6" /></>,

  // ── Actions / UI ─────────────────────────────────────────────────
  search: <><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" /></>,
  bell: <><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6Z" /><path d="M10.5 20a1.8 1.8 0 0 0 3 0" /></>,
  bulb: <><path d="M9 18h6" /><path d="M10 21h4" /><path d="M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.2 1 2.5h6c0-1.3.3-1.8 1-2.5A6 6 0 0 0 12 3Z" /></>,
  chat: <path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-6.4A8 8 0 1 1 21 12Z" />,
  bot: <><rect x="4" y="8" width="16" height="12" rx="3" /><path d="M12 4v4" /><circle cx="12" cy="4" r="1" /><line x1="9" y1="13" x2="9" y2="15" /><line x1="15" y1="13" x2="15" y2="15" /></>,
  sparkle: <path d="M12 3l1.9 5.6L19.5 10.5 13.9 12.4 12 18l-1.9-5.6L4.5 10.5l5.6-1.9L12 3Z" />,
  folder: <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />,
  news: <><path d="M4 5h13a1 1 0 0 1 1 1v12a1 1 0 0 0 1 1 1 1 0 0 0 1-1V8" /><path d="M4 5a1 1 0 0 0-1 1v12a2 2 0 0 0 2 2h13" /><line x1="7" y1="9" x2="14" y2="9" /><line x1="7" y1="13" x2="14" y2="13" /><line x1="7" y1="17" x2="11" y2="17" /></>,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
  hand: <path d="M18 11V6a1.5 1.5 0 0 0-3 0V5a1.5 1.5 0 0 0-3 0 1.5 1.5 0 0 0-3 0v6l-1.5-2a1.5 1.5 0 0 0-2.5 1.6L7 16a5 5 0 0 0 5 4 5 5 0 0 0 5-5v-1a1.5 1.5 0 0 0-3 0" />,

  // ── Glyphs ───────────────────────────────────────────────────────
  x: <><line x1="6" y1="6" x2="18" y2="18" /><line x1="18" y1="6" x2="6" y2="18" /></>,
  plus: <><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></>,
  menu: <><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></>,
  check: <polyline points="20 6 9 17 4 12" />,
  alert: <><path d="M12 3 2 20h20L12 3Z" /><line x1="12" y1="10" x2="12" y2="14" /><line x1="12" y1="17.5" x2="12" y2="17.5" /></>,
  star: <path d="M12 3l2.7 5.9 6.3.7-4.7 4.3 1.3 6.2L12 17.8 6.1 20.4l1.3-6.2L2.7 9.9l6.3-.7L12 3Z" />,
};

export default function Icon({
  name,
  size = "1em",
  color,
  filled = false,
  strokeWidth = 2,
  className = "",
  style = {},
  ...rest
}) {
  const inner = PATHS[name];
  if (!inner) return null;

  // The star is the only glyph that reads better filled.
  const isFillable = name === "star";
  const fill = isFillable && filled ? "currentColor" : "none";

  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill={fill}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
      style={{
        display: "inline-block",
        flexShrink: 0,
        verticalAlign: "text-bottom",
        color,
        ...style,
      }}
      {...rest}
    >
      {inner}
    </svg>
  );
}
