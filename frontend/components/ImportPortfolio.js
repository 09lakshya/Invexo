import { useState, useRef } from "react";
import API from "../services/api";
import Icon from "./Icon";

// Brokers we can import from. `auto` is the catch-all for any other broker's
// CSV/XLSX export — the backend parser detects columns fuzzily.
const BROKERS = [
  { id: "zerodha", name: "Zerodha", hint: "Console → Holdings → Download", color: "#387ed1" },
  { id: "groww", name: "Groww", hint: "Stocks → Holdings → Export", color: "#00b386" },
  { id: "angelone", name: "Angel One", hint: "Portfolio → Holdings → Export", color: "#e83e3e" },
  { id: "upstox", name: "Upstox", hint: "Holdings → Download report", color: "#eb5b25" },
  { id: "auto", name: "Other broker", hint: "Any holdings CSV / XLSX", color: "var(--purple)" },
];

const overlayStyle = {
  position: "fixed", inset: 0, zIndex: 1000,
  background: "rgba(0,0,0,0.6)", backdropFilter: "blur(6px)",
  display: "flex", alignItems: "center", justifyContent: "center",
  padding: "clamp(12px, 3vmin, 32px)",
};

const cardStyle = {
  background: "var(--bg-card)", border: "1px solid var(--border-medium)",
  borderRadius: "clamp(16px, 2.5vmin, 22px)", width: "min(760px, 100%)",
  maxHeight: "90vh", display: "flex", flexDirection: "column",
  boxShadow: "0 24px 80px rgba(0,0,0,0.5)", overflow: "hidden",
};

const cellInput = {
  width: "100%", background: "var(--input-bg)", border: "1px solid var(--border-subtle)",
  borderRadius: "8px", padding: "7px 9px", color: "var(--text-primary)",
  fontSize: "0.82rem", fontFamily: "inherit", outline: "none",
};

function isValidRow(r) {
  return r.symbol && r.symbol.trim() && Number(r.quantity) > 0 && Number(r.buy_price) > 0;
}

export default function ImportPortfolio({ open, onClose, onImported }) {
  const [broker, setBroker] = useState(null);
  const [rows, setRows] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [fileName, setFileName] = useState("");
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef(null);

  if (!open) return null;

  const reset = () => {
    setBroker(null); setRows([]); setWarnings([]); setFileName("");
    setError(""); setLoading(false); setCommitting(false);
  };
  const close = () => { reset(); onClose(); };

  const handleFile = async (file) => {
    if (!file) return;
    const okExt = /\.(csv|xlsx|xls|txt)$/i.test(file.name);
    if (!okExt) { setError("Please upload a CSV or XLSX holdings export."); return; }
    setError(""); setLoading(true); setFileName(file.name);
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("broker", broker?.id || "auto");
      const res = await API.post("/portfolio/import/preview", fd);
      setRows((res.data.rows || []).map((r, i) => ({ ...r, _id: i })));
      setWarnings(res.data.warnings || []);
    } catch (e) {
      setError(e?.response?.data?.detail || "Could not read this file. Try a CSV export.");
      setFileName("");
    } finally {
      setLoading(false);
    }
  };

  const updateRow = (id, field, value) =>
    setRows(rs => rs.map(r => r._id === id ? { ...r, [field]: value } : r));
  const removeRow = (id) => setRows(rs => rs.filter(r => r._id !== id));

  const validRows = rows.filter(isValidRow);
  const canImport = validRows.length > 0 && !committing;

  const commit = async () => {
    setCommitting(true); setError("");
    try {
      const holdings = validRows.map(r => ({
        symbol: r.symbol.trim().toUpperCase(),
        company_name: r.company_name || r.symbol,
        quantity: Number(r.quantity),
        buy_price: Number(r.buy_price),
      }));
      const res = await API.post("/portfolio/import/commit", { holdings });
      onImported?.(res.data.imported);
      close();
    } catch (e) {
      setError(e?.response?.data?.detail || "Import failed. Please try again.");
      setCommitting(false);
    }
  };

  const hasPreview = rows.length > 0;

  return (
    <div style={overlayStyle} onClick={close}>
      <div style={cardStyle} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "clamp(16px, 2.5vmin, 22px) clamp(18px, 3vmin, 26px)", borderBottom: "1px solid var(--border-subtle)" }}>
          <div>
            <p className="section-label">Import Portfolio</p>
            <h2 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "clamp(1.1rem, 2.4vmin, 1.5rem)", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
              {hasPreview ? "Review & confirm" : "Upload a broker statement"}
            </h2>
          </div>
          <button onClick={close} aria-label="Close" style={{ background: "var(--input-bg)", border: "1px solid var(--border-subtle)", borderRadius: "10px", width: 36, height: 36, cursor: "pointer", color: "var(--text-secondary)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "clamp(16px, 3vmin, 24px)", overflowY: "auto" }}>
          {!hasPreview ? (
            <>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginBottom: "16px" }}>
                Direct broker login is coming soon. For now, export your holdings from your broker and drop the file below — we'll read it and let you review before importing.
              </p>

              {/* Broker picker */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "10px", marginBottom: "20px" }}>
                {BROKERS.map(b => {
                  const active = broker?.id === b.id;
                  return (
                    <button
                      key={b.id}
                      onClick={() => setBroker(b)}
                      style={{
                        textAlign: "left", cursor: "pointer",
                        background: active ? "var(--hover-overlay)" : "var(--input-bg)",
                        border: `1.5px solid ${active ? b.color : "var(--border-subtle)"}`,
                        borderRadius: "12px", padding: "12px 14px", transition: "all 0.2s",
                      }}
                    >
                      <span style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                        <span style={{ width: 9, height: 9, borderRadius: "50%", background: b.color, flexShrink: 0 }} />
                        <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--text-primary)" }}>{b.name}</span>
                      </span>
                      <span style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{b.hint}</span>
                    </button>
                  );
                })}
              </div>

              {/* Dropzone */}
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files?.[0]); }}
                onClick={() => fileRef.current?.click()}
                style={{
                  border: `2px dashed ${dragOver ? "var(--accent)" : "var(--border-medium)"}`,
                  borderRadius: "16px", padding: "clamp(24px, 5vmin, 44px)", textAlign: "center",
                  cursor: "pointer", background: dragOver ? "var(--hover-overlay)" : "transparent",
                  transition: "all 0.2s",
                }}
              >
                <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls,.txt" style={{ display: "none" }}
                  onChange={e => handleFile(e.target.files?.[0])} />
                {loading ? (
                  <><div className="spinner" style={{ margin: "0 auto 12px" }} /><p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>Reading {fileName}…</p></>
                ) : (
                  <>
                    <p style={{ color: "var(--accent)", display: "flex", justifyContent: "center", marginBottom: "10px" }}><Icon name="upload" size={30} strokeWidth={1.5} /></p>
                    <p style={{ fontWeight: 700, color: "var(--text-primary)", marginBottom: "4px" }}>
                      Drop your {broker ? broker.name : "broker"} statement here
                    </p>
                    <p style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>or click to browse · CSV or XLSX</p>
                  </>
                )}
              </div>
            </>
          ) : (
            <>
              {warnings.length > 0 && (
                <div style={{ background: "var(--gold-dim, rgba(245,190,80,0.12))", border: "1px solid var(--gold, #f5be50)", borderRadius: "12px", padding: "10px 14px", marginBottom: "16px" }}>
                  {warnings.map((w, i) => (
                    <p key={i} style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "flex", gap: "8px", alignItems: "flex-start" }}>
                      <Icon name="alert" size={14} /> {w}
                    </p>
                  ))}
                </div>
              )}
              <p style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginBottom: "12px" }}>
                {validRows.length} of {rows.length} holdings ready. Fix any highlighted rows — symbol, quantity and price are all required.
              </p>

              <div style={{ overflowX: "auto", border: "1px solid var(--border-subtle)", borderRadius: "12px" }}>
                <table style={{ width: "100%", minWidth: "540px", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: "var(--input-bg)" }}>
                      {["Symbol", "Company", "Qty", "Avg price", ""].map((h, i) => (
                        <th key={i} style={{ textAlign: i > 1 && i < 4 ? "right" : "left", padding: "9px 10px", fontSize: "0.68rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(r => {
                      const invalid = !isValidRow(r);
                      return (
                        <tr key={r._id} style={{ borderTop: "1px solid var(--border-subtle)", background: invalid ? "var(--red-dim, rgba(240,80,80,0.08))" : "transparent" }}>
                          <td style={{ padding: "6px 8px", width: "22%" }}>
                            <input value={r.symbol} onChange={e => updateRow(r._id, "symbol", e.target.value.toUpperCase())} placeholder="TICKER" style={{ ...cellInput, borderColor: r.symbol ? "var(--border-subtle)" : "var(--red, #f05050)", fontWeight: 700 }} />
                          </td>
                          <td style={{ padding: "6px 8px", width: "34%" }}>
                            <input value={r.company_name || ""} onChange={e => updateRow(r._id, "company_name", e.target.value)} placeholder="Company" style={cellInput} />
                          </td>
                          <td style={{ padding: "6px 8px", width: "16%" }}>
                            <input type="number" min="0" step="any" value={r.quantity} onChange={e => updateRow(r._id, "quantity", e.target.value)} style={{ ...cellInput, textAlign: "right" }} />
                          </td>
                          <td style={{ padding: "6px 8px", width: "20%" }}>
                            <input type="number" min="0" step="any" value={r.buy_price} onChange={e => updateRow(r._id, "buy_price", e.target.value)} style={{ ...cellInput, textAlign: "right" }} />
                          </td>
                          <td style={{ padding: "6px 8px", textAlign: "center" }}>
                            <button onClick={() => removeRow(r._id)} aria-label="Remove row" style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--text-muted)", display: "flex" }}>
                              <Icon name="trash" size={15} />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {error && (
            <p style={{ marginTop: "14px", color: "var(--red, #f05050)", fontSize: "0.82rem", display: "flex", gap: "8px", alignItems: "center" }}>
              <Icon name="alert" size={14} /> {error}
            </p>
          )}
        </div>

        {/* Footer */}
        {hasPreview && (
          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", padding: "clamp(14px, 2.5vmin, 20px) clamp(18px, 3vmin, 26px)", borderTop: "1px solid var(--border-subtle)" }}>
            <button onClick={() => { setRows([]); setWarnings([]); setFileName(""); }} style={{ padding: "11px 18px", borderRadius: "12px", border: "1px solid var(--border-subtle)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer", fontFamily: "inherit", fontWeight: 600, fontSize: "0.85rem" }}>
              Choose another file
            </button>
            <button onClick={commit} disabled={!canImport} style={{ padding: "11px 26px", borderRadius: "12px", border: "none", cursor: canImport ? "pointer" : "not-allowed", opacity: canImport ? 1 : 0.5, fontFamily: "inherit", fontWeight: 700, fontSize: "0.9rem", background: "linear-gradient(135deg, var(--accent), var(--purple))", color: "var(--bg-primary)", boxShadow: canImport ? "0 6px 24px var(--accent-glow)" : "none" }}>
              {committing ? "Importing…" : `Import ${validRows.length} holding${validRows.length !== 1 ? "s" : ""}`}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
