# AskLivermore — Extracted Scanner Prompts

> Extracted 2026-04-19 from https://asklivermore.com/docs
> 47 scanners across 8 categories, scanning 5,000+ NASDAQ/NYSE stocks daily
> All use A+ / A / B+ / B grading scale
> Likely LLM prompt-driven evaluation with pre-filter data thresholds

---

## SCORING SYSTEM (Confluence/Conviction Score)

### Architecture
- **Domain independence**: Signals from different analytical types weigh more than multiple signals within same domain
  - Example: Bull Flag + Insider Buying > Bull Flag + VCP (both momentum)
- **Signal rarity multipliers**:
  - Insider Buying cluster: **2.5x**
  - Volume spike: **0.3x**
- **Volume direction evaluation**:
  - Rising volume accumulation: full score
  - Flat/declining volume: dampened score
  - Heavy down-volume distribution: penalized

### Diminishing Returns Model
- 1st new domain signal: **+15 points**
- 2nd signal: **+12 points**
- 3rd signal: **+9 points**
- 5th signal from same domain: **+3 points**

### Normalization
- Raw scores undergo **square-root scaling** → 0-100 normalized range

### Tier Classification
| Tier | Range | Characteristics |
|------|-------|-----------------|
| S | 90+ | Multiple strong signals across analysis types; rare |
| A | 80-89 | Several confirming signals from different domains |
| B | 70-79 | Few signals confirming each other |
| C | <70 | Single signal or weak confluence |

### Update Frequency
- Pattern scanners: daily recalculation
- Intraday scanners: every 5 minutes

---

## UNIVERSAL GRADING TEMPLATE (used across all scanners)

```
A+ — "Textbook setup — strong confluence across all criteria. Highest conviction."
A  — "High-quality setup worth watching closely. Minor criteria may be slightly off."
B+ — "Decent setup with some reservations. One or two criteria fall short of ideal."
B  — "Pattern detected but lower conviction. Use as a watchlist candidate, not a trade trigger."
```

---

## 1. DAY TRADING SCANNERS (9 scanners, live every 5 min)

### 1.1 Relative Volume (RVOL)
**Pre-filter thresholds:**
- Today's volume ≥ 2x 50-day average
- Absolute volume liquidity floor enforced
- Price action directionality: green close = accumulation, red close = distribution
- Wide-range days + high RVOL = genuine price discovery

**Evaluation criteria:**
- Very high relative volume + clear directional movement + strong absolute volume → A+
- Significant RVOL with direction; minor criteria may slightly underperform → A
- Elevated volume with some reservations; one or two criteria fall short → B+
- Pattern detected but lower conviction → B

**Trading rules:**
- Entry: combine with intraday levels (opening range high, VWAP reclaim, MA pullback)
- Stop: most recent swing low or VWAP (whichever tighter)
- Targets: partial gains at 1R and 2R; trail with VWAP or 5-period EMA

---

### 1.2 High Avg Daily Range (ADR%)
**Pre-filter thresholds:**
- ADR ≥ 4% over 14-day period
- Today's range vs 14-day average (expansion = unusual activity)
- Volume liquidity floor enforced
- Minimum price: $5

**Evaluation criteria:**
- Extremely high ADR with expanding volatility and strong volume → A+
- High ADR with good volume → A
- Elevated range with minor shortfalls → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: use ADR as filter, then look for setups (breakouts, pullbacks, VWAP reclaims)
- Position sizing: 1x ADR adverse move = max risk per trade
- Targets: 1x to 2x ADR

---

### 1.3 Unusual Volume Spike
**Pre-filter thresholds:**
- 3x+ the 50-day average volume minimum
- Z-score normalization applied (stable stocks rank higher than volatile at same multiple)
- Absolute share volume floor enforced
- Upper-half close = Accumulation; lower-half = Distribution

**Evaluation criteria:**
- Extreme statistical anomaly with strong directional movement → A+
- Significant spike worth close monitoring → A
- Unusual activity with minor reservations → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: wait for accumulation confirmation (upper-half close), enter on pullback to VWAP or higher low above spike-day midpoint
- Stop: below spike day's low
- Target: 1x spike-day range as first target; trail with 10 EMA or 21 EMA

---

### 1.4 5% Gap Scanner
**Pre-filter thresholds:**
- Gap ≥ 5% above or below previous close
- Direction classified: Gap Up / Gap Down
- Gap-hold status: held gaps continue, filled gaps reverse
- RVOL 5x+ signals institutional activity
- Absolute volume floor for tradeability

**Evaluation criteria:**
- Massive gap that held throughout the day on heavy volume → A+
- High-quality setup worth watching closely → A
- Solid gap with some reservations → B+
- Pattern detected but lower conviction → B

**Trading rules:**
- Entry: wait for 5-15 min opening range; long above OR high, short below OR low
- Stop: opposite side of opening range
- Targets: 1x opening range projected from breakout; trail with 5 EMA or 9 EMA
- Note: gaps under 3% mostly fill same day

---

### 1.5 Highest Volume
**Pre-filter thresholds:**
- Minimum 10M shares traded today
- RVOL context vs 50-day average
- Price change % correlation checked
- Price floor: $5+

**Evaluation criteria:**
- Strong confluence across all criteria → A+
- High-quality setup with minor deviations → A
- Decent setup with one or two criteria falling short → B+
- Pattern detected but lower conviction → B

**Trading rules:**
- Entry: use as watchlist filter, cross-reference with RVOL and clean technical setup
- Stop: most recent swing low (longs) or swing high (shorts)
- Target: trailing stops for continuation

---

### 1.6 Change in Character
**Pre-filter thresholds:**
- 7+ of last 10 days at below-average volume (quiet period)
- Today's RVOL 2x+ vs 50-day average (spike)
- Price change confirmation (directional validation)
- Absolute volume liquidity enforced

**Evaluation criteria:**
- Strong confluence across all criteria → A+
- High-quality setup; minor criteria slightly off → A
- Decent setup; one or two criteria fall short → B+
- Pattern detected but lower conviction → B

**Trading rules:**
- Entry: avoid chasing spike bar; wait for pullback or higher low at breakout level
- Stop: below breakout level or spike day's low
- Target: 2-3x the prior 10-day range

---

### 1.7 Buyable Gap Up
**Pre-filter thresholds:**
- Gap ≥ 3% from previous close
- RVOL ≥ 1.5x on gap day
- Must hold above gap low throughout entire day
- Close in upper portion of day's range
- Stock above 50-day SMA (trend confirmation)

**Evaluation criteria:**
- Strong gap, heavy volume, held all day, close near highs → A+
- Solid gap with hold, minor deviations acceptable → A
- Decent setup, 1-2 criteria fall short → B+
- Pattern detected, watchlist only → B

**Trading rules:**
- Entry: close of gap day if all criteria met, OR clean pullback to gap-up open within 1-3 sessions
- Stop: below gap-day low
- Target: prior pivot or measured move from base; trail with 10 EMA

---

### 1.8 Recent Doublers
**Pre-filter thresholds:**
- 100%+ gain in last 60 trading days
- Price floor: $5
- Institutional-grade volume required
- Distance from 60-day high tracked (5-10% = intact; 30%+ = fading)
- Speed evaluation: faster doublers = stronger institutional participation
- Gain retention measured

**Evaluation criteria:**
- Strong confluence across criteria; maximum momentum → A+
- Strong double with good retention; minor criteria gaps → A
- Some reservations; 1-2 criteria fall short → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: don't buy extended above 10 EMA; wait for 5-15 day consolidation, breakout on volume
- Stop: low of consolidation
- Target: trail using 10 EMA or 21 EMA; can produce tripler/quadrupler moves

---

### 1.9 Gaps & Strong Moves
**Pre-filter thresholds:**
- Gap 3%+ either direction
- OR total day move 5%+
- OR day range 7%+
- RVOL required
- Classification: Gap Up, Gap Down, Gap & Fade, Intraday Runner, Wide Range Day

**Evaluation criteria:**
- Large clean moves and heavy volume → A+
- Significant moves with minor criteria variations → A
- Solid setups with 1-2 criteria falling short → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Gap Ups → opening range breakout
- Gap & Fade → break of opening range low
- Runners → pullback to VWAP or MA
- Wide Range → next clean technical level
- Stop: defined stop based on technical level
- Profit: partial at 1R, trail remainder

---

## 2. PRE/POST MARKET SCANNERS (4 scanners)

### 2.1 Pre-Market Movers
**Pre-filter thresholds:**
- Minimum stock price: $1
- Minimum prior-day volume: 50,000 shares
- Gap/move ≥ 2%
- Window: 7:00 AM - 9:30 AM ET (peak: 8:00-9:30 AM)
- Volume ratio vs prior-day volume for confirmation

**Evaluation criteria:**
- Large gap + heavy volume + clear directional commitment → A+
- Strong pre-market move with minor deviations → A
- Meaningful activity with 1-2 criteria shortfalls → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: use as watchlist; wait for regular-hours opening range
- Stop: opening range opposite extreme (not pre-market high/low)
- Target: 1x opening range projection; trail with VWAP

---

### 2.2 Post-Market Movers
**Pre-filter thresholds:**
- 2%+ overnight gap from prior close
- Minimum stock price: $2
- Minimum prior-day volume: 50,000 shares
- Classification: After-Hours Catalyst, Continuation, Reversal

**Evaluation criteria:**
- Significant gap + clear catalyst + pre-market volume confirmation → A+
- Strong after-hours move with minor deviations → A
- Meaningful activity; 1-2 criteria slightly suboptimal → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: next-day watchlist; trade regular-hours opening range only
- Stop: opposite side of opening range
- Target: first significant daily chart level; trail with VWAP

---

### 2.3 IPO Base Builder
**Pre-filter thresholds:**
- IPO date within 6-18 months
- Decline 30-60% from post-IPO high
- Consolidation range: <15% for 4+ weeks
- Declining volume during consolidation (most important signal)
- Breakout volume ≥ 50% above 50-day average

**Evaluation criteria:**
- Textbook setup with strong confluence → A+
- High-quality, minor deviations → A
- 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: breakout above consolidation top on above-average volume
- Stop: below base's low
- Target: post-IPO all-time high; then trail with 21 EMA

---

### 2.4 Recent IPO Breakout
*(Documentation not found — 404)*

---

## 3. SWING TRADING SCANNERS (16 scanners)

### 3.1 VCP (Volatility Contraction Pattern)
**Pre-filter thresholds:**
- 3+ progressive contractions, each shallower than last
- Volume dry-up at pivot (lowest volume near breakout point)
- Must pass all 8 Minervini trend template criteria
- Strong relative strength vs market
- Breakout volume ≥ 50% above 50-day average

**Evaluation criteria:**
- Multiple progressively tighter contractions with clear volume dry-up → A+
- Strong contractions, slightly less tight or fewer → A
- Forming pattern, not fully mature → B+
- Minimum criteria met, lower conviction → B

**Trading rules:**
- Entry: buy at pivot point breakout (high of final contraction)
- Stop: below low of final contraction; alternative: midpoint of last contraction; max 7-8%
- Target: base low to pivot distance projected above breakout; trail for extended moves

**Blog insights:**
- Minimum 3-4 pullbacks with each correction smaller in %
- Breakout volume: ≥ 40% above 20-day average OR ≥ 40% above 50-day average
- "Perfect" patterns (each pullback 60-70% smaller) fail 34% more often than irregular formations
- Companies reporting within 10 days: 23% higher failure rates

---

### 3.2 Cup & Handle
**Pre-filter thresholds:**
- Cup depth: 15-35%
- Cup shape: U-shaped (rounded bottom preferred over V-shaped)
- Prior uptrend: minimum 30% advance
- Handle in upper third of cup
- Handle must not drop below cup midpoint
- Declining volume in handle
- Breakout volume: 40-50% above 50-day average

**Evaluation criteria:**
- Textbook: smooth base, brief handle, declining volume → A+
- Solid cup with good handle, minor criteria slightly off → A
- Decent setup with 1-2 criteria shortfalls → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: breakout above handle's high
- Stop: below handle's low or cup midpoint; max 7-8% below buy point
- Target: cup depth added to breakout point; 50-100%+ advances in strong markets

---

### 3.3 Ascending Triangle
**Pre-filter thresholds:**
- Flat resistance: 2+ touches within 2% of same price level
- Higher lows on each pullback (rising support)
- Declining volume as triangle narrows
- Price near apex and close to resistance
- Above 50 SMA (uptrend context)

**Evaluation criteria:**
- Textbook setup; strong confluence → A+
- Solid triangle; most factors present → A
- Decent; 1-2 criteria fall short → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: breakout above flat resistance; volume ≥ 50% above 50-day average; must close above resistance
- Stop: below most recent higher low or rising trendline
- Target: triangle height (widest point) projected upward from breakout
- Stats: 75% upward breakout rate in uptrends (Bulkowski); 70% overall

---

### 3.4 Pocket Pivot (Morales & Kacher)
**Pre-filter thresholds:**
- Up-volume exceeds max down-volume of prior 10 sessions
- Near 10-day SMA; not extended far above 50-day SMA
- Close in upper 60% of day's range
- Low volume in bars preceding the pivot day
- Strong RS vs S&P 500

**Evaluation criteria:**
- Textbook setup, strong confluence → A+
- High-quality, minor criteria slightly off → A
- Some reservations, 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: when all criteria align
- Stop: below pocket pivot day low OR below 50-day MA (whichever tighter)
- Target: subsequent base breakout; measured move; trail with 10-day MA

---

### 3.5 Qullamaggie Breakout
**Pre-filter thresholds:**
- Prior move: 30%+ gain on heavy volume
- Consolidation: range <10%, volume declining to ≥ 50% below daily average
- Consolidation near highs of initial move
- Genuine fundamental catalyst required (earnings, FDA, contract, sector rotation)

**Evaluation criteria:**
- Textbook setup with strong confluence → A+
- High-quality, minor deviations → A
- Decent, 1-2 criteria slightly off → B+
- Lower conviction → B

**Trading rules:**
- Entry: breakout above tight consolidation on volume ≥ 50-day average
- Stop: below consolidation range low
- Target: 10-20% moves; sell into strength with partial profit-taking

---

### 3.6 Bull Flag
**Pre-filter thresholds:**
- Pole: strong upward move (30-40% typical)
- Flag retraces <50% of pole (ideally <30%)
- Declining volume during flag consolidation
- Tight, well-defined flag channel
- Proximity to upper trendline (breakout pivot)

**Evaluation criteria:**
- Textbook setup — strong confluence → A+
- Most factors align; minor deviations → A
- Decent; 1-2 criteria slightly suboptimal → B+
- Pattern detected; lower conviction → B

**Trading rules:**
- Entry: breakout above upper trendline; volume 1.5x+ average; candle must close above trendline
- Stop: below flag's lower boundary or lowest point of consolidation
- Target: pole height projected from breakout point
- Stats: ~67% success rate historically (S&P 500 data, 2 decades)

**Blog insights:**
- Shallow retracement: 3-5% during consolidation
- Flag range examples: 2.8% (tight, preferred) to 8.3% (acceptable for larger caps)
- Declining volume = "selling pressure diminishing"
- Typical R:R: 1:2 or better

---

### 3.7 Bear Flag (Bearish)
**Pre-filter thresholds:**
- Pole decline: ≥ 10% over 1-8 bars
- Flag retraces <50% of pole decline
- Volume declines during flag consolidation
- Price drifts toward lower end of flag range
- Price below 50-day SMA (bearish context required)

**Evaluation criteria:**
- Textbook; strong confluence → A+
- High-quality with minor deviations → A
- Decent; 1-2 criteria shortfalls → B+
- Lower conviction → B

**Trading rules:**
- Entry: breakdown below flag's lower boundary with volume expansion
- Stop: above flag's high (bounce top)
- Target: pole length projected downward from breakdown; partial profits at intermediate support

---

### 3.8 Weinstein Stage 1 (Base Formation)
**Pre-filter thresholds:**
- 30-week MA must fully flatten
- Price range contraction (tightening oscillation)
- Longer bases = stronger subsequent advances
- Volume: subtle increases on up-weeks, dry-ups on down-weeks
- Proximity to Stage 2 breakout (near top of mature base)

**Evaluation criteria:**
- Textbook with strong confluence → A+
- High-quality, minor deviations → A
- Developing; 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: breakout above flattened 30-week MA on significant volume
- Stop: below base range top or 30-week MA
- Target: 50-100%+ over months; trail with 10-week or 30-week MA

---

### 3.9 .618 Fibonacci Entry (Golden Pocket)
**Pre-filter thresholds:**
- Pullback to .618-.786 zone
- Clean, impulsive prior advance (choppy action reduces reliability)
- .618 level aligns with prior resistance, MAs, or trendlines
- Declining volume during retracement
- Bullish candlestick patterns or momentum turns at zone

**Evaluation criteria:**
- Textbook with strong confluence → A+
- High-quality; minor deviations → A
- Decent; 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: price reaches .618-.786 zone with bullish reversal signal
- Stop: below .786 level OR below reversal candle's low (whichever lower)
- Targets: retest of prior swing high (100%); extensions at 1.272 and 1.618

---

### 3.10 Inverse Head & Shoulders
**Pre-filter thresholds:**
- Three successive lows: left shoulder (moderate), head (deepest), right shoulder (higher than head)
- Head depth ratio: 1.5x-2.5x relative to shoulder depth
- Volume: declines L-shoulder → head, increases on R-shoulder, surges at neckline
- Shoulder symmetry (balanced preferred)
- Relatively flat neckline preferred

**Evaluation criteria:**
- Textbook; strong confluence → A+
- High-quality; minor criteria slightly off → A
- Decent; 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: decisive close above neckline with volume ≥ 50% above average; OR pullback to neckline as support
- Stop: below right shoulder low
- Target: head-to-neckline distance projected upward from breakout

---

### 3.11 Head & Shoulders Top (Bearish)
**Pre-filter thresholds:**
- Three peaks: left shoulder → head (higher high) → right shoulder (lower high)
- Head-to-shoulder ratio: 1.5x-2.5x
- Volume: heaviest on L-shoulder, declining through head and R-shoulder, expanding at breakdown
- Balanced shoulders preferred
- Flat or slightly upward-sloping neckline preferred
- Right shoulder must form lower high than head (mandatory)

**Evaluation criteria:**
- Symmetric, clear neckline, weakening volume on R-shoulder → A+
- Good pattern, most factors aligned → A
- Decent; 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: decisive close below neckline on increased volume; OR pullback to neckline underside as resistance
- Stop: above right shoulder high
- Target: head-to-neckline distance projected downward
- Stats: 80%+ success rate with strict criteria (Bulkowski)

---

### 3.12 Bottom Finder (StockWhale)
**Pre-filter thresholds:**
- Extreme extension below 50-day and 200-day MAs
- Volume capitulation spike followed by sharp dry-up
- Momentum divergence: RSI/MACD higher low while price lower low
- Prior support level proximity
- Decline deceleration (steep → shallow)

**Evaluation criteria:**
- Strong confluence across all criteria → A+
- High-quality with minor criteria slightly off → A
- Decent; 1-2 criteria falling short → B+
- Lower conviction → B

**Trading rules:**
- Entry: pilot position when 3 convergence signals align; add on first higher low or above 10-day MA
- Stop: 3-5% below capitulation low
- Targets: declining 20-day MA (partial); 50-day MA (trail remainder)

---

### 3.13 Falling Wedge
*(Documentation not found — 404)*

---

### 3.14 Weinstein Stage 3 (Distribution)
*(Documentation not found — 404)*

---

### 3.15 Parabolic Short (Bearish)
**Pre-filter thresholds:**
- Extreme distance above 50-day and 200-day MAs
- Volume climax patterns (final buying wave exhaustion)
- Momentum divergence: RSI/MACD lower highs while price higher highs
- Statistical overextension: Bollinger Band width, std dev, historical percentile
- Historical mean reversion zones

**Evaluation criteria:**
- Textbook with strong confluence → A+
- High-quality; minor criteria slightly off → A
- Decent with reservations; 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: when momentum divergence confirmed + first significant red candle on volume after climax
- Stop: above parabolic high; never add to losing short
- Targets: 20-day MA (first), 50-day MA (second); 50-62% retracement typical

---

### 3.16 Short Squeeze Setup
**Pre-filter thresholds:**
- Short interest ≥ 15% of float (or equivalent days-to-cover)
- Must coincide with active bullish pattern (bull flag, VCP, ascending triangle, etc.)
- Increasing volume (shorts covering)
- Days to cover estimate evaluated
- Price above 50-day SMA

**Evaluation criteria:**
- Strong confluence across all criteria → A+
- High-quality with minor deviations → A
- 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: breakout confirmed with ≥ 1.5x average volume
- Stop: below pattern support level (tight)
- Exit: 1/3 at +20%, 1/3 at +40%, trail final 1/3 with 2x ATR

---

## 4. MOMENTUM SCANNERS (5 scanners)

### 4.1 Minervini Trend Template (8-Point Stage 2)
**All 8 criteria required (no partial matches):**
1. Price above 50-day MA
2. Price above 150-day MA
3. Price above 200-day MA
4. 150-day MA above 200-day MA
5. 200-day MA trending upward for at least 1 month
6. Within 25% of 52-week high
7. At least 25% above 52-week low
8. Relative strength ranking in upper tier vs market

**Entry signal:** Meeting all 8 is necessary but not sufficient — must wait for specific setup pattern (VCP, high tight flag, base breakout) with volume confirmation

**Trading rules:**
- Stop: 7-8% below buy point
- Target: 15-20% initial gains

---

### 4.2 CAN SLIM (7 Factors)
**Factor criteria:**
- **C** (Current Quarterly Earnings): Accelerating quarterly EPS (each quarter faster than last)
- **A** (Annual Earnings Growth): Consistent annual growth 25%+ over 3-5 years
- **N** (New Highs/Products/Management): Near 52-week highs; new catalysts
- **S** (Supply & Demand): Increasing volume on advances, declining on pullbacks
- **L** (Leader or Laggard): RS rating in top 20% (95% of winners had RS > 80)
- **I** (Institutional Sponsorship): Fund accumulation evidence through volume
- **M** (Market Direction): Must avoid confirmed downtrends

**Grading:**
- A+: all criteria strong
- A: most factors aligned
- B+: several criteria met
- B: pattern detected, lower conviction

**Trading rules:**
- Entry: breakout from base (cup-handle, flat base, double bottom) with volume 40-50% above average
- Stop: 7-8% below entry (no exceptions)
- Target: 20-25% gains; trail with 10-week MA

---

### 4.3 RS New High
**Pre-filter thresholds:**
- RS line within 2% of its 52-week high
- Stock price 5-20% below its own 52-week high (creates divergence)
- Above 50-day SMA
- Positive Mansfield RS value
- RS at 90th+ percentile of its own history
- Calculation period: 252 trading days vs SPY

**Trading rules:**
- Entry: base breakout, pocket pivot, or pullback to 21 EMA while divergence active
- Stop: below recent swing low or 50-day SMA (whichever tighter)
- Target: retest of 52-week high; trail 10 or 21 EMA

---

### 4.4 BX Trend Momentum (DiCarlo Buy Signal)
**Pre-filter thresholds:**
- Weekly trend confirmed bullish (momentum oscillators + MAs)
- Daily pullback to 21 EMA support
- Daily momentum oscillators turning positive at support
- Rising 21 EMA with price pulling back to it
- Volume expansion on bounce from 21 EMA

**Trading rules:**
- Entry: daily pullback reaches 21 EMA + weekly trend bullish + daily momentum turning positive from oversold
- Stop: below recent swing low OR below 50-day MA (whichever closer)
- Target: prior swing high; trail with 10 EMA

---

### 4.5 Weinstein Stage 2 — Confirmed Breakout (New Uptrend)
**Pre-filter thresholds:**
- Price closes above both 50-day and 200-day MAs
- 50-day MA above 200-day MA (or crossing above)
- Volume ≥ 40% above average on breakout
- Improving RS vs S&P 500
- Longer, tighter bases preferred
- 21 EMA slope turning positive after flat/negative

**Trading rules:**
- Entry: price close above both MAs on 40%+ volume
- Stop: below 200-day MA or most recent swing low
- Target: trail with 21 EMA or 50-day MA for multi-month advances

---

## 5. EARNINGS SCANNERS (5 scanners)

### 5.1 Power Earnings Gap (PEG)
**Pre-filter thresholds:**
- Gap ≥ 5%
- Volume: 3x+ the 50-day average (institutional participation)
- Significant EPS beat above consensus
- Tight consolidation near gap-day highs
- Gap fill on volume = invalidation

**Evaluation criteria:**
- Massive gap, huge volume, tight consolidation near highs → A+
- Strong gap with good volume, minor criteria slightly off → A
- Solid setup; 1-2 criteria fall short → B+
- Lower conviction → B

**Trading rules:**
- Entry: breakout above consolidation on volume; avoid day-one chasing
- Stop: below gap-day low
- Target: 20-50% potential; use consolidation height projected above breakout

---

### 5.2 PEG + Flag
**Pre-filter thresholds:**
- Same PEG criteria (5%+ gap, 3x volume, EPS beat) PLUS:
- Flag forms 3-10 days after gap
- Retraces ≤ 30-40% of gap move
- Declining volume in flag
- Flag near top of gap-day range
- Max flag duration: 10-15 days

**Trading rules:**
- Entry: breakout above flag's high with expanding volume
- Stop: below flag's low; secondary: gap-day low
- Target: gap-day range projected above flag breakout

---

### 5.3 Earnings Next Week
*(Calendar-based scanner — estimated reporting dates with trend positioning)*

---

### 5.4 Earnings Next Month
*(Calendar-based scanner — estimated reporting dates with trend positioning)*

---

### 5.5 Earnings Watch
**Pre-filter thresholds:**
- Estimated earnings date within 30 days
- Cross-references 15 bullish pattern scanners: Bull Flag, VCP, Cup & Handle, Ascending Triangle, Livermore, Qullamaggie, Minervini, CANSLIM, PEG, IHS, Stage 2, Pocket Pivot, BX Trend, RS New High, Buyable Gap Up
- 3+ patterns firing = institutional-level conviction
- Days until earnings (imminent = bonus grading)
- Above 50 SMA required

**Trading rules:**
- Entry: trade the underlying pattern; treat earnings as tailwind only
- Stop: pattern invalidation level
- Exit flat before earnings report

---

## 6. VALUE & GROWTH SCANNERS (4 scanners)

### 6.1 Buffett Value Compounder
**Pre-filter thresholds:**
- ROE > 15% for 5+ years
- Stable or expanding profit margins
- Debt-to-equity < 0.5
- Predictable earnings + strong free cash flow
- P/E at or below stock's own 5-year historical average

**Trading rules:**
- Entry: when ROE > 15%, margins stable, debt minimal, trading at/below historical P/E
- Stop: exit if ROE < 12% for 2 consecutive years, margins contract, debt rises; price stop 20-25%
- Target: permanent ownership while quality remains

---

### 6.2 Peter Lynch GARP
**Pre-filter thresholds:**
- PEG ratio < 1.0 (significantly undervalued at < 0.75)
- Earnings growth ≥ 15% annually (target 15-30% for fast growers)
- Consistent revenue expansion
- Rising institutional ownership

**Trading rules:**
- Entry: PEG < 1.0, 15%+ earnings growth, consistent revenue, non-overextended technically
- Stop: technical 15-20% below entry; fundamental exit if PEG > 1.5 or earnings < 15%
- Target: hold for years; doubling+ as market recognizes undervaluation

---

### 6.3 Dividend Growth Accelerator
**Pre-filter thresholds:**
- 3+ consecutive years of dividend increases
- YoY dividend growth rate itself accelerating
- Yield ≥ 0.5% minimum (ideal: 2%+)
- Payout ratio < 80%
- Absolute dollar amounts trending upward over multiple years

**Trading rules:**
- Entry: pullbacks to 200-day MA or broad corrections when yield spikes above 3-year average
- Stop: 15-20% below entry; dividend cuts/freezes = exit
- Target: hold indefinitely if dividend keeps accelerating; reinvest dividends

---

### 6.4 Munger 200-Week MA
**Pre-filter thresholds:**
- Price within 5% of 200-week MA
- ROE > 12% consistently (entry signal at > 15%)
- Positive earnings growth over trailing 5 years
- Stable gross margins (low variance)
- P/E below sector median

**Trading rules:**
- Entry: quality business (ROE > 15%, stable margins) touches/dips below 200-week MA
- Stop: 10-15% below 200-week MA
- Target: return to historical valuation (50-week MA or higher); 30-50% over 1-3 years

---

## 7. INTELLIGENCE SCANNERS (4 scanners)

### 7.1 Smart Money Confluence
**Pre-filter thresholds:**
- Long setups: 3+ independent bullish signals from 25 scanners
- Short setups: 2+ independent bearish signals from 4 scanners (bear flag, H&S top, parabolic, Stage 3)
- Only bullish-type volume surges count toward long confluences
- Individual signal grades maintained from source scanners

**Evaluation criteria:**
- 5+ confluences; exceptional independent signals → A+
- Strong multi-signal confluence → A
- Developing; 1-2 minor shortfalls → B+
- Meets minimum threshold; lower conviction → B

**Trading rules:**
- Entry: use highest-graded individual signal's entry criteria
- Stop: tightest risk level among active signals
- Target: partial exits at 10-15%; trail with 10 EMA
- Position sizing: 5+ confluences warrant more patience

---

### 7.2 Insider Buying Tracker
**Pre-filter thresholds:**
- Multiple insiders buying independently (cluster buying)
- Purchase amounts: $500K+ = meaningful; $1M+ = very high conviction
- C-suite (CEO/CFO): 3x weight vs directors
- Cluster within 14-day window most meaningful; 30-day window evaluated
- Pullback purchases score higher (contrarian signal)
- Buying below recent MAs preferred

**Trading rules:**
- Entry: 2+ insiders within 14 days + technical stabilization (higher low, support bounce, bullish candle)
- Stop: below recent swing low OR 8-10% below entry (whichever tighter)
- Time horizon: weeks to months
- Target: return to insider purchase price or prior swing high

---

### 7.3 Volume Surge
**Pre-filter thresholds:**
- 3x minimum vs 50-day average; 5x+ = extraordinary
- Close in top 20% of range = bullish; bottom 20% = bearish
- Must break above 20-day or 50-day highs
- Excludes stocks with earnings within ±3 days
- Must not be far above 50 SMA (avoids extended entries)

**Trading rules:**
- Entry: on surge-day close or pullback to surge-day midpoint next session
- Stop: below surge day's low; or 20-day low for wider stops
- Target: measured move = surge-day range from close; trail with 10 EMA for 5-15 sessions

---

### 7.4 Serenity Hidden Gems (Supply Chain)
**Selection criteria:**
- Universe: typically 40-60 stocks at any time
- Chokepoint position in critical supply chain
- Larger players cannot function without them
- Near-zero analyst coverage

**Two scoring dimensions:**
1. Supply chain depth (layers 1-6; prefer layers 5-6)
2. Information asymmetry (market misunderstanding vs strategic importance)

**Layer classification:**
- Layer 1-2: final assemblers, direct suppliers (high coverage, fully priced)
- Layer 3-4: component makers, specialty chemicals (some coverage)
- Layer 5-6: precursor materials, calibration equipment, specialty minerals (near-zero coverage, often single-source)

**Operational rules:**
- NEW tags clear after 14 days
- Removal: thesis breaks (customer loss, competitive disruption, regulatory change)
- Full thesis, supply chain position, grade, risk factors per pick

---

## 8. FEATURED / GUIDES

### 8.1 Livermore Pivotal Point — Breakout
**Pre-filter thresholds:**
- Breakout volume: 2x the 50-day average minimum
- Suspect if below 1.5x average
- Tight consolidation that compresses energy
- First breakout from new consolidation is most reliable
- Market direction alignment required
- Strong prior trend with institutional sponsorship

**Evaluation criteria:**
- Market leader, ultra-tight consolidation, explosive volume near highs → A+
- Strong breakout; minor criteria deviations → A
- Decent with reservations; 1-2 shortfalls → B+
- Lower conviction → B

**Trading rules:**
- Continuation pivotal points: 20-50%+ advance potential
- Reversal pivotal points: mark direction changes
- Trail stops; add to winners at subsequent pivotal points
- Avoid: low-volume breakouts, secondary breakouts, ignoring market direction
