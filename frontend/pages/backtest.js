import React, { useState, useEffect } from "react";
import Head from "next/head";
import Navbar from "../components/Navbar";
import API from "../services/api";
import {
  Chart as ChartJS, LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Filler);

function StatTile({ label, value, sub, positive }) {
  return (
    <div className="glass" style={{ padding: "16px 18px", flex: "1 1 140px", minWidth: "140px", boxShadow: "var(--shadow-card)" }}>
      <div style={{ fontSize: "0.66rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-muted)", marginBottom: "6px" }}>{label}</div>
      <div style={{ fontSize: "1.3rem", fontWeight: 800, fontFamily: "'Space Grotesk', sans-serif", color: positive === undefined ? "var(--text-primary)" : positive ? "var(--green)" : "var(--red)" }}>{value}</div>
      {sub && <div style={{ fontSize: "0.68rem", color: "var(--text-muted)", marginTop: "4px" }}>{sub}</div>}
    </div>
  );
}

const inputStyle = {
  padding: "8px 12px", borderRadius: "10px", border: "1px solid var(--border-medium)",
  background: "var(--search-bg)", color: "var(--text-primary)", fontSize: "0.82rem",
  fontFamily: "inherit", outline: "none", width: "100%",
};

function Field({ label, children, hint }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "5px", flex: "1 1 140px", minWidth: "130px" }}>
      <label style={{ fontSize: "0.64rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--text-muted)" }}>{label}</label>
      {children}
      {hint && <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", opacity: 0.7 }}>{hint}</span>}
    </div>
  );
}

function pct(v) { return v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v}%`; }

const lineOptions = (fmt) => ({
  responsive: true, maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  plugins: { legend: { display: false }, tooltip: { enabled: true } },
  scales: {
    y: { grid: { color: "var(--border-subtle)" }, ticks: { color: "var(--text-secondary)", callback: fmt } },
    x: { grid: { display: false }, ticks: { color: "var(--text-secondary)", maxTicksLimit: 8, autoSkip: true } },
  },
  elements: { point: { radius: 0, hoverRadius: 5 } },
});

export default function BacktestPage() {
  const [cfg, setCfg] = useState(null);
  const [form, setForm] = useState({
    symbols: "RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK",
    start: "", end: "", holding_days: 3, initial_capital: 100000, trade_fraction: 0.1, n_folds: 4,
  });
  const [costs, setCosts] = useState({});
  const [showCosts, setShowCosts] = useState(false);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    API.get("/backtest/config").then((r) => {
      setCfg(r.data);
      setCosts(r.data.cost_model_defaults);
    }).catch(() => {});
  }, []);

  const run = async () => {
    setLoading(true); setError(null); setResult(null);
    const symbols = form.symbols.split(",").map((s) => s.trim()).filter(Boolean);
    const cost_overrides = {};
    if (cfg) {
      Object.entries(costs).forEach(([k, v]) => {
        if (k in cfg.cost_model_defaults && Number(v) !== cfg.cost_model_defaults[k]) cost_overrides[k] = Number(v);
      });
    }
    try {
      const r = await API.post("/backtest/run", {
        symbols, start: form.start || null, end: form.end || null,
        holding_days: Number(form.holding_days), initial_capital: Number(form.initial_capital),
        trade_fraction: Number(form.trade_fraction), n_folds: Number(form.n_folds), cost_overrides,
      });
      if (r.data.error) setError(r.data.error);
      else setResult(r.data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Backtest failed.");
    } finally {
      setLoading(false);
    }
  };

  const m = result?.metrics;
  const equityData = result && {
    labels: result.equity_curve.map((p) => p.date),
    datasets: [{ data: result.equity_curve.map((p) => p.equity), borderColor: "var(--accent)", backgroundColor: "var(--accent-dim)", borderWidth: 2, tension: 0.2, fill: true }],
  };
  const ddData = result && {
    labels: result.drawdown_curve.map((p) => p.date),
    datasets: [{ data: result.drawdown_curve.map((p) => p.drawdown_pct), borderColor: "var(--red)", backgroundColor: "var(--red-dim)", borderWidth: 2, tension: 0.2, fill: true }],
  };

  const COST_KEYS = cfg ? Object.keys(cfg.cost_model_defaults).filter((k) => k !== "slippage_rate") : [];

  return (
    <>
      <Head><title>Backtest | Invexo</title></Head>
      <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }}>
        <Navbar />
        <div className="page-wrapper" style={{ marginTop: "20px" }}>
          <div style={{ textAlign: "center", marginBottom: "24px" }} className="animate-fadeInUp">
            <h1 style={{ fontFamily: "'Space Grotesk', sans-serif", fontSize: "clamp(2rem, 5vmin, 3rem)", fontWeight: 800, letterSpacing: "-0.02em", marginBottom: "10px" }}>
              Walk-Forward <span className="text-gradient">Backtest</span>
            </h1>
            <p style={{ color: "var(--text-muted)", fontSize: "0.95rem", maxWidth: "660px", margin: "0 auto" }}>
              Replays the technical consensus on historical NSE data with honest costs. Walk-forward only — the confidence threshold is calibrated on the past and tested out-of-sample. No in-sample results are shown.
            </p>
          </div>

          {/* Config panel */}
          <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)", marginBottom: "20px" }}>
            <div style={{ display: "flex", gap: "14px", flexWrap: "wrap", marginBottom: "14px" }}>
              <Field label="Symbols (comma-separated)"><input style={inputStyle} value={form.symbols} onChange={(e) => setForm((f) => ({ ...f, symbols: e.target.value }))} /></Field>
              <Field label="From"><input type="date" style={inputStyle} value={form.start} onChange={(e) => setForm((f) => ({ ...f, start: e.target.value }))} /></Field>
              <Field label="To"><input type="date" style={inputStyle} value={form.end} onChange={(e) => setForm((f) => ({ ...f, end: e.target.value }))} /></Field>
            </div>
            <div style={{ display: "flex", gap: "14px", flexWrap: "wrap" }}>
              <Field label="Holding days" hint="1–20"><input type="number" min={1} max={20} style={inputStyle} value={form.holding_days} onChange={(e) => setForm((f) => ({ ...f, holding_days: e.target.value }))} /></Field>
              <Field label="Initial capital (₹)"><input type="number" style={inputStyle} value={form.initial_capital} onChange={(e) => setForm((f) => ({ ...f, initial_capital: e.target.value }))} /></Field>
              <Field label="Trade fraction" hint="of equity/trade"><input type="number" step="0.01" min={0.01} max={1} style={inputStyle} value={form.trade_fraction} onChange={(e) => setForm((f) => ({ ...f, trade_fraction: e.target.value }))} /></Field>
              <Field label="Walk-forward folds" hint="2–8"><input type="number" min={2} max={8} style={inputStyle} value={form.n_folds} onChange={(e) => setForm((f) => ({ ...f, n_folds: e.target.value }))} /></Field>
            </div>

            {/* Cost assumptions */}
            <button onClick={() => setShowCosts((s) => !s)} style={{ marginTop: "14px", background: "transparent", border: "none", color: "var(--accent)", fontWeight: 700, fontSize: "0.8rem", cursor: "pointer", fontFamily: "inherit" }}>
              {showCosts ? "▾" : "▸"} Cost assumptions {showCosts ? "" : "(defaults: NSE delivery + 10bps slippage)"}
            </button>
            {showCosts && cfg && (
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginTop: "12px", padding: "12px", background: "var(--surface-hover)", borderRadius: "12px" }}>
                {COST_KEYS.map((k) => (
                  <Field key={k} label={k.replace(/_/g, " ")} hint={cfg.cost_model_docs?.[k]}>
                    <input type="number" step="any" style={inputStyle} value={costs[k]} onChange={(e) => setCosts((c) => ({ ...c, [k]: e.target.value }))} />
                  </Field>
                ))}
              </div>
            )}

            <div style={{ marginTop: "16px" }}>
              <button onClick={run} disabled={loading} style={{ padding: "10px 28px", borderRadius: "12px", border: "none", background: "linear-gradient(135deg, var(--accent) 0%, var(--purple) 100%)", color: "var(--bg-primary)", fontWeight: 800, fontSize: "0.9rem", cursor: loading ? "wait" : "pointer", fontFamily: "inherit", opacity: loading ? 0.7 : 1 }}>
                {loading ? "Running walk-forward…" : "Run Backtest"}
              </button>
            </div>
          </div>

          {error && (
            <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)", borderLeft: "3px solid var(--red)", marginBottom: "20px" }}>
              <p style={{ color: "var(--red)", fontWeight: 600, fontSize: "0.85rem" }}>{error}</p>
            </div>
          )}

          {loading && (
            <div className="glass" style={{ padding: "40px", textAlign: "center", boxShadow: "var(--shadow-card)" }}>
              <div style={{ width: "40px", height: "40px", margin: "0 auto 12px", borderRadius: "50%", border: "3px solid var(--surface-hover)", borderTopColor: "var(--accent)", animation: "spin 0.9s linear infinite" }} />
              <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>Downloading history & rolling walk-forward folds…</p>
            </div>
          )}

          {m && (
            <>
              <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginBottom: "20px" }} className="animate-fadeInUp">
                <StatTile label="Total Return" value={pct(m.total_return_pct)} sub={`₹${m.final_equity?.toLocaleString("en-IN")} final`} positive={m.total_return_pct > 0} />
                <StatTile label="CAGR" value={pct(m.cagr_pct)} positive={m.cagr_pct > 0} />
                <StatTile label="Sharpe" value={m.sharpe ?? "—"} sub="trade-based" positive={m.sharpe > 0} />
                <StatTile label="Sortino" value={m.sortino ?? "—"} positive={m.sortino > 0} />
                <StatTile label="Max Drawdown" value={pct(m.max_drawdown_pct)} positive={false} />
                <StatTile label="Profit Factor" value={m.profit_factor ?? "—"} positive={m.profit_factor >= 1} />
                <StatTile label="Win Rate" value={m.win_rate_pct != null ? `${m.win_rate_pct}%` : "—"} sub={`${m.total_trades} OOS trades`} positive={m.win_rate_pct >= 50} />
                <StatTile label="Avg Win / Loss" value={`${pct(m.avg_win_pct)} / ${pct(m.avg_loss_pct)}`} sub={`avg trade ${pct(m.avg_trade_pct)}`} />
              </div>

              <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: "12px", fontFamily: "'Space Grotesk', sans-serif" }}>Equity Curve (out-of-sample)</h3>
                <div style={{ height: "260px" }}><Line data={equityData} options={lineOptions((v) => "₹" + Number(v).toLocaleString("en-IN"))} /></div>
              </div>

              <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: "12px", fontFamily: "'Space Grotesk', sans-serif" }}>Drawdown</h3>
                <div style={{ height: "180px" }}><Line data={ddData} options={lineOptions((v) => v + "%")} /></div>
              </div>

              {/* Per-regime */}
              <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)", marginBottom: "16px" }}>
                <h3 style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: "12px", fontFamily: "'Space Grotesk', sans-serif" }}>By market regime</h3>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.8rem", minWidth: "440px" }}>
                    <thead><tr style={{ color: "var(--text-muted)", textAlign: "left", fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      <th style={{ padding: "6px 10px" }}>Regime</th><th style={{ padding: "6px 10px" }}>Trades</th><th style={{ padding: "6px 10px" }}>Win rate</th><th style={{ padding: "6px 10px" }}>Avg return</th><th style={{ padding: "6px 10px" }}>Profit factor</th>
                    </tr></thead>
                    <tbody>
                      {Object.entries(result.per_regime).map(([regime, r]) => (
                        <tr key={regime} style={{ borderTop: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "10px", fontWeight: 700, textTransform: "capitalize" }}>{regime.replace("_", " ")}</td>
                          <td style={{ padding: "10px" }}>{r.trades}</td>
                          <td style={{ padding: "10px", fontWeight: 700, color: r.win_rate >= 50 ? "var(--green)" : "var(--red)" }}>{r.win_rate}%</td>
                          <td style={{ padding: "10px", color: r.avg_return_pct > 0 ? "var(--green)" : "var(--red)" }}>{pct(r.avg_return_pct)}</td>
                          <td style={{ padding: "10px" }}>{r.profit_factor ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Folds + cost model used */}
              <div className="glass" style={{ padding: "20px", boxShadow: "var(--shadow-card)" }}>
                <h3 style={{ fontSize: "0.85rem", fontWeight: 700, marginBottom: "10px", fontFamily: "'Space Grotesk', sans-serif" }}>Walk-forward folds & cost model</h3>
                <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "12px" }}>
                  {result.folds.map((f) => (
                    <span key={f.fold} style={{ padding: "4px 10px", borderRadius: "8px", background: "var(--surface-hover)", fontSize: "0.72rem", fontWeight: 600 }}>
                      Fold {f.fold}: conf ≥ {f.threshold}{f.test_trades != null ? ` · ${f.test_trades} OOS` : ""}
                    </span>
                  ))}
                </div>
                <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", lineHeight: 1.6 }}>
                  Costs applied per trade: brokerage {(result.cost_model.brokerage_rate * 100).toFixed(3)}% (cap ₹{result.cost_model.brokerage_cap}), STT {(result.cost_model.stt_rate * 100).toFixed(3)}%, exchange {(result.cost_model.exchange_txn_rate * 100).toFixed(4)}%, GST {(result.cost_model.gst_rate * 100)}%, stamp {(result.cost_model.stamp_rate * 100).toFixed(3)}%, slippage {result.cost_model.slippage_bps} bps/side. {m.risk_note}
                </p>
                {result.warnings?.length > 0 && (
                  <p style={{ fontSize: "0.7rem", color: "var(--red)", marginTop: "8px" }}>{result.warnings.join(" · ")}</p>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
