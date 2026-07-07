import { createContext, useContext, useState, useEffect, useRef } from "react";
import { useAuth } from "./AuthContext";

const WebSocketContext = createContext(null);

export function useWebSocket() {
  return useContext(WebSocketContext);
}

// Decode a JWT's expiry and tell us if it's expired (or about to be). The
// access token lives only 15 minutes, so a socket that dropped during sleep/
// idle must not reconnect with a stale token — we refresh first.
function isTokenExpired(jwt) {
  try {
    const payload = jwt.split(".")[1];
    const padded = payload.replace(/-/g, "+").replace(/_/g, "/").padEnd(payload.length + (4 - (payload.length % 4)) % 4, "=");
    const { exp } = JSON.parse(atob(padded));
    if (!exp) return false;
    return exp * 1000 - Date.now() < 5000; // expired or < 5s of life left
  } catch {
    return false; // can't decode → let the server be the judge
  }
}

export function WebSocketProvider({ children }) {
  const { token, refreshAccessToken } = useAuth();
  const [stocks, setStocks] = useState({});
  const [prevStocks, setPrevStocks] = useState({});
  const [connected, setConnected] = useState(false);

  // Keep the refresh fn in a ref so it never re-triggers the socket effect
  // (it's a new function reference on every AuthProvider render).
  const refreshRef = useRef(refreshAccessToken);
  useEffect(() => { refreshRef.current = refreshAccessToken; }, [refreshAccessToken]);

  useEffect(() => {
    if (!token) {
      setConnected(false);
      return;
    }

    let ws;
    let retryTimer;
    let active = true;

    const connect = () => {
      if (!active) return;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
      clearTimeout(retryTimer);

      // Never connect with a dead token. Refreshing updates `token` in
      // AuthContext, which re-runs this effect and reconnects with a fresh one.
      // If the refresh fails, AuthContext clears the session and token→null
      // stops the loop cleanly.
      if (isTokenExpired(token)) {
        refreshRef.current?.().catch(() => {});
        return;
      }

      const defaultWsUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
        .replace(/^http/, "ws") + "/market/ws";
      let wsUrl = process.env.NEXT_PUBLIC_WS_URL || defaultWsUrl;

      const separator = wsUrl.includes("?") ? "&" : "?";
      wsUrl = `${wsUrl}${separator}token=${encodeURIComponent(token)}`;

      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (active) setConnected(true);
      };

      ws.onmessage = (e) => {
        if (!active) return;
        try {
          const data = JSON.parse(e.data);
          if (data && data.type === "ping") {
            return;
          }
          setStocks((prev) => {
            setPrevStocks(prev);
            return data;
          });
        } catch (err) {
          console.error("Error parsing websocket message data:", err);
        }
      };

      ws.onclose = () => {
        if (!active) return;
        setConnected(false);
        // connect() will refresh the token first if it has expired.
        retryTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        if (ws) ws.close();
      };
    };

    // When the tab/network comes back after sleep or a long idle, reconnect
    // immediately (refreshing the token if needed) instead of waiting on the
    // retry timer with a possibly-expired token.
    const onWake = () => {
      if (!active) return;
      if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
      if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
      connect();
    };

    connect();
    if (typeof window !== "undefined") {
      window.addEventListener("online", onWake);
      window.addEventListener("focus", onWake);
      document.addEventListener("visibilitychange", onWake);
    }

    return () => {
      active = false;
      clearTimeout(retryTimer);
      if (typeof window !== "undefined") {
        window.removeEventListener("online", onWake);
        window.removeEventListener("focus", onWake);
        document.removeEventListener("visibilitychange", onWake);
      }
      if (ws) ws.close();
    };
  }, [token]);

  return (
    <WebSocketContext.Provider value={{ stocks, prevStocks, connected }}>
      {children}
    </WebSocketContext.Provider>
  );
}
