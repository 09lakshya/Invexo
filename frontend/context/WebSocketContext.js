import { createContext, useContext, useState, useEffect } from "react";
import { useAuth } from "./AuthContext";

const WebSocketContext = createContext(null);

export function useWebSocket() {
  return useContext(WebSocketContext);
}

export function WebSocketProvider({ children }) {
  const { token } = useAuth();
  const [stocks, setStocks] = useState({});
  const [prevStocks, setPrevStocks] = useState({});
  const [connected, setConnected] = useState(false);

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
      
      const defaultWsUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
        .replace(/^http/, "ws") + "/market/ws";
      let wsUrl = process.env.NEXT_PUBLIC_WS_URL || defaultWsUrl;
      
      // Append token query parameter
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
        retryTimer = setTimeout(connect, 5000);
      };

      ws.onerror = () => {
        if (ws) ws.close();
      };
    };

    connect();

    return () => {
      active = false;
      clearTimeout(retryTimer);
      if (ws) ws.close();
    };
  }, [token]);

  return (
    <WebSocketContext.Provider value={{ stocks, prevStocks, connected }}>
      {children}
    </WebSocketContext.Provider>
  );
}
