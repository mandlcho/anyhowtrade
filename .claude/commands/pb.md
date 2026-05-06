Run the PB EMA scanner for the given tickers. If no tickers are provided, scan all positions from latest_scan.json.

Execute this command from the project root:

```
/Users/mandl/Desktop/projects/openscan/venv/bin/python3 /Users/mandl/Desktop/projects/openscan/pb.py $ARGUMENTS
```

Display the raw output to the user, then for each ticker provide your analysis in this exact format:

---

**Ticker: [TICKER]**

**PB EMA Context (Daily):** Upper=[value] | Lower=[value] | Close=[value] | vs Upper=[pct]% | vs Lower=[pct]%

**PB EMA Context (4H — second opinion):** Upper=[value] | Lower=[value] | Close=[value] | vs Upper=[pct]% | vs Lower=[pct]%

**Primary Label (Daily):** [one of the 9 labels below]

**Reasoning:**
- [Daily bullet 1 — price action relative to band]
- [Daily bullet 2 — band state: expanding/compressing/flat]
- [Daily bullet 3 — trend direction and momentum implication]
- [Daily bullet 4 — candle behavior in last 3 bars if notable]
- [4H bullet — does 4H agree or conflict with daily label? State which label applies on 4H]

**Swing Implication:**
- [What the setup means for a swing trade — entry, hold, or exit]
- [Key levels to watch (PB upper/lower as support/resistance)]
- [Risk context — what invalidates the thesis]

**Confidence:** High / Medium / Low

---

## The 9 PB EMA Labels

Apply these labels based on the raw output data (Close, PB_upper, PB_lower, and the prior bar values):

1. **Heading toward PB EMA** — Price is approaching the band from above (toward upper) or below (toward lower) but has not yet touched it. Distance is narrowing over recent bars.

2. **Bouncing off PB EMA** — Price touched or wicked into the PB EMA band and is now moving away from it, with the most recent close confirming the bounce direction.

3. **Falling below PB EMA** — Price was inside or above the band and has now closed below PB_lower, but has not confirmed a sustained breakdown yet (1–2 bars only).

4. **Reclaiming PB EMA** — Price was below the band and has now closed back above PB_lower. Shows re-entry into the band. Bullish reclaim of structure.

5. **Breaking out above PB EMA** — Price has closed above PB_upper for the first time or after a period below it. Breakout condition — above band.

6. **Breaking out below PB EMA** — Price has closed below PB_lower decisively, confirmed by 2+ bars below. Bearish breakdown.

7. **Wick-through and rejection at PB EMA** — Price wicked through the band (upper or lower) but the candle body closed back inside or on the other side. Rejection pattern — watch direction of body close.

8. **Trading inside PB EMA band** — Price is between PB_lower and PB_upper. Neutral zone. Band direction (expanding/compressing) is more important signal here.

9. **Failed reclaim of PB EMA** — Price attempted to reclaim PB_lower (or PB_upper) but closed back below (or above) it. Bearish failure for reclaims, bullish failure for breakdowns.

## Label Selection Rules

- Use the raw output's Position label (Above Band, Inside Band, etc.) as a starting point, but apply the 9 labels above using your analysis of the last 3 candles shown in the raw output.
- Transition labels (Reclaiming Upper, Losing Lower from raw output) map to labels 4/5 (bullish) or 3/6 (bearish).
- Band State (Expanding/Compressing/Flat) informs conviction — expanding bands amplify the current trend, compressing bands signal indecision.
- Always check 4H for confirmation or divergence before stating Confidence level.
- High confidence = Daily and 4H agree on label and direction. Medium = mixed signals. Low = conflicting timeframes or insufficient data.
