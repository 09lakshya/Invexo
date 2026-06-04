import { createContext, useContext, useState, useEffect } from "react";

const WebSocketContext = createContext(null);

export function useWebSocket() {
  return useContext(WebSocketContext);
}

export function WebSocketProvider({ children }) {
  const [stocks, setStocks] = useState({});
  const [prevStocks, setPrevStocks] = useState({});
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let ws;
    let retryTimer;
    let active = true;

    const connect = () => {
      if (!active) return;
      
      const defaultWsUrl = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
        .replace(/^http/, "ws") + "/market/ws";
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || defaultWsUrl;
      
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
  }, []);

  return (
    <WebSocketContext.Provider value={{ stocks, prevStocks, connected }}>
      {children}
    </WebSocketContext.Provider>
  );
}
