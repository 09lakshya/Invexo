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
function CandlestickChart({ data, colors, isIntraday, showSwitcher }) {
  const [setRef, size] = useElementSize();
  const { width, height } = size;
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [zoomRange, setZoomRange] = useState({ start: 0, end: data.length - 1 });
  const [yOffset, setYOffset] = useState(0);
  const [isPanning, setIsPanning] = useState(false);

  useEffect(() => {
    setZoomRange({ start: 0, end: data.length - 1 });
    setYOffset(0);
    setHoveredIndex(null);
  }, [data]);

  useEffect(() => {
    setHoveredIndex(null);
  }, [zoomRange]);

  const visibleData = data.slice(zoomRange.start, zoomRange.end + 1);

  const marginTop = 36; // Extra spacing for HUD
  const marginBottom = 28;
  const marginLeft = 15;
  const marginRight = 60; // Space for Y-Axis labels

  const plotWidth = Math.max(50, width - marginLeft - marginRight);
  const plotHeight = Math.max(50, height - marginTop - marginBottom);

  const lows = visibleData.map((d) => Number(d.Low));
  const highs = visibleData.map((d) => Number(d.High));
  const minPrice = Math.min(...lows);
  const maxPrice = Math.max(...highs);
  const priceRange = (maxPrice - minPrice) || 1.0;

  const minPriceAdjusted = minPrice + yOffset;
  const maxPriceAdjusted = maxPrice + yOffset;

  const getX = (index) => marginLeft + (index / (visibleData.length - 1)) * plotWidth;
  const getY = (price) => height - marginBottom - ((price - minPriceAdjusted) / priceRange) * plotHeight;

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
    const val = minPriceAdjusted + (i / yTicksCount) * priceRange;
    return { val, y: getY(val) };
  });

  const xTicksCount = 4;
  const xTicks = Array.from({ length: xTicksCount + 1 }).map((_, i) => {
    const index = Math.floor((i / xTicksCount) * (visibleData.length - 1));
    return { label: formatXLabel(visibleData[index].Date), x: getX(index) };
  });

  // Refs for drag tracking
  const isDragging = useRef(false);
  const dragStartX = useRef(0);
  const dragStartY = useRef(0);
  const dragStartRange = useRef({ start: 0, end: data.length - 1 });
  const dragStartYOffset = useRef(0);

  const handleMouseDown = (e) => {
    if (e.button !== 0) return; // Only left click
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (x >= marginLeft && x <= (width - marginRight) && y >= marginTop && y <= (height - marginBottom)) {
      isDragging.current = true;
      setIsPanning(true);
      dragStartX.current = e.clientX;
      dragStartY.current = e.clientY;
      dragStartRange.current = { ...zoomRange };
      dragStartYOffset.current = yOffset;
      setHoveredIndex(null);
    }
  };

  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (isDragging.current) {
      const dx = e.clientX - dragStartX.current;
      const dy = e.clientY - dragStartY.current;

      // X-Panning
      const indicesPerPixel = (dragStartRange.current.end - dragStartRange.current.start) / plotWidth;
      const shiftX = Math.round(-dx * indicesPerPixel);
      const span = dragStartRange.current.end - dragStartRange.current.start;
      
      let newStart = dragStartRange.current.start + shiftX;
      let newEnd = dragStartRange.current.end + shiftX;
      
      if (newStart < 0) {
        newStart = 0;
        newEnd = span;
      }
      if (newEnd > data.length - 1) {
        newEnd = data.length - 1;
        newStart = newEnd - span;
      }

      // Y-Panning
      const priceUnitsPerPixel = priceRange / plotHeight;
      const shiftY = dy * priceUnitsPerPixel;
      const newYOffset = dragStartYOffset.current + shiftY;

      setZoomRange({ start: newStart, end: newEnd });
      setYOffset(newYOffset);
      return;
    }

    if (x < marginLeft || x > width - marginRight || y < marginTop || y > height - marginBottom) {
      setHoveredIndex(null);
      return;
    }

    const relativeX = x - marginLeft;
    const pct = relativeX / plotWidth;
    const index = Math.max(0, Math.min(visibleData.length - 1, Math.round(pct * (visibleData.length - 1))));
    setHoveredIndex(index);
  };

  const handleMouseUp = () => {
    isDragging.current = false;
    setIsPanning(false);
  };

  const handleMouseLeave = () => {
    isDragging.current = false;
    setIsPanning(false);
    setHoveredIndex(null);
  };

  const svgRef = useRef(null);

  // References for touch zoom tracking
  const touchStartDistance = useRef(0);
  const touchStartStart = useRef(0);
  const touchStartEnd = useRef(data.length - 1);

  const handleTouchStart = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (e.touches.length === 1) {
      const x = e.touches[0].clientX - rect.left;
      const y = e.touches[0].clientY - rect.top;

      if (x >= marginLeft && x <= (width - marginRight) && y >= marginTop && y <= (height - marginBottom)) {
        isDragging.current = true;
        setIsPanning(true);
        dragStartX.current = e.touches[0].clientX;
        dragStartY.current = e.touches[0].clientY;
        dragStartRange.current = { ...zoomRange };
        dragStartYOffset.current = yOffset;
        setHoveredIndex(null);
      }
    } else if (e.touches.length === 2) {
      isDragging.current = false;
      setIsPanning(false);

      const x0 = e.touches[0].clientX - rect.left;
      const y0 = e.touches[0].clientY - rect.top;
      const x1 = e.touches[1].clientX - rect.left;
      const y1 = e.touches[1].clientY - rect.top;

      const inside0 = x0 >= marginLeft && x0 <= (width - marginRight) && y0 >= marginTop && y0 <= (height - marginBottom);
      const inside1 = x1 >= marginLeft && x1 <= (width - marginRight) && y1 >= marginTop && y1 <= (height - marginBottom);

      if (inside0 && inside1) {
        if (e.cancelable) e.preventDefault(); // Prevent browser screen zoom
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        touchStartDistance.current = dist;
        touchStartStart.current = zoomRange.start;
        touchStartEnd.current = zoomRange.end;
      }
    }
  };

  const handleTouchMove = (e) => {
    if (e.touches.length === 1 && isDragging.current) {
      if (e.cancelable) e.preventDefault(); // Prevent page/screen scroll bounce
      const dx = e.touches[0].clientX - dragStartX.current;
      const dy = e.touches[0].clientY - dragStartY.current;

      // X-Panning
      const indicesPerPixel = (dragStartRange.current.end - dragStartRange.current.start) / plotWidth;
      const shiftX = Math.round(-dx * indicesPerPixel);
      const span = dragStartRange.current.end - dragStartRange.current.start;
      
      let newStart = dragStartRange.current.start + shiftX;
      let newEnd = dragStartRange.current.end + shiftX;
      
      if (newStart < 0) {
        newStart = 0;
        newEnd = span;
      }
      if (newEnd > data.length - 1) {
        newEnd = data.length - 1;
        newStart = newEnd - span;
      }

      // Y-Panning
      const priceUnitsPerPixel = priceRange / plotHeight;
      const shiftY = dy * priceUnitsPerPixel;
      const newYOffset = dragStartYOffset.current + shiftY;

      setZoomRange({ start: newStart, end: newEnd });
      setYOffset(newYOffset);
    } else if (e.touches.length === 2 && touchStartDistance.current > 0) {
      if (e.cancelable) e.preventDefault(); // Prevent browser screen zoom
      const dist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const ratio = touchStartDistance.current / dist;
      
      const initialSpan = touchStartEnd.current - touchStartStart.current;
      const targetSpan = Math.max(4, Math.min(data.length - 1, Math.round(initialSpan * ratio)));
      
      const diff = targetSpan - initialSpan;
      const leftDiff = Math.floor(diff / 2);
      const rightDiff = diff - leftDiff;
      
      let newStart = touchStartStart.current - leftDiff;
      let newEnd = touchStartEnd.current + rightDiff;
      
      if (newStart < 0) {
        newEnd = Math.min(data.length - 1, newEnd - newStart);
        newStart = 0;
      }
      if (newEnd > data.length - 1) {
        newStart = Math.max(0, newStart - (newEnd - (data.length - 1)));
        newEnd = data.length - 1;
      }

      setZoomRange({ start: newStart, end: newEnd });
    }
  };

  const handleTouchEnd = () => {
    isDragging.current = false;
    setIsPanning(false);
    touchStartDistance.current = 0;
  };

  const handleZoom = (direction) => {
    setZoomRange(prev => {
      const span = prev.end - prev.start;
      const delta = Math.max(1, Math.round(span * 0.1));
      if (direction > 0) {
        if (span > 4) {
          return { start: prev.start + delta, end: prev.end - delta };
        }
      } else {
        return {
          start: Math.max(0, prev.start - delta),
          end: Math.min(data.length - 1, prev.end + delta)
        };
      }
      return prev;
    });
  };

  const handleReset = () => {
    setZoomRange({ start: 0, end: data.length - 1 });
    setYOffset(0);
  };

  // Passive wheel event handling inside the graph margins
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const onWheel = (e) => {
      const rect = svgEl.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      if (x >= marginLeft && x <= (width - marginRight) && y >= marginTop && y <= (height - marginBottom)) {
        e.preventDefault();
        const direction = e.deltaY < 0 ? 1 : -1;
        
        setZoomRange(prev => {
          const span = prev.end - prev.start;
          const delta = Math.max(1, Math.round(span * 0.08));
          if (direction > 0) {
            if (span > 4) {
              return { start: prev.start + delta, end: prev.end - delta };
            }
          } else {
            return {
              start: Math.max(0, prev.start - delta),
              end: Math.min(data.length - 1, prev.end + delta)
            };
          }
          return prev;
        });
      }
    };

    svgEl.addEventListener("wheel", onWheel, { passive: false });
    return () => svgEl.removeEventListener("wheel", onWheel);
  }, [width, height, data.length, marginLeft, marginRight, marginTop, marginBottom]);

  const activeItem = (hoveredIndex !== null && visibleData[hoveredIndex]) ? visibleData[hoveredIndex] : null;
  const activeChangePct = (activeItem && activeItem.Open) ? ((activeItem.Close - activeItem.Open) / activeItem.Open) * 100 : 0;

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
          <span style={{ fontWeight: 600, opacity: 0.85 }}>Drag to Pan | Scroll/Pinch to Zoom | Move cursor for details</span>
        )}
      </div>

      <svg
        ref={svgRef}
        width={width}
        height={height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseLeave}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{ cursor: isPanning ? "grabbing" : "crosshair", display: "block", touchAction: "none" }}
      >
        <defs>
          <clipPath id="chart-plot-area">
            <rect
              x={marginLeft}
              y={marginTop}
              width={plotWidth}
              height={plotHeight}
            />
          </clipPath>
        </defs>

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
              clipPath="url(#chart-plot-area)"
              shapeRendering="crispEdges"
            />
            <text
              x={width - marginRight + 8}
              y={tick.y + 3}
              fill={colors.textSecondary}
              fontSize="10"
              fontWeight="600"
              fontFamily="'Space Grotesk', sans-serif"
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
              clipPath="url(#chart-plot-area)"
              shapeRendering="crispEdges"
            />
            <text
              x={tick.x}
              y={height - marginBottom + 14}
              textAnchor="middle"
              fill={colors.textSecondary}
              fontSize="10"
              fontWeight="600"
              fontFamily="'Space Grotesk', sans-serif"
            >
              {tick.label}
            </text>
          </g>
        ))}

        {/* Clipped Plot Content */}
        <g clipPath="url(#chart-plot-area)">
          {/* Candlestick bars */}
          {visibleData.map((d, i) => {
            const x = Math.round(getX(i));
            const yOpen = Math.round(getY(d.Open));
            const yClose = Math.round(getY(d.Close));
            const yHigh = Math.round(getY(d.High));
            const yLow = Math.round(getY(d.Low));

            const isBullish = d.Close >= d.Open;
            const color = isBullish ? colors.green : colors.red;

            // Compute custom bar width
            const candleW = Math.max(3, Math.round((plotWidth / visibleData.length) * 0.65));
            const halfW = Math.round(candleW / 2);

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
                  strokeWidth="1"
                  shapeRendering="crispEdges"
                />
                {/* Candle Body */}
                <rect
                  x={x - halfW}
                  y={yTop}
                  width={candleW}
                  height={bodyH}
                  fill={color}
                  stroke={color}
                  strokeWidth="1"
                  shapeRendering="crispEdges"
                />
              </g>
            );
          })}

          {/* Crosshair overlays */}
          {hoveredIndex !== null && visibleData[hoveredIndex] && (
            <g pointerEvents="none">
              {/* Vertical cross line */}
              <line
                x1={Math.round(getX(hoveredIndex))}
                y1={marginTop}
                x2={Math.round(getX(hoveredIndex))}
                y2={height - marginBottom}
                stroke={colors.green}
                strokeWidth="1"
                strokeDasharray="4 4"
                opacity="0.6"
                shapeRendering="crispEdges"
              />
              {/* Horizontal cross line */}
              <line
                x1={marginLeft}
                y1={Math.round(getY(visibleData[hoveredIndex].Close))}
                x2={width - marginRight}
                y2={Math.round(getY(visibleData[hoveredIndex].Close))}
                stroke={colors.green}
                strokeWidth="1"
                strokeDasharray="4 4"
                opacity="0.6"
                shapeRendering="crispEdges"
              />
              {/* Focus Point */}
              <circle
                cx={Math.round(getX(hoveredIndex))}
                cy={Math.round(getY(visibleData[hoveredIndex].Close))}
                r="3.5"
                fill={visibleData[hoveredIndex].Close >= visibleData[hoveredIndex].Open ? colors.green : colors.red}
                stroke="#fff"
                strokeWidth="1"
              />
            </g>
          )}
        </g>
      </svg>

      {/* Floating Zoom Controls inside top-right corner of the card */}
      <div style={{
        position: "absolute",
        top: "8px",
        right: showSwitcher ? "110px" : "12px",
        display: "flex",
        gap: "6px",
        zIndex: 10,
        pointerEvents: "auto",
      }}>
        <button
          onClick={() => handleZoom(1)}
          title="Zoom In"
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "6px",
            border: `1px solid ${colors.borderSubtle}`,
            background: colors.bgCard,
            color: colors.textPrimary,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: "bold",
            fontSize: "1rem",
            backdropFilter: "blur(8px)",
            transition: "all 0.2s",
            boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.background = "var(--accent-dim)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = colors.borderSubtle;
            e.currentTarget.style.background = colors.bgCard;
          }}
        >
          +
        </button>
        <button
          onClick={() => handleZoom(-1)}
          title="Zoom Out"
          style={{
            width: "28px",
            height: "28px",
            borderRadius: "6px",
            border: `1px solid ${colors.borderSubtle}`,
            background: colors.bgCard,
            color: colors.textPrimary,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: "bold",
            fontSize: "1.1rem",
            backdropFilter: "blur(8px)",
            transition: "all 0.2s",
            boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
          }}
          onMouseEnter={e => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.background = "var(--accent-dim)";
          }}
          onMouseLeave={e => {
            e.currentTarget.style.borderColor = colors.borderSubtle;
            e.currentTarget.style.background = colors.bgCard;
          }}
        >
          −
        </button>
        {(zoomRange.start > 0 || zoomRange.end < data.length - 1 || yOffset !== 0) && (
          <button
            onClick={handleReset}
            title="Reset View"
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "6px",
              border: `1px solid ${colors.borderSubtle}`,
              background: colors.bgCard,
              color: colors.textPrimary,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: "bold",
              backdropFilter: "blur(8px)",
              transition: "all 0.2s",
              boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = "var(--accent)";
              e.currentTarget.style.background = "var(--accent-dim)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = colors.borderSubtle;
              e.currentTarget.style.background = colors.bgCard;
            }}
          >
            ↺
          </button>
        )}
      </div>
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

export default function RealChart({ data, chartType: externalChartType, setChartType: externalSetChartType }) {
  const [internalChartType, internalSetChartType] = useState("line");
  const chartType = externalChartType !== undefined ? externalChartType : internalChartType;
  const setChartType = externalSetChartType !== undefined ? externalSetChartType : internalSetChartType;
  const showSwitcher = externalChartType === undefined;

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
      {showSwitcher && (
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
      )}

      {chartType === "line" ? (
        <div style={{ height: "100%", width: "100%" }}>
          <Line data={chartData} options={chartOptions} />
        </div>
      ) : (
        <CandlestickChart data={cleaned} colors={colors} isIntraday={isIntraday} showSwitcher={showSwitcher} />
      )}
    </div>
  );
}
