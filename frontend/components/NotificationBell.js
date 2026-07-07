import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/router";
import API from "../services/api";

const BellIcon = ({ size = 20, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
    <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
  </svg>
);

// Relative time label from a "YYYY-MM-DD HH:MM:SS" server timestamp (UTC-naive).
function timeAgo(ts) {
  if (!ts) return "";
  const then = new Date(ts.replace(" ", "T") + "Z").getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const sectionLabelStyle = {
  padding: "10px 18px 6px",
  fontSize: "0.68rem",
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: "var(--text-muted)",
};

export default function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [items, setItems] = useState([]);
  const [subs, setSubs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const ref = useRef(null);

  // Track the mobile breakpoint (matches the 768px used across the navbar).
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 768px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  const fetchUnread = useCallback(async () => {
    try {
      const res = await API.get("/signal-alerts/notifications/unread-count");
      setUnread(res.data.unread_count || 0);
    } catch (err) {
      // Silent — unauthenticated or transient; the bell just shows no badge.
    }
  }, []);

  const fetchFeed = useCallback(async () => {
    setLoading(true);
    // Pull the fired-signal feed and the user's subscriptions together so the
    // bell shows both what has happened and what they're following. A stock the
    // user just subscribed to shows up under "Following" even before it fires.
    const [feedRes, subsRes] = await Promise.allSettled([
      API.get("/signal-alerts/notifications", { params: { limit: 20 } }),
      API.get("/signal-alerts/subscriptions"),
    ]);
    if (feedRes.status === "fulfilled") {
      setItems(feedRes.value.data.notifications || []);
      setUnread(feedRes.value.data.unread_count || 0);
    } else {
      setItems([]);
    }
    if (subsRes.status === "fulfilled") {
      setSubs(subsRes.value.data || []);
    }
    setLoading(false);
  }, []);

  const removeSub = useCallback(async (sub) => {
    const prev = subs;
    setSubs((list) => list.filter((s) => s.id !== sub.id)); // optimistic
    try {
      await API.delete(`/signal-alerts/subscriptions/${sub.id}`);
    } catch (err) {
      setSubs(prev); // revert on failure
    }
  }, [subs]);

  // Poll the unread badge on mount and every 60s.
  useEffect(() => {
    fetchUnread();
    const id = setInterval(fetchUnread, 60000);
    return () => clearInterval(id);
  }, [fetchUnread]);

  // Close on outside click.
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next) fetchFeed();
  };

  const markAllRead = async () => {
    try {
      await API.post("/signal-alerts/notifications/read-all");
      setUnread(0);
      setItems((prev) => prev.map((n) => ({ ...n, is_read: 1 })));
    } catch (err) {
      /* no-op */
    }
  };

  const openStock = async (n) => {
    if (!n.is_read) {
      try {
        await API.post(`/signal-alerts/notifications/${n.id}/read`);
        setUnread((u) => Math.max(0, u - 1));
        setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: 1 } : x)));
      } catch (err) {
        /* no-op */
      }
    }
    setOpen(false);
    router.push(`/stock/${n.symbol}`);
  };

  const goToStock = (symbol) => {
    setOpen(false);
    router.push(`/stock/${symbol}`);
  };

  return (
    <div ref={ref} style={{ position: "relative", flexShrink: 0 }}>
      <button
        onClick={toggle}
        aria-label="Signal notifications"
        style={{
          position: "relative",
          background: "var(--search-bg)",
          border: "1px solid var(--border-medium)",
          borderRadius: "12px",
          width: "40px",
          height: "40px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          color: "var(--text-secondary)",
          transition: "all 0.2s",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent-glow)"; }}
        onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border-medium)"; }}
      >
        <BellIcon size={18} />
        {unread > 0 && (
          <span
            style={{
              position: "absolute",
              top: "-4px",
              right: "-4px",
              minWidth: "18px",
              height: "18px",
              padding: "0 4px",
              borderRadius: "9px",
              background: "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)",
              color: "#fff",
              fontSize: "0.68rem",
              fontWeight: 800,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 2px 8px var(--accent-glow)",
            }}
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          style={{
            // On mobile the bell sits left of the avatar/menu, so anchoring the
            // wide panel to the bell's right edge overflowed off-screen left.
            // Below 768px, span the viewport with small side margins instead.
            position: isMobile ? "fixed" : "absolute",
            top: isMobile ? "calc(clamp(52px, 8vmin, 64px) + 8px)" : "calc(100% + 8px)",
            ...(isMobile ? { left: "12px", right: "12px" } : { right: 0 }),
            width: isMobile ? "auto" : "min(360px, 92vw)",
            maxHeight: "70vh",
            overflowY: "auto",
            background: "var(--dropdown-bg)",
            border: "1px solid var(--border-medium)",
            borderRadius: "16px",
            boxShadow: "var(--shadow-dropdown)",
            zIndex: 300,
            animation: "fadeInUp 0.2s ease forwards",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "14px 18px",
              borderBottom: "1px solid var(--border-subtle)",
              position: "sticky",
              top: 0,
              background: "var(--dropdown-bg)",
            }}
          >
            <span style={{ fontWeight: 700, color: "var(--text-primary)", fontSize: "0.95rem" }}>
              Buy / Sell signals
            </span>
            {items.some((n) => !n.is_read) && (
              <button
                onClick={markAllRead}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--accent)",
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "inherit",
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          {loading ? (
            <div style={{ padding: "28px 18px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
              Loading…
            </div>
          ) : items.length === 0 && subs.length === 0 ? (
            <div style={{ padding: "28px 18px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.85rem", lineHeight: 1.6 }}>
              No signals yet.<br />
              Subscribe to a stock, or add it to your watchlist or portfolio, to get buy/sell alerts here.
            </div>
          ) : (
            <>
              {items.length > 0 && (
                <>
                  <div style={sectionLabelStyle}>Recent signals</div>
                  {items.map((n) => {
                    const isBuy = n.action === "BUY";
                    const color = isBuy ? "var(--green)" : "var(--red)";
                    const bg = isBuy ? "var(--green-dim)" : "var(--red-dim)";
                    return (
                      <button
                        key={n.id}
                        onClick={() => openStock(n)}
                        style={{
                          width: "100%",
                          display: "flex",
                          gap: "12px",
                          padding: "14px 18px",
                          background: n.is_read ? "transparent" : "var(--hover-overlay)",
                          border: "none",
                          borderBottom: "1px solid var(--border-subtle)",
                          cursor: "pointer",
                          textAlign: "left",
                          fontFamily: "inherit",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--hover-overlay)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = n.is_read ? "transparent" : "var(--hover-overlay)")}
                      >
                        <span
                          style={{
                            flexShrink: 0,
                            alignSelf: "flex-start",
                            marginTop: "2px",
                            padding: "3px 8px",
                            borderRadius: "8px",
                            background: bg,
                            color,
                            fontSize: "0.7rem",
                            fontWeight: 800,
                            letterSpacing: "0.03em",
                          }}
                        >
                          {n.action}
                        </span>
                        <span style={{ flex: 1, minWidth: 0 }}>
                          <span style={{ display: "flex", justifyContent: "space-between", gap: "8px", alignItems: "baseline" }}>
                            <strong style={{ color: "var(--text-primary)", fontSize: "0.88rem" }}>{n.symbol}</strong>
                            <span style={{ color: "var(--text-muted)", fontSize: "0.72rem", flexShrink: 0 }}>{timeAgo(n.created_at)}</span>
                          </span>
                          <span style={{ display: "block", color: "var(--text-muted)", fontSize: "0.78rem", lineHeight: 1.5, marginTop: "3px" }}>
                            {n.message}
                          </span>
                        </span>
                      </button>
                    );
                  })}
                </>
              )}

              {subs.length > 0 && (
                <>
                  <div style={sectionLabelStyle}>Following</div>
                  {subs.map((s) => (
                    <div
                      key={s.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "12px 18px",
                        borderBottom: "1px solid var(--border-subtle)",
                      }}
                    >
                      <button
                        onClick={() => goToStock(s.symbol)}
                        style={{
                          flex: 1,
                          minWidth: 0,
                          display: "flex",
                          flexDirection: "column",
                          gap: "2px",
                          background: "transparent",
                          border: "none",
                          cursor: "pointer",
                          textAlign: "left",
                          fontFamily: "inherit",
                          padding: 0,
                        }}
                      >
                        <strong style={{ color: "var(--text-primary)", fontSize: "0.88rem" }}>{s.symbol}</strong>
                        <span style={{ color: "var(--text-muted)", fontSize: "0.74rem" }}>
                          Alerts at ≥ {s.min_confidence}% confidence
                        </span>
                      </button>
                      <button
                        onClick={() => removeSub(s)}
                        aria-label={`Stop following ${s.symbol}`}
                        title={`Stop following ${s.symbol}`}
                        style={{
                          flexShrink: 0,
                          width: "28px",
                          height: "28px",
                          borderRadius: "8px",
                          border: "1px solid var(--border-subtle)",
                          background: "transparent",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                        onMouseEnter={(e) => { e.currentTarget.style.color = "var(--red)"; e.currentTarget.style.borderColor = "var(--red-dim)"; }}
                        onMouseLeave={(e) => { e.currentTarget.style.color = "var(--text-muted)"; e.currentTarget.style.borderColor = "var(--border-subtle)"; }}
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                          <line x1="6" y1="6" x2="18" y2="18" />
                          <line x1="18" y1="6" x2="6" y2="18" />
                        </svg>
                      </button>
                    </div>
                  ))}
                  <div style={{ padding: "10px 18px 4px", color: "var(--text-muted)", fontSize: "0.72rem", lineHeight: 1.5 }}>
                    Watchlist and portfolio holdings are covered automatically.
                  </div>
                </>
              )}
            </>
          )}

          <div style={{ padding: "10px 18px", textAlign: "center", color: "var(--text-muted)", fontSize: "0.68rem", lineHeight: 1.5 }}>
            Automated model signals, not investment advice.
          </div>
        </div>
      )}
    </div>
  );
}
