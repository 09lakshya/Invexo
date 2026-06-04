import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { useState, useEffect, useRef } from "react";

ChartJS.register(
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Filler,
);

// ── CUSTOM RESPONSIVE RESIZE OBSERVER HOOK ──────────────────────────────────
function useElementSize() {
  const [size, setSize] = useState({ width: 600, height: 300 });
  const [ref, setRef] = useState(null);

  useEffect(() => {
    if (!ref) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setSize({
          width: Math.floor(entry.contentRect.width),
          height: Math.floor(entry.contentRect.height),
        });
      }
    });
    observer.observe(ref);
    return () => observer.disconnect();
  }, [ref]);

  return [setRef, size];
}

// ── CUSTOM HIGH-FIDELITY CANDLESTICK CHART COMPONENT ────────────────────────
function CandlestickChart({ data, colors, isIntraday }) {
  const [setRef, size] = useElementSize();
  const { width, height } = size;
  const [hoveredIndex, setHoveredIndex] = useState(null);

  const marginTop = 36; // Extra spacing for HUD
  const marginBottom = 28;
  const marginLeft = 15;
  const marginRight = 60; // Space for Y-Axis labels

  const plotWidth = Math.max(50, width - marginLeft - marginRight);
  const plotHeight = Math.max(50, height - marginTop - marginBottom);

  const lows = data.map((d) => Number(d.Low));
  const highs = data.map((d) => Number(d.High));
  const minPrice = Math.min(...lows);
  const maxPrice = Math.max(...highs);
  const priceRange = (maxPrice - minPrice) || 1.0;

  const getX = (index) => marginLeft + (index / (data.length - 1)) * plotWidth;
  const getY = (price) => height - marginBottom - ((price - minPrice) / priceRange) * plotHeight;

  const formatXLabel = (dateString) => {
    try {
      const date = new Date(dateString);
      const day = String(date.getDate()).padStart(2, "0");
      const month = String(date.getMonth() + 1).padStart(2, "0");
      if (isIntraday) {
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
      }
      return `${day}/${month}`;
    } catch {
      return dateString;
    }
  };

  // Generate grid values
  const yTicksCount = 4;
  const yTicks = Array.from({ length: yTicksCount + 1 }).map((_, i) => {
    const val = minPrice + (i / yTicksCount) * priceRange;
    return { val, y: getY(val) };
  });

  const xTicksCount = 4;
  const xTicks = Array.from({ length: xTicksCount + 1 }).map((_, i) => {
    const index = Math.floor((i / xTicksCount) * (data.length - 1));
    return { label: formatXLabel(data[index].Date), x: getX(index) };
  });

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const relativeX = x - marginLeft;
    const pct = relativeX / plotWidth;
    const index = Math.max(0, Math.min(data.length - 1, Math.round(pct * (data.length - 1))));
    setHoveredIndex(index);
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
  };

  const activeItem = hoveredIndex !== null ? data[hoveredIndex] : null;
  const activeChangePct = activeItem ? ((activeItem.Close - activeItem.Open) / activeItem.Open) * 100 : 0;

  return (
    <div ref={setRef} style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Absolute OHLC Header HUD */}
      <div style={{
        position: "absolute",
        top: "8px",
        left: "12px",
        fontSize: "0.68rem",
        color: colors.textSecondary,
        fontFamily: "'Space Grotesk', sans-serif",
        display: "flex",
        gap: "10px",
        flexWrap: "wrap",
        pointerEvents: "none",
        zIndex: 5,
        background: colors.bgPrimary === "#080c1a" ? "rgba(8, 12, 26, 0.5)" : "rgba(255, 255, 255, 0.6)",
        padding: "4px 8px",
        borderRadius: "6px",
        backdropFilter: "blur(6px)",
        border: `1px solid ${colors.borderSubtle}`,
        animation: "fadeIn 0.2s ease",
      }}>
        {activeItem ? (
          <>
            <span style={{ fontWeight: 700, color: colors.textPrimary }}>
              {new Date(activeItem.Date).toLocaleDateString("en-IN", {
                day: "numeric",
                month: "short",
                hour: isIntraday ? "2-digit" : undefined,
                minute: isIntraday ? "2-digit" : undefined,
              })}
            </span>
            <span>O:<span style={{ color: (activeItem.Close || 0) >= (activeItem.Open || 0) ? colors.green : colors.red, marginLeft: "2px", fontWeight: 700 }}>₹{Number(activeItem.Open || 0).toFixed(2)}</span></span>
            <span>H:<span style={{ color: (activeItem.Close || 0) >= (activeItem.Open || 0) ? colors.green : colors.red, marginLeft: "2px", fontWeight: 700 }}>₹{Number(activeItem.High || 0).toFixed(2)}</span></span>
            <span>L:<span style={{ color: (activeItem.Close || 0) >= (activeItem.Open || 0) ? colors.green : colors.red, marginLeft: "2px", fontWeight: 700 }}>₹{Number(activeItem.Low || 0).toFixed(2)}</span></span>
            <span>C:<span style={{ color: (activeItem.Close || 0) >= (activeItem.Open || 0) ? colors.green : colors.red, marginLeft: "2px", fontWeight: 700 }}>₹{Number(activeItem.Close || 0).toFixed(2)}</span></span>
            <span style={{ color: (activeChangePct || 0) >= 0 ? colors.green : colors.red, fontWeight: 700, marginLeft: "4px" }}>
              {(activeChangePct || 0) >= 0 ? "\u25B2 +" : "\u25BC "}{Number(activeChangePct || 0).toFixed(2)}%
            </span>
          </>
        ) : (
          <span style={{ fontWeight: 600, opacity: 0.85 }}>Move cursor over chart for OHLC details</span>
        )}
      </div>

      <svg
        width={width}
        height={height}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{ cursor: "crosshair", display: "block" }}
      >
        {/* Horizontal Gridlines & Y-Axis Ticks */}
        {yTicks.map((tick, i) => (
          <g key={`y-grid-${i}`}>
            <line
              x1={marginLeft}
              y1={tick.y}
              x2={width - marginRight}
              y2={tick.y}
              stroke={colors.borderSubtle}
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <text
              x={width - marginRight + 8}
              y={tick.y + 3}
              fill={colors.textSecondary}
              fontSize="9"
              fontFamily="monospace"
            >
              ₹{tick.val.toFixed(1)}
            </text>
          </g>
        ))}

        {/* Vertical Gridlines & X-Axis Ticks */}
        {xTicks.map((tick, i) => (
          <g key={`x-grid-${i}`}>
            <line
              x1={tick.x}
              y1={marginTop}
              x2={tick.x}
              y2={height - marginBottom}
              stroke={colors.borderSubtle}
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <text
              x={tick.x}
              y={height - marginBottom + 14}
              textAnchor="middle"
              fill={colors.textSecondary}
              fontSize="9"
              fontFamily="sans-serif"
            >
              {tick.label}
            </text>
          </g>
        ))}

        {/* Candlestick bars */}
        {data.map((d, i) => {
          const x = getX(i);
          const yOpen = getY(d.Open);
          const yClose = getY(d.Close);
          const yHigh = getY(d.High);
          const yLow = getY(d.Low);

          const isBullish = d.Close >= d.Open;
          const color = isBullish ? colors.green : colors.red;

          // Compute custom bar width
          const candleW = Math.max(3, (plotWidth / data.length) * 0.65);
          const halfW = candleW / 2;

          const yTop = Math.min(yOpen, yClose);
          const yBottom = Math.max(yOpen, yClose);
          const bodyH = Math.max(1.5, yBottom - yTop);

          return (
            <g key={`candle-${i}`} opacity={hoveredIndex !== null && hoveredIndex !== i ? 0.6 : 1}>
              {/* Wick shadow */}
              <line
                x1={x}
                y1={yHigh}
                x2={x}
                y2={yLow}
                stroke={color}
                strokeWidth="1.2"
              />
              {/* Candle Body */}
              <rect
                x={x - halfW}
                y={yTop}
                width={candleW}
                height={bodyH}
                fill={color}
                stroke={color}
                strokeWidth="0.8"
                rx="0.5"
              />
            </g>
          );
        })}

        {/* Crosshair overlays */}
        {hoveredIndex !== null && (
          <g pointerEvents="none">
            {/* Vertical cross line */}
            <line
              x1={getX(hoveredIndex)}
              y1={marginTop}
              x2={getX(hoveredIndex)}
              y2={height - marginBottom}
              stroke={colors.green}
              strokeWidth="0.75"
              strokeDasharray="4 4"
              opacity="0.6"
            />
            {/* Horizontal cross line */}
            <line
              x1={marginLeft}
              y1={getY(data[hoveredIndex].Close)}
              x2={width - marginRight}
              y2={getY(data[hoveredIndex].Close)}
              stroke={colors.green}
              strokeWidth="0.75"
              strokeDasharray="4 4"
              opacity="0.6"
            />
            {/* Focus Point */}
            <circle
              cx={getX(hoveredIndex)}
              cy={getY(data[hoveredIndex].Close)}
              r="3.5"
              fill={data[hoveredIndex].Close >= data[hoveredIndex].Open ? colors.green : colors.red}
              stroke="#fff"
              strokeWidth="1"
            />
          </g>
        )}
      </svg>
    </div>
  );
}

// Resolve a CSS variable to its computed value (Chart.js can't use var() directly)
function getCSSVar(varName, fallback = "#888") {
  if (typeof window === "undefined") return fallback;
  const val = getComputedStyle(document.documentElement)
    .getPropertyValue(varName)
    .trim();
  return val || fallback;
}

export default function RealChart({ data }) {
  const [chartType, setChartType] = useState("line"); // "line" | "candle"

  // 🔥 FORCE VALID DATA (Normalize keys and sanitize nulls/NaNs)
  const cleaned = (data || []).map((d) => {
    if (!d) return null;
    const open = d.Open !== undefined && d.Open !== null ? Number(d.Open) : (d.open !== undefined && d.open !== null ? Number(d.open) : null);
    const high = d.High !== undefined && d.High !== null ? Number(d.High) : (d.high !== undefined && d.high !== null ? Number(d.high) : null);
    const low = d.Low !== undefined && d.Low !== null ? Number(d.Low) : (d.low !== undefined && d.low !== null ? Number(d.low) : null);
    const close = d.Close !== undefined && d.Close !== null ? Number(d.Close) : (d.close !== undefined && d.close !== null ? Number(d.close) : null);
    const date = d.Date || d.date;

    const finalClose = close !== null && !isNaN(close) ? close : null;
    const finalOpen = open !== null && !isNaN(open) ? open : finalClose;
    const finalHigh = high !== null && !isNaN(high) ? high : Math.max(finalOpen || 0, finalClose || 0);
    const finalLow = low !== null && !isNaN(low) ? low : Math.min(finalOpen || 999999, finalClose || 999999);

    return {
      Date: date,
      Open: finalOpen,
      High: finalHigh,
      Low: finalLow,
      Close: finalClose,
    };
  }).filter(
    (d) => d && d.Date && d.Close !== null && d.Open !== null && d.High !== null && d.Low !== null
  );

  // Resolve CSS vars to real colors for Chart.js (re-resolve on theme change)
  const [colors, setColors] = useState({
    green: "#00c896",
    red: "#ff4d6a",
    greenDim: "rgba(0,200,150,0.08)",
    redDim: "rgba(255,77,106,0.08)",
    bgCard: "#111827",
    bgPrimary: "#080c1a",
    textPrimary: "#f1f5f9",
    textSecondary: "#94a3b8",
    borderSubtle: "rgba(255,255,255,0.06)",
  });

  useEffect(() => {
    const resolve = () => {
      setColors({
        green: getCSSVar("--green", "#00c896"),
        red: getCSSVar("--red", "#ff4d6a"),
        greenDim: getCSSVar("--green-dim", "rgba(0,200,150,0.08)"),
        redDim: getCSSVar("--red-dim", "rgba(255,77,106,0.08)"),
        bgCard: getCSSVar("--bg-card", "#111827"),
        bgPrimary: getCSSVar("--bg-primary", "#080c1a"),
        textPrimary: getCSSVar("--text-primary", "#f1f5f9"),
        textSecondary: getCSSVar("--text-secondary", "#94a3b8"),
        borderSubtle: getCSSVar("--border-subtle", "rgba(255,255,255,0.06)"),
      });
    };

    resolve();

    // Re-resolve when theme changes (watches data-theme attribute)
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.attributeName === "data-theme") {
          resolve();
          break;
        }
      }
    });
    observer.observe(document.documentElement, { attributes: true });

    return () => observer.disconnect();
  }, []);

  if (cleaned.length === 0) {
    return <div style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>No chart data available</div>;
  }

  // Determine if bullish or bearish
  const firstPrice = Number(cleaned[0].Close);
  const lastPrice = Number(cleaned[cleaned.length - 1].Close);
  const isBullish = lastPrice >= firstPrice;

  // Set colors based on trend — using resolved values
  const lineColor = isBullish ? colors.green : colors.red;
  const bgColor = isBullish ? colors.greenDim : colors.redDim;

  let isIntraday = false;
  if (cleaned.length > 2) {
    const t1 = new Date(cleaned[0].Date).getTime();
    const t2 = new Date(cleaned[cleaned.length - 1].Date).getTime();
    if (t2 - t1 <= 7 * 24 * 60 * 60 * 1000) {
      isIntraday = true;
    }
  }

  const formatLabel = (dateString) => {
    try {
      const date = new Date(dateString);
      const day = String(date.getDate()).padStart(2, "0");
      const month = String(date.getMonth() + 1).padStart(2, "0");
      
      if (isIntraday) {
        const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        return `${day}/${month}  ${time}`;
      } else {
        const year = date.getFullYear();
        return `${day}/${month}/${year}`;
      }
    } catch {
      return dateString;
    }
  };

  const labels = cleaned.map((d) => formatLabel(d.Date));
  const prices = cleaned.map((d) => Number(d.Close));

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    plugins: {
      tooltip: {
        enabled: true,
        backgroundColor: colors.bgCard,
        borderColor: lineColor,
        borderWidth: 2,
        titleColor: lineColor,
        bodyColor: colors.textPrimary,
        padding: 12,
        borderRadius: 8,
        titleFont: {
          size: 14,
          weight: "bold",
        },
        bodyFont: {
          size: 12,
        },
        callbacks: {
          label: function (context) {
            return `Price: ₹${context.parsed.y.toFixed(2)}`;
          },
        },
      },
      legend: {
        display: false,
      },
    },
    scales: {
      x: {
        grid: {
          color: colors.borderSubtle,
        },
        ticks: {
          color: colors.textSecondary,
          font: {
            size: 11,
          },
        },
      },
      y: {
        grid: {
          color: colors.borderSubtle,
        },
        ticks: {
          color: colors.textSecondary,
          font: {
            size: 11,
          },
          callback: function (value) {
            return "₹" + value.toFixed(0);
          },
        },
      },
    },
  };

  const chartData = {
    labels,
    datasets: [
      {
        label: "Price",
        data: prices,
        borderColor: lineColor,
        backgroundColor: bgColor,
        fill: true,
        tension: 0.05,
        pointRadius: 0,
        pointHoverRadius: 8,
        pointBackgroundColor: lineColor,
        pointBorderColor: colors.bgPrimary,
        pointBorderWidth: 2,
      },
    ],
  };

  return (
    <div style={{ height: "100%", width: "100%", position: "relative" }}>
      {/* Dynamic chart type switcher */}
      <div style={{
        position: "absolute",
        top: "8px",
        right: "12px",
        display: "flex",
        background: "var(--filter-tab-bg)",
        border: "1px solid var(--filter-tab-border)",
        borderRadius: "10px",
        padding: "2px",
        zIndex: 10,
        backdropFilter: "blur(8px)",
      }}>
        <button
          onClick={() => setChartType("line")}
          style={{
            padding: "4px 10px",
            borderRadius: "7px",
            border: "none",
            cursor: "pointer",
            fontSize: "0.7rem",
            fontWeight: 700,
            background: chartType === "line" ? "var(--accent-dim)" : "transparent",
            color: chartType === "line" ? "var(--accent)" : "var(--filter-tab-inactive)",
            transition: "all 0.2s",
            fontFamily: "inherit",
          }}
        >
          Line
        </button>
        <button
          onClick={() => setChartType("candle")}
          style={{
            padding: "4px 10px",
            borderRadius: "7px",
            border: "none",
            cursor: "pointer",
            fontSize: "0.7rem",
            fontWeight: 700,
            background: chartType === "candle" ? "var(--accent-dim)" : "transparent",
            color: chartType === "candle" ? "var(--accent)" : "var(--filter-tab-inactive)",
            transition: "all 0.2s",
            fontFamily: "inherit",
          }}
        >
          Candle
        </button>
      </div>

      {chartType === "line" ? (
        <div style={{ height: "100%", width: "100%" }}>
          <Line data={chartData} options={chartOptions} />
        </div>
      ) : (
        <CandlestickChart data={cleaned} colors={colors} isIntraday={isIntraday} />
      )}
    </div>
  );
}
