import yfinance as yf
print("IDEA:")
print(yf.Ticker("IDEA").history(period="1d"))
print("OLAELEC:")
print(yf.Ticker("OLAELEC").history(period="1d"))
