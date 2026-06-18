import numpy as np
import pandas as pd
import yfinance as yf
from app.services.market.ticker_utils import _working_ticker, _yf_session
from app.utils.logger import get_logger

logger = get_logger("backtesting_service")

class BacktestingService:
    @staticmethod
    def run_backtest(symbol: str, strategy: str = "MA", period: str = "2y", initial_capital: float = 100000.0) -> dict:
        """
        Runs a backtest on a stock symbol using the specified strategy.
        Strategies:
            - "MA": Moving Average Crossover (20-day vs 50-day)
            - "RSI": RSI indicator (Buy < 30, Sell > 70)
        """
        try:
            ticker_symbol = _working_ticker(symbol)
            stock = yf.Ticker(ticker_symbol, session=_yf_session)
            df = stock.history(period=period)
            
            if df.empty or len(df) < 50:
                return {"error": "Not enough historical data for backtesting"}
                
            close = df["Close"]
            signals = pd.Series(0, index=df.index)
            
            # 1. Strategy Signal Generation
            if strategy == "MA":
                ma_fast = close.rolling(20).mean()
                ma_slow = close.rolling(50).mean()
                # Buy when fast MA crosses above slow MA
                signals = np.where(ma_fast > ma_slow, 1, -1)
            elif strategy == "RSI":
                import ta
                rsi = ta.momentum.RSIIndicator(close=close, window=14).rsi()
                # Buy when RSI < 30, sell/short/out when RSI > 70
                signals = np.where(rsi < 30, 1, np.where(rsi > 70, -1, 0))
            else:
                # Default Buy & Hold
                signals = np.ones(len(close))
                
            # 2. Portfolio Simulation
            capital = initial_capital
            shares = 0.0
            equity = []
            trades = 0
            winning_trades = 0
            
            state = "OUT"  # OUT or HOLDING
            buy_price = 0.0
            
            for i in range(len(df)):
                price = float(close.iloc[i])
                sig = signals[i]
                
                # Check for buy
                if sig == 1 and state == "OUT":
                    shares = capital / price
                    buy_price = price
                    capital = 0.0
                    state = "HOLDING"
                    trades += 1
                # Check for sell
                elif sig == -1 and state == "HOLDING":
                    capital = shares * price
                    shares = 0.0
                    state = "OUT"
                    if price > buy_price:
                        winning_trades += 1
                
                # Current equity value
                current_equity = capital + (shares * price)
                equity.append(current_equity)
                
            equity_series = pd.Series(equity, index=df.index)
            
            # Final liquidate if still holding
            final_portfolio_value = float(equity_series.iloc[-1])
            total_return_pct = ((final_portfolio_value - initial_capital) / initial_capital) * 100
            
            # Metrics Calculations
            # CAGR
            days = (df.index[-1] - df.index[0]).days
            years = days / 365.25
            cagr = ((final_portfolio_value / initial_capital) ** (1 / max(0.1, years)) - 1) * 100
            
            # Sharpe Ratio
            daily_returns = equity_series.pct_change().dropna()
            # Risk-free rate assumed at 6% (standard in India)
            rf_daily = 0.06 / 252
            excess_returns = daily_returns - rf_daily
            sharpe = (excess_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0.0
            
            # Win Rate
            win_rate = (winning_trades / trades * 100) if trades > 0 else 0.0
            
            # Max Drawdown
            rolling_max = equity_series.cummax()
            drawdowns = (equity_series - rolling_max) / rolling_max
            max_drawdown = float(drawdowns.min()) * 100
            
            return {
                "symbol": symbol,
                "strategy": strategy,
                "period": period,
                "initial_capital": round(initial_capital, 2),
                "final_value": round(final_portfolio_value, 2),
                "total_return_pct": round(total_return_pct, 2),
                "cagr": round(cagr, 2),
                "sharpe_ratio": round(sharpe, 2),
                "win_rate": round(win_rate, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "total_trades": trades
            }
        except Exception as e:
            logger.error(f"Backtesting error: {e}")
            return {"error": f"Backtesting failed: {str(e)}"}
