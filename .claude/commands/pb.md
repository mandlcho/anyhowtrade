Run the PB EMA scanner for the given tickers. If no tickers are provided, scan all positions from latest_scan.json.

Execute this command from the project root:

```
/Users/mandl/Desktop/projects/openscan/venv/bin/python3 /Users/mandl/Desktop/projects/openscan/pb.py $ARGUMENTS
```

Display the raw output, then for each ticker give the analysis in this exact format. Use plain, simple language — no jargon. Speak like you're explaining to a friend, not writing a research report.

---

**[TICKER]**

**Levels:** Daily band: [upper] / [lower] | Close: [close] | 4H band: [upper] / [lower]

**What's happening:** [1–2 sentences in plain English — where is price relative to the band, what has it been doing the last 3 days]

**4H check:** [1 sentence — does the 4H agree or disagree, and what does that mean]

**What to do:** BUY / SELL / HOLD / WAIT — [1–2 sentences explaining the action in simple terms. What level matters, what would change the call]

**Confidence:** High / Medium / Low

---

## The 9 Labels (internal reference — do not show to user)

Use these to inform the "What's happening" and "What to do" sections. Translate them into plain language.

1. **Heading toward band** — Getting closer to the band but hasn't touched it yet
2. **Bouncing off band** — Touched the band and bounced away — good sign if going up, bad if going down
3. **Just fell below band** — Dropped below for the first time — early warning, watch it
4. **Reclaiming band** — Was below, now climbing back above the lower line — getting healthy again
5. **Broke out above band** — Closed above the top line — strong, trending up
6. **Broke below band** — Confirmed below the bottom line for multiple days — weak, in trouble
7. **Wick rejection** — Poked through the band but snapped back — line is acting as a wall
8. **Inside band** — Between the two lines — neutral, no clear signal, watch the band direction
9. **Failed reclaim** — Tried to get back above the line but got rejected — bad sign

## Rules

- Daily label drives the call. 4H is a second opinion — if they disagree, say so and lower confidence.
- Band Expanding = trend is strong. Band Compressing = trend is losing steam, be cautious.
- "WAIT" means the setup isn't ready yet — tell the user what price level to watch for.
- Keep it short. Two sentences max per section. No bullet walls.
