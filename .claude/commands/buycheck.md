Run the buy signal checker against the Mag 7 watchlist (AAPL, MSFT, GOOGL, AMZN, META, NVDA, TSLA). Execute this command from the project root:

```
/Users/mandl/Desktop/projects/openscan/venv/bin/python3 /Users/mandl/Desktop/projects/openscan/buycheck.py
```

Display the full output to the user. If any stocks triggered 6+ out of 10 buy signals, they have been automatically added to the `claude.buy` watchlist in moomoo. Summarize the key findings — which stocks are showing recovery and why.

The 10 buy signals checked are:
1. RSI oversold (<40) + turning up
2. Bullish divergence
3. MACD bullish crossover
4. MACD histogram expanding bullish 3+ bars
5. Heavy accumulation day (RVOL >1.5x, green candle)
6. Price reclaims 10 MA
7. Price reclaims 21 EMA
8. Close in upper 80% of range
9. Bollinger Band lower bounce
10. Pullback to 50 MA support (within 3%)
