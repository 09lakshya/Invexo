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
import { useState, useEffect, useRef, useMemo } from "react";

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
function CandlestickChart({ data, colors, isIntraday, showSwitcher, zoomRef, onZoomStateChange }) {
  const [setRef, size] = useElementSize();
  const { width, height } = size;
  const [hoveredIndex, setHoveredIndex] = useState(null);
  const [zoomRange, setZoomRange] = useState({ start: 0, end: data.length - 1 });
  const [yOffset, setYOffset] = useState(0);
  const [isPanning, setIsPanning] = useState(false);

  // Only reset zoom and panning when the actual dataset contents change (e.g. changing symbol or period)
  const dataKey = data.length > 0 ? `${data.length}-${data[0].Date}-${data[data.length - 1].Date}` : "";

  useEffect(() => {
    console.log("Resetting zoomRange due to dataKey change:", dataKey);
    setZoomRange({ start: 0, end: data.length - 1 });
    setYOffset(0);
    setHoveredIndex(null);
  }, [dataKey]);

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
      e.preventDefault(); // Prevent text selection and default dragging behaviors
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

  // Sync refs to avoid recreating touch event listeners
  const zoomRangeRef = useRef(zoomRange);
  const yOffsetRef = useRef(yOffset);
  const priceRangeRef = useRef(priceRange);

  useEffect(() => {
    zoomRangeRef.current = zoomRange;
  }, [zoomRange]);

  useEffect(() => {
    yOffsetRef.current = yOffset;
  }, [yOffset]);

  useEffect(() => {
    priceRangeRef.current = priceRange;
  }, [priceRange]);

  // Expose zoom controls via ref to parent components
  useEffect(() => {
    console.log("RealChart setting zoomRef.current", { zoomRef, current: zoomRef?.current });
    if (zoomRef) {
      zoomRef.current = {
        zoomIn: () => {
          console.log("zoomRef.zoomIn triggered");
          handleZoom(1);
        },
        zoomOut: () => {
          console.log("zoomRef.zoomOut triggered");
          handleZoom(-1);
        },
        reset: () => {
          console.log("zoomRef.reset triggered");
          handleReset();
        }
      };
    }
    return () => {
      console.log("RealChart zoomRef cleanup (retaining ref contents)");
    };
  }, [zoomRef, zoomRange, yOffset, data.length]);

  // Propagate zoom state changes to parent (so parent can conditionally show Reset button)
  useEffect(() => {
    const zoomed = zoomRange.start > 0 || zoomRange.end < data.length - 1 || yOffset !== 0;
    if (onZoomStateChange) {
      onZoomStateChange(zoomed);
    }
  }, [zoomRange, yOffset, data.length, onZoomStateChange]);

  // Active/Passive Touch event handling inside the graph margins to prevent whole-screen scrolling
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const onTouchStart = (e) => {
      const rect = svgEl.getBoundingClientRect();
      if (e.touches.length === 1) {
        const x = e.touches[0].clientX - rect.left;
        const y = e.touches[0].clientY - rect.top;

        if (x >= marginLeft && x <= (width - marginRight) && y >= marginTop && y <= (height - marginBottom)) {
          if (e.cancelable) e.preventDefault(); // Prevent viewport scrolling/panning during chart dragging
          isDragging.current = true;
          setIsPanning(true);
          dragStartX.current = e.touches[0].clientX;
          dragStartY.current = e.touches[0].clientY;
          dragStartRange.current = { ...zoomRangeRef.current };
          dragStartYOffset.current = yOffsetRef.current;
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
          if (e.cancelable) e.preventDefault(); // Stop screen zoom gesture
          const dist = Math.hypot(
            e.touches[0].clientX - e.touches[1].clientX,
            e.touches[0].clientY - e.touches[1].clientY
          );
          touchStartDistance.current = dist;
          touchStartStart.current = zoomRangeRef.current.start;
          touchStartEnd.current = zoomRangeRef.current.end;
        }
      }
    };

    const onTouchMove = (e) => {
      if (e.touches.length === 1 && isDragging.current) {
        if (e.cancelable) e.preventDefault(); // BLOCK mobile scroll/bounce page drag!
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
        const priceUnitsPerPixel = priceRangeRef.current / plotHeight;
        const shiftY = dy * priceUnitsPerPixel;
        const newYOffset = dragStartYOffset.current + shiftY;

        setZoomRange({ start: newStart, end: newEnd });
        setYOffset(newYOffset);
      } else if (e.touches.length === 2 && touchStartDistance.current > 0) {
        if (e.cancelable) e.preventDefault(); // Stop screen zoom gesture
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

    const onTouchEnd = () => {
      isDragging.current = false;
      setIsPanning(false);
      touchStartDistance.current = 0;
    };

    svgEl.addEventListener("touchstart", onTouchStart, { passive: false });
    svgEl.addEventListener("touchmove", onTouchMove, { passive: false });
    svgEl.addEventListener("touchend", onTouchEnd, { passive: false });

    return () => {
      svgEl.removeEventListener("touchstart", onTouchStart);
      svgEl.removeEventListener("touchmove", onTouchMove);
      svgEl.removeEventListener("touchend", onTouchEnd);
    };
  }, [width, height, data.length, marginLeft, marginRight, marginTop, marginBottom]);

  const handleZoom = (direction) => {
    console.log("handleZoom called with direction:", direction);
    setZoomRange(prev => {
      const span = prev.end - prev.start;
      const delta = Math.max(1, Math.round(span * 0.1));
      let nextRange = { ...prev };
      if (direction > 0) {
        if (span > 4) {
          nextRange = { start: prev.start + delta, end: prev.end - delta };
        }
      } else {
        nextRange = {
          start: Math.max(0, prev.start - delta),
          end: Math.min(data.length - 1, prev.end + delta)
        };
      }
      console.log("New zoom range set to:", nextRange);
      return nextRange;
    });
  };

  const handleReset = () => {
    console.log("handleReset called");
    setZoomRange({ start: 0, end: data.length - 1 });
    setYOffset(0);
  };

  // Wheel event handling: Ctrl+scroll = zoom, regular two-finger trackpad scroll = pan
  useEffect(() => {
    const svgEl = svgRef.current;
    if (!svgEl) return;

    const onWheel = (e) => {
      const rect = svgEl.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      
      if (x >= marginLeft && x <= (width - marginRight) && y >= marginTop && y <= (height - marginBottom)) {
        e.preventDefault();

        if (e.ctrlKey || e.metaKey) {
          // Ctrl+scroll (or trackpad pinch gesture) → ZOOM
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
        } else {
          // Regular two-finger trackpad scroll → PAN
          const currentRange = zoomRangeRef.current;
          const span = currentRange.end - currentRange.start;
          const isZoomed = span < data.length - 1 || yOffsetRef.current !== 0;

          if (isZoomed) {
            // Horizontal panning via deltaX (and deltaY for left/right when no deltaX)
            const dx = e.deltaX !== 0 ? e.deltaX : 0;
            const dy = e.deltaY;

            // X-axis panning: shift visible date window
            if (Math.abs(dx) > 0) {
              const indicesPerPixel = span / plotWidth;
              const shiftX = Math.round(dx * indicesPerPixel * 0.5);
              
              if (shiftX !== 0) {
                setZoomRange(prev => {
                  const s = prev.end - prev.start;
                  let newStart = prev.start + shiftX;
                  let newEnd = prev.end + shiftX;
                  
                  if (newStart < 0) { newStart = 0; newEnd = s; }
                  if (newEnd > data.length - 1) { newEnd = data.length - 1; newStart = newEnd - s; }
                  
                  return { start: newStart, end: newEnd };
                });
              }
            }

            // Y-axis panning: shift price offset
            if (Math.abs(dy) > 0) {
              const priceUnitsPerPixel = priceRangeRef.current / plotHeight;
              const shiftY = dy * priceUnitsPerPixel * 0.5;
              setYOffset(prev => prev + shiftY);
            }
          } else {
            // Not zoomed in — use vertical scroll as zoom (legacy behaviour)
            const direction = e.deltaY < 0 ? 1 : -1;
            
            setZoomRange(prev => {
              const s = prev.end - prev.start;
              const delta = Math.max(1, Math.round(s * 0.08));
              if (direction > 0) {
                if (s > 4) {
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
        }
      }
    };

    svgEl.addEventListener("wheel", onWheel, { passive: false });
    return () => svgEl.removeEventListener("wheel", onWheel);
  }, [width, height, data.length, marginLeft, marginRight, marginTop, marginBottom, plotWidth, plotHeight]);

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

export default function RealChart({
  data,
  chartType: externalChartType,
  setChartType: externalSetChartType,
  zoomRef: externalZoomRef,
  onZoomStateChange: externalOnZoomStateChange
}) {
  const [internalChartType, internalSetChartType] = useState("line");
  const chartType = externalChartType !== undefined ? externalChartType : internalChartType;
  const setChartType = externalSetChartType !== undefined ? externalSetChartType : internalSetChartType;
  const showSwitcher = externalChartType === undefined;

  const internalZoomRef = useRef(null);
  const zoomRef = externalZoomRef || internalZoomRef;

  const [localIsZoomed, setLocalIsZoomed] = useState(false);
  const onZoomStateChange = externalOnZoomStateChange || setLocalIsZoomed;

  // 🔥 FORCE VALID DATA (Normalize keys and sanitize nulls/NaNs)
  const cleaned = useMemo(() => {
    return (data || []).map((d) => {
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
  }, [data]);

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
          gap: "6px",
          zIndex: 10,
        }}>
          {/* Switcher */}
          <div style={{
            display: "flex",
            background: "var(--filter-tab-bg)",
            border: "1px solid var(--filter-tab-border)",
            borderRadius: "10px",
            padding: "2px",
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

          {/* Zoom Controls inside switcher row */}
          {chartType === "candle" && (
            <div style={{
              display: "flex",
              gap: "2px",
              background: "var(--filter-tab-bg)",
              border: "1px solid var(--filter-tab-border)",
              borderRadius: "10px",
              padding: "2px",
              backdropFilter: "blur(8px)",
              animation: "fadeIn 0.2s ease-in-out",
            }}>
              <button
                onClick={() => {
                  console.log("RealChart internal + clicked, zoomRef:", zoomRef.current);
                  zoomRef.current?.zoomIn();
                }}
                title="Zoom In"
                style={{
                  padding: "4px 8px",
                  borderRadius: "7px",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  background: "transparent",
                  color: "var(--filter-tab-inactive)",
                  transition: "all 0.2s",
                  fontFamily: "inherit",
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = "var(--accent-dim)";
                  e.currentTarget.style.color = "var(--accent)";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--filter-tab-inactive)";
                }}
              >
                +
              </button>
              <button
                onClick={() => {
                  console.log("RealChart internal - clicked, zoomRef:", zoomRef.current);
                  zoomRef.current?.zoomOut();
                }}
                title="Zoom Out"
                style={{
                  padding: "4px 8px",
                  borderRadius: "7px",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "0.7rem",
                  fontWeight: 700,
                  background: "transparent",
                  color: "var(--filter-tab-inactive)",
                  transition: "all 0.2s",
                  fontFamily: "inherit",
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = "var(--accent-dim)";
                  e.currentTarget.style.color = "var(--accent)";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--filter-tab-inactive)";
                }}
              >
                −
              </button>
              {localIsZoomed && (
                <button
                  onClick={() => {
                    console.log("RealChart internal reset clicked, zoomRef:", zoomRef.current);
                    zoomRef.current?.reset();
                  }}
                  title="Reset View"
                  style={{
                    padding: "4px 8px",
                    borderRadius: "7px",
                    border: "none",
                    cursor: "pointer",
                    fontSize: "0.65rem",
                    fontWeight: 700,
                    background: "transparent",
                    color: "var(--filter-tab-inactive)",
                    transition: "all 0.2s",
                    fontFamily: "inherit",
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = "var(--accent-dim)";
                    e.currentTarget.style.color = "var(--accent)";
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--filter-tab-inactive)";
                  }}
                >
                  ↺
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {chartType === "line" ? (
        <div style={{ height: "100%", width: "100%" }}>
          <Line data={chartData} options={chartOptions} />
        </div>
      ) : (
        <CandlestickChart
          data={cleaned}
          colors={colors}
          isIntraday={isIntraday}
          showSwitcher={showSwitcher}
          zoomRef={zoomRef}
          onZoomStateChange={onZoomStateChange}
        />
      )}
    </div>
  );
}
