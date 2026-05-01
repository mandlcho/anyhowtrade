Run the sell signal checker against all current positions. Execute this command from the project root:

```
/Users/mandl/Desktop/projects/openscan/venv/bin/python3 /Users/mandl/Desktop/projects/openscan/sellcheck.py
```

Display the full output to the user. If any stocks triggered 6+ out of 10 sell signals, they have been automatically added to the `claude.sell` watchlist in moomoo. Summarize the key findings — which positions are at risk and why.

The 10 sell signals checked are:
1. RSI overbought (>70) + rolling over
2. Bearish divergence
3. MACD bearish crossover
4. MACD histogram contracting 3+ bars
5. Heavy distribution day (RVOL >1.5x, red candle)
6. Price below 10 MA
7. Price below 21 EMA
8. Close in lower 20% of range
9. Bollinger Band upper rejection
10. Overextended >15% above 50 MA
