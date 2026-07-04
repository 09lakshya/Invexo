import { useState, useRef, useEffect } from "react";
import API from "../services/api";

export default function VexoWidget() {
  const [showCopilot, setShowCopilot] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatHistory, setChatHistory] = useState([
    {
      sender: "copilot",
      text: "👋 **Hello! I'm Vexo, your AI investment assistant.**\n\nI can run AI **predictions**, pull today's **Daily Edge** picks, analyze your **portfolio & watchlist**, fetch **news**, and even set **price alerts** for you. What would you like to do?",
    },
  ]);
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Scroll to bottom of chat when new messages arrive
  useEffect(() => {
    if (showCopilot && chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatHistory, showCopilot]);

  const sendCopilotMessage = async () => {
    if (!chatInput.trim()) return;
    const msg = chatInput;
    setChatInput("");
    // Send the recent conversation so Vexo has memory of the dialogue.
    const priorHistory = chatHistory
      .slice(-10)
      .map((m) => ({ sender: m.sender, text: m.text }));
    setChatHistory((prev) => [...prev, { sender: "user", text: msg }]);
    setChatLoading(true);
    try {
      const res = await API.post("/copilot/chat", { message: msg, history: priorHistory });
      setChatHistory((prev) => [...prev, { sender: "copilot", text: res.data.response }]);
    } catch (err) {
      setChatHistory((prev) => [
        ...prev,
        { sender: "copilot", text: "⚠️ Failed to get response. Please try again." },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const formatCopilotText = (text) => {
    if (!text) return "";
    return text.split("\n").map((line, idx) => {
      if (line.startsWith("### ")) {
        return (
          <h4
            key={idx}
            style={{
              margin: "14px 0 6px 0",
              fontSize: "1rem",
              fontWeight: 800,
              fontFamily: "Space Grotesk, sans-serif",
              color: "var(--accent)",
            }}
          >
            {line.replace("### ", "")}
          </h4>
        );
      }
      if (line.startsWith("## ")) {
        return (
          <h3
            key={idx}
            style={{
              margin: "16px 0 8px 0",
              fontSize: "1.1rem",
              fontWeight: 800,
              fontFamily: "Space Grotesk, sans-serif",
              color: "var(--accent)",
            }}
          >
            {line.replace("## ", "")}
          </h3>
        );
      }
      if (line.startsWith("* ")) {
        const parts = line.replace("* ", "").split(/\*\*(.*?)\*\//g);
        const parsed = parts.map((part, i) =>
          i % 2 === 1 ? (
            <strong key={i} style={{ color: "var(--accent)", fontWeight: 700 }}>
              {part}
            </strong>
          ) : (
            part
          )
        );
        return (
          <li
            key={idx}
            style={{
              marginLeft: "14px",
              listStyleType: "disc",
              fontSize: "0.85rem",
              lineHeight: "1.5",
              marginBottom: "4px",
            }}
          >
            {parsed}
          </li>
        );
      }
      // Simple regex bold replacement (split by **)
      const parts = line.split(/\*\*(.*?)\*\*/g);
      const content = parts.map((part, i) =>
        i % 2 === 1 ? (
          <strong key={i} style={{ color: "var(--text-primary)", fontWeight: 700 }}>
            {part}
          </strong>
        ) : (
          part
        )
      );
      return (
        <p
          key={idx}
          style={{
            margin: "6px 0",
            fontSize: "0.85rem",
            lineHeight: "1.5",
            color: "var(--text-secondary)",
          }}
        >
          {content}
        </p>
      );
    });
  };

  return (
    <>
      <style jsx>{`
        .vexo-drawer {
          max-width: 400px;
        }
        .vexo-fab {
          bottom: 24px;
        }
        @media (max-width: 600px) {
          .vexo-drawer {
            max-width: 100% !important;
          }
          .vexo-fab {
            bottom: 80px !important;
          }
        }
      `}</style>

      {/* Floating Action Button */}
      <button
        className="vexo-fab"
        onClick={() => setShowCopilot((prev) => !prev)}
        style={{
          position: "fixed",
          right: "24px",
          width: "60px",
          height: "60px",
          borderRadius: "30px",
          background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%)",
          color: "var(--bg-primary)",
          border: "none",
          boxShadow: "0 8px 24px rgba(0, 200, 150, 0.4)",
          cursor: "pointer",
          zIndex: 9999,
          display: showCopilot ? "none" : "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: "1.8rem",
          transition: "transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)",
          transform: showCopilot ? "scale(0.8)" : "scale(1)",
        }}
        aria-label="Toggle Vexo AI Assistant"
        onMouseEnter={(e) => (e.currentTarget.style.transform = showCopilot ? "scale(0.8)" : "scale(1.05)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = showCopilot ? "scale(0.8)" : "scale(1)")}
      >
        {showCopilot ? "✕" : "💬"}
      </button>

      {/* Vexo Drawer / Modal */}
      <div
        className="vexo-drawer"
        style={{
          position: "fixed",
          top: "0",
          right: "0",
          width: "100%",
          height: "100%",
          background: "var(--bg-primary)",
          borderLeft: "1px solid var(--border-subtle)",
          boxShadow: "-10px 0 30px rgba(0,0,0,0.5)",
          transform: showCopilot ? "translateX(0)" : "translateX(100%)",
          transition: "transform 0.4s cubic-bezier(0.22, 1, 0.36, 1)",
          zIndex: 9998,
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px",
            borderBottom: "1px solid var(--border-subtle)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "rgba(255, 255, 255, 0.02)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "12px",
                background: "linear-gradient(135deg, var(--accent) 0%, var(--accent-light) 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--bg-primary)",
                fontSize: "1.2rem",
              }}
            >
              🤖
            </div>
            <div>
              <h3
                style={{
                  fontFamily: "'Space Grotesk', sans-serif",
                  fontSize: "1.1rem",
                  fontWeight: 800,
                  margin: 0,
                  color: "var(--text-primary)",
                }}
              >
                Vexo
              </h3>
              <p style={{ margin: 0, fontSize: "0.75rem", color: "var(--text-muted)" }}>
                AI Investment Assistant
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCopilot(false)}
            style={{
              background: "var(--bg-secondary)",
              border: "none",
              width: "32px",
              height: "32px",
              borderRadius: "50%",
              color: "var(--text-secondary)",
              cursor: "pointer",
              fontSize: "1rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            aria-label="Close Vexo"
          >
            ✕
          </button>
        </div>

        {/* Chat History */}
        <div style={{ flex: 1, overflowY: "auto", padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
          {chatHistory.map((msg, i) => (
            <div
              key={i}
              style={{
                alignSelf: msg.sender === "user" ? "flex-end" : "flex-start",
                maxWidth: "85%",
                animation: "fadeIn 0.3s ease",
              }}
            >
              <div
                style={{
                  background: msg.sender === "user" ? "var(--accent)" : "var(--bg-secondary)",
                  color: msg.sender === "user" ? "var(--bg-primary)" : "var(--text-primary)",
                  padding: "12px 16px",
                  borderRadius: msg.sender === "user" ? "18px 18px 0 18px" : "18px 18px 18px 0",
                  border: msg.sender === "copilot" ? "1px solid var(--border-medium)" : "none",
                  boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
                }}
              >
                {msg.sender === "copilot" ? formatCopilotText(msg.text) : <p style={{ margin: 0, fontSize: "0.9rem", fontWeight: 600 }}>{msg.text}</p>}
              </div>
              <p
                style={{
                  fontSize: "0.65rem",
                  color: "var(--text-muted)",
                  margin: "6px 4px 0",
                  textAlign: msg.sender === "user" ? "right" : "left",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                }}
              >
                {msg.sender === "user" ? "You" : "Vexo AI"}
              </p>
            </div>
          ))}
          {chatLoading && (
            <div style={{ alignSelf: "flex-start", maxWidth: "85%" }}>
              <div
                style={{
                  background: "var(--bg-secondary)",
                  padding: "12px 16px",
                  borderRadius: "18px 18px 18px 0",
                  border: "1px solid var(--border-medium)",
                  display: "flex",
                  gap: "6px",
                  alignItems: "center",
                }}
              >
                <div className="spinner" style={{ width: "16px", height: "16px", borderWidth: "2px", borderColor: "var(--accent) transparent var(--accent) transparent" }}></div>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Analyzing...</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Chat Input */}
        <div style={{ padding: "20px 24px", borderTop: "1px solid var(--border-subtle)", background: "var(--bg-primary)" }}>
          <div style={{ display: "flex", gap: "10px", position: "relative" }}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendCopilotMessage()}
              placeholder="Ask for a prediction, picks, or analysis..."
              style={{
                flex: 1,
                background: "var(--input-bg)",
                color: "var(--text-primary)",
                border: "1px solid var(--border-medium)",
                padding: "14px 16px",
                borderRadius: "12px",
                fontSize: "0.9rem",
                outline: "none",
                fontFamily: "inherit",
              }}
              disabled={chatLoading}
            />
            <button
              onClick={sendCopilotMessage}
              disabled={chatLoading || !chatInput.trim()}
              style={{
                flexShrink: 0,
                width: "46px",
                height: "46px",
                background: chatInput.trim() ? "var(--accent)" : "var(--bg-secondary)",
                color: chatInput.trim() ? "var(--bg-primary)" : "var(--text-muted)",
                border: "none",
                borderRadius: "12px",
                cursor: chatInput.trim() && !chatLoading ? "pointer" : "not-allowed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s",
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            </button>
          </div>
          <p style={{ fontSize: "0.65rem", color: "var(--text-muted)", textAlign: "center", marginTop: "12px" }}>
            Vexo can run AI predictions, analyze your portfolio, and take actions like setting alerts.
          </p>
        </div>
      </div>
    </>
  );
}
