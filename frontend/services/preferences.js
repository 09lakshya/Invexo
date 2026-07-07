// Shared reader for the user's saved settings so that preferences chosen on the
// Settings page (chart style, default range, display density) actually take
// effect elsewhere in the app instead of only living in localStorage.

export const SETTINGS_KEY = "invexo_settings_v1";

export const TIMEFRAME_KEYS = ["1d", "1w", "1m", "3m", "6m", "1y"];

export function getUserSettings() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) || "null");
  } catch {
    return null;
  }
}

// Chart preferences consumed by the stock page + RealChart.
export function getChartDefaults() {
  const s = getUserSettings();
  const chartType = s?.trading?.chartType === "candle" ? "candle" : "line";
  const timeframe = TIMEFRAME_KEYS.includes(s?.trading?.timeframe)
    ? s.trading.timeframe
    : "3m";
  return { chartType, timeframe };
}

export function getDensity() {
  const s = getUserSettings();
  return s?.appearance?.density === "compact" ? "compact" : "comfortable";
}

// Applies the density preference to <html> so the CSS tokens in globals.css
// can respond to it on every page, not just the Settings page.
export function applyDensity(density) {
  if (typeof document === "undefined") return;
  const value = density === "compact" ? "compact" : "comfortable";
  document.documentElement.setAttribute("data-density", value);
}
