# Invexo — Premium Real-Time AI Stock Dashboard

**Live Production App**: [invexo.co.in](https://invexo.co.in/)

Invexo (NexTrade) is a premium real-time Indian stock market analytics dashboard. It combines real-time streaming, advanced quantitative technical analysis indicators, natural language news sentiment models, and consensus-calibrated machine learning predictions into a unified, responsive glassmorphic user interface.

---

## 🚀 Key Features

### 1. Interactive & Resilient Charting
* **Quick View Modal**: Click on any stock card on the dashboard to open a glassmorphic chart modal overlay without navigating away.
* **Dual Graph Switcher**: Seamlessly toggle between a custom **Candlestick Chart** and a **Normal Line Graph** inside both the quick-view modal and full stock detail pages.
* **Fault-Tolerant Data Cleaning**: Integrated client-side mapping filters that normalize database casing (`Open` vs `open`) and dynamically compute fallbacks for missing/null/NaN pricing values from Yahoo Finance, preventing UI coordinates rendering crashes.
* **Interactive HUD**: Hover over chart items to view open, high, low, close (OHLC), and percentage change values dynamically.

### 2. High-Accuracy AI Predictions & Calibration
* **Dynamic Regime Adaptation**: Expected price moves automatically adjust weights based on the market regime:
  * **Trending Markets (High ADX)**: Prioritizes momentum-based factors.
  * **Range-Bound Markets (Low ADX)**: Prioritizes mean-reverting indicators.
* **Consensus-Based Confidence Scores**: Computes consensus scores across 7 distinct indicators (EMA Crossovers, MACD, RSI, Stochastics, Bollinger Bands, News Sentiment, and Company Fundamentals) to calibrate and output realistic accuracy percentages.

### 3. Financial NLP Sentiment Analysis
* **Recency-Weighted Sentiment**: Applies linear recency decay to news articles to weigh the latest headlines more heavily than older stories.
* **Financial Lexicon Parser**: Overlays standard lexicon models with custom financial dictionary rules to correctly score trading keywords (e.g. "surges", "bankruptcy", "investigation").

### 4. Live Market Streaming
* **WebSockets Engine**: Backend connects to a FastAPI WebSocket gateway, caching market data and broadcasting real-time tick changes to all connected clients.

---

## 🛠️ Tech Stack

* **Frontend**: Next.js (React), Tailwind CSS, Chart.js (`react-chartjs-2`), Custom SVG Candlestick Engine.
* **Backend**: FastAPI (Python), Uvicorn, Pandas, Numpy, `curl_cffi` (for TLS fingerprint client impersonation to bypass scraping blocks), TextBlob (NLP sentiment).

---

## 📂 Repository Structure

```text
NexTrade/
├── frontend/             # Next.js UI Application
│   ├── components/       # Reusable components (RealChart, StockCard, Navbar)
│   └── pages/            # Page routing (Dashboard, Detail View, Portfolio, Advisor)
├── backend/              # FastAPI Application Server
│   ├── services/         # Core logic (AI Predictor, Data Fetching, Sentiment)
│   ├── routers/          # API Route Controllers (Market endpoints, Prediction endpoints)
│   └── main.py           # Application Entrypoint
└── README.md             # Documentation Guide
```

---

## ⚙️ Setup and Running Guide

### 1. Run the Backend Server
Prerequisites: Python 3.10+ installed.

```bash
# Navigate to the backend folder
cd backend

# Create and activate virtual environment
python -m venv venv
# On macOS/Linux:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt

# Start the server (runs on http://localhost:8000)
uvicorn main:app --reload --port 8000
```

### 2. Run the Frontend App
Prerequisites: Node.js (v18+) installed.

```bash
# Navigate to the frontend folder
cd ../frontend

# Install dependencies
npm install

# Start the development server (runs on http://localhost:3000)
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## 🔒 yfinance API Impersonation Note
To circumvent Yahoo Finance Bot Protections (which trigger rate-limiting blocks and `404 Not Found` errors in cloud deployment sandboxes), all quantitative endpoints leverage `curl_cffi` to perform client-side **TLS Fingerprint Impersonation** (mimicking Google Chrome v120). This ensures stable history fetches for Indian Stock symbols (NSE/BSE).
