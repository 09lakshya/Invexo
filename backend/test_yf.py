import yfinance as yf
print(yf.Ticker("IDEA.NS").history(period="5d"))
print(yf.download("IDEA.NS", period="5d"))
