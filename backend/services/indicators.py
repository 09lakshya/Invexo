import numpy as np
import pandas as pd

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2):
    sma = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band

def calculate_adx(df: pd.DataFrame, period: int = 14):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    
    h_l = high - low
    h_pc = (high - close.shift(1)).abs().fillna(0.0)
    l_pc = (low - close.shift(1)).abs().fillna(0.0)
    
    tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    plus_dm_series = pd.Series(plus_dm, index=df.index)
    minus_dm_series = pd.Series(minus_dm, index=df.index)
    
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    atr_safe = np.where(atr != 0, atr, 1e-9)
    
    plus_di = 100 * plus_dm_series.ewm(alpha=1/period, adjust=False).mean() / atr_safe
    minus_di = 100 * minus_dm_series.ewm(alpha=1/period, adjust=False).mean() / atr_safe
    
    di_sum = plus_di + minus_di
    di_diff = (plus_di - minus_di).abs()
    dx = 100 * np.where(di_sum != 0, di_diff / di_sum, 0.0)
    
    adx = pd.Series(dx, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    return plus_di, minus_di, adx

def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    low_min = df["Low"].rolling(window=k_period).min()
    high_max = df["High"].rolling(window=k_period).max()
    
    denom = high_max - low_min
    k = 100 * np.where(denom != 0, (df["Close"] - low_min) / denom, 50.0)
    k_series = pd.Series(k, index=df.index).fillna(50.0)
    d = k_series.rolling(window=d_period).mean().fillna(50.0)
    return k_series, d
