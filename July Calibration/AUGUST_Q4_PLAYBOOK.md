# August → Q4 2026 Playbook — the El Niño record window

*Written 2026-07-23, ahead of the August market open. Grounded in NOAA records (hard facts), the live ONI (El Niño +1.0 and ramping), and the microstructure lessons from the June/July tape (§9 of PROFITABILITY_ANALYSIS.md). Projections marked "proj" are illustrative back-of-envelope, not the model — recompute fair P from the ensemble+regression once August ERA5 data exists.*

---

## 0. The one reframe that changes the plan

**August is not the summer longshot, and it is not even your best YES month.** Two hard facts:

- **August's record is 1.25** (2023), a *higher* bar than June/July's 1.18. 2024 printed 1.24 — a near-miss even in the last strong El Niño.
- **El Niño is ramping fast**: ONI +0.5 (spring) → **+1.0 (AMJ)** → strengthening into a likely strong event by Q4 (CPC ~63% very-strong NDJ). Its warming contribution to the global mean is *small in August and largest in Nov–Dec*.

So the "records cluster in El Niño" regime is switching ON, and it escalates through the fall. That flips the edge you had all summer: **selling the longshot was +EV Jan–July because every month decayed to NO. In the El Niño ramp, YES becomes the value side — but not uniformly, and not most in August.**

### The record map (this is the strategy)

| Month | Record | 2024 | proj 2026 | margin | Read |
|---|---|---|---|---|---|
| **Aug** | 1.25 | 1.24 | ~1.18 | −0.07 | YES roughly fair at 10–15¢; a defensible *value* buy, not a steal |
| **Sep** | **1.41** | 1.22 | ~1.19 | −0.22 | **Record is a wall. SELL YES here — your old engine still works.** |
| **Oct** | 1.35 | 1.31 | ~1.32 | −0.03 | **Best YES value of the year — softest record vs the El Niño-boosted trend.** |
| **Nov** | 1.40 | 1.30 | ~1.34 | −0.06 | Live YES, El Niño near peak. |
| **Dec** | 1.36 | 1.26 | ~1.32 | −0.04 | Live YES, El Niño peak. |

**The single biggest improvement to your plan: don't concentrate on August. Spread the El Niño-tail YES capital across Oct/Nov/Dec (softer records, stronger El Niño), keep SELLING YES in September (1.41 is unbreakable-ish), and treat August as a small starter + a spike-trading month.**

---

## 1. Stress-test of your stated plan

Your plan: **(a) $500 YES at 10¢ on open; (b) $1,500 reserve to deploy when NO ≤ 60¢, "capitalize the YES and switch."**

### (a) $500 YES at 10¢ — good instinct, three fixes
- ✅ Directionally right for the regime: buying cheap El Niño-tail optionality instead of mechanically selling it.
- ⚠️ **Don't market-buy at the open.** July opened 7–27¢ on a near-empty book; the first prints are noise. Post a **resting limit at ≤10¢** and let impatient sellers fill you — you become the maker, get the best price, pay 0 fee.
- ⚠️ **$500 at 10¢ = 5,000 contracts.** On a $1–3k book you *cannot* fill that at 10¢ without moving the price up onto yourself. **Scale in** (e.g., 1,000-lot clips on dips), or accept a higher average.
- ⚠️ **Define the exit ladder before you enter**, or the base rate (decay to ~3¢) grinds you out. Suggested: scale out 40% at 25¢, 40% at 40¢, ride the last 20% as a lotto into settlement. Plus a **model stop**: if by ~Aug 15 the ensemble P(YES) < 8% and no surge signal, cut and recycle to a better month.

### (b) The "$1,500 → buy NO at 60¢" switch — this is the dangerous part
**Buying NO at 60¢ (YES 40¢) is +EV in exactly one of two cases and a disaster in the other.** The price alone does not tell you which:

- ✅ **Overshoot (liquidity vacuum, §9):** a single large taker gapped the book at an illiquid hour with **no fresh forecast_log high** behind it. The spike reverts. Buying the panic NO is the fade — this is the July 18 setup you were *right* to want and *wrong* to fight.
- ❌ **Genuine record run (El Niño real):** the ensemble P(YES) is 40%+ *and rising*, the forecast is at new highs. NO at 60¢ keeps falling to 30¢ and settles at $0. Buying NO here is July's mistake wearing a new costume — trading the price, not the model.

**The rule that saves you:** *only deploy the NO reserve if, at that moment, the 51-member ensemble P(YES) < 35% (fair NO > 65¢) AND there is no forecast_log high in the last 24h.* If the ensemble says 45% and climbing, do the opposite — **hold/add YES**, because you're in a Scenario C run (below). **Gate the switch on the model, never on the 60¢ price.**

---

## 2. The August scenario tree (with what to do in each)

| Scenario | Rough odds | What it looks like | Your play |
|---|---|---|---|
| **A — Calm decay** | ~45–55% | YES bleeds 10→3¢, book deep, no surge | Exit YES on *any* spike; don't hold to zero. Reserve stays dry → **redeploy to Oct**. Sell the occasional overshoot spike for income. |
| **B — Surge overshoot** | ~25–35% (up from summer) | Forecast scare spikes YES to 40–50¢ intraday, then reverts | **Plan's sweet spot:** sell YES into the spike (+3–4× on the 10¢), then IF model-gated (P<35%, no fresh high) buy NO 60¢ for the reversion. |
| **C — Genuine record run** | ~15–20% (elevated by El Niño) | YES climbs 10→30→50 and *stays*, ensemble P rising, forecast at highs | **Do NOT switch to NO.** Hold/add YES. The 10¢ ticket can 5–10×. This is the scenario your "buy NO at 60¢" rule would blow up in. |

The discriminator between B and C is the **forecast_log timestamp vs the ensemble trend**, which you already compute. B = spike with stale fundamentals (fade). C = spike with a fresh model high (respect/ride).

---

## 3. Recommendations by perspective

### Market / microstructure
- **Be the resting liquidity, not the taker.** The §9 lesson: spikes are liquidity vacuums, and the money is being the order the vacuum lifts. Pre-place **resting YES asks** (to sell into fear spikes) and **resting NO bids** (to buy the panic). Don't chase — the July −$256 was chasing.
- **Two spike types, one discriminator.** Spike + no fresh forecast_log high = fade (liquidity event). Spike + new model high = respect (information event). Free signal, you already log both.
- **Thin book at open = best YES entry.** Widest spreads, most mispricing, patient limits get filled cheap.
- **Calm ≠ opportunity.** When 1,500-lot blocks trade with zero price impact (deep MM liquidity), there's no sweep edge — just accumulate at fair or wait.

### Trader / execution
- **Limits, not markets. Scale in and out.** Every entry and exit as resting clips sized to the book (~a few hundred to 1,000 lots), never one $500–1,500 market order that moves price onto you.
- **Pre-commit exits and stops in writing** (the ladder + the model stop above). The July damage was 100% discretionary reactions in the spike.
- **Respect book depth = respect your own risk cap.** Your model's hard cap is $300/market. Your plan is $2,000 on a $1–3k book — you'd *be* the market, moving price both ways and taking concentrated tail risk. **Either keep per-month exposure near book-depth/3, or accept you're running well outside the model's risk framework and size the tail accordingly.**
- **Stay maker.** July's $25 fees (7× June) came from crossing the spread during the spike. Maker = 0 fee = another edge.

### Risk / portfolio
- **August is the *start*, not the peak.** Don't spend the bankroll on the weakest El Niño month. Reserve the bulk for **Oct/Nov/Dec** (softer records + stronger El Niño).
- **Sell September.** The 1.41 record is a wall; September YES is the one clean *sell-the-longshot* left. Fund your Q4 YES buys with September YES-selling premium.
- **Size the El Niño basket as one correlated bet.** Long YES across Aug–Dec all pay together if El Niño delivers and all decay together if it fizzles. That's one position, not five — cap the *aggregate* tail, and buy a little September NO... actually the natural hedge is the September YES-sell (short the one month that won't break, long the months that might).
- **The tail that ends you** is a single oversized month going to a record against a NO position. In the El Niño window the record risk is *up*, so the old "NO everything" reflex is the losing habit — which is exactly why your instinct to flip toward YES is right, as long as it's sized.

### Model / signal
- **The fundamental leads price ~2–3 days** (Jul 15 model → Jul 18 price). Watch each ECMWF run; act on the run, not the tape. This is your cleanest edge in a surge.
- **Trust the 51-member ensemble P, not the deterministic point.** The 0.0% point estimate that hid real tail mass in July would be even more dangerous in an El Niño month where the tail is fat. The member distribution is the anchor for every fair-value and gate decision.
- **Automate the divergence trigger:** `|market_YES − ens_P| > 15¢` → alert, with direction (market ≫ model → fade/sell YES; market ≪ model with dev3 warm → ride/buy YES). You compute both numbers into `data.js` every 15 min; this is a few lines.
- **ONI is the slow thesis dial.** Rising ONI → rising record odds, escalating toward Q4. Update the record-map read as ONI prints monthly.

### Other / meta
- **Build the NOAA release snipe before the Aug print (~Sep 10–14).** El Niño months are exactly where *surprise* prints (record when the book underpriced it) happen — the snipe's big-payoff scenario. Needs order code (you're read-only) + an always-on runner (not the laptop that slept in June).
- **Cross-platform basis.** Polymarket's August/Q4 markets settle on **GISTEMP** (runs ~+0.09 warmer than NOAA). When the two platforms' implied YES diverge *beyond* that structural gap, sell the rich / buy the cheap — a basis trade, not arbitrage.
- **Calendar relative value.** If Oct YES is 15¢ and Sep YES is 15¢, they are *not* the same bet (Oct margin −0.03 vs Sep −0.22). Buy Oct, sell Sep — a within-series relative-value pair that's near-neutral to the overall warming level.
- **Income layer under the directional core.** Independent of your Aug/Q4 direction: keep harvesting the retail-YES-overshoot (sell the fear spikes that revert) and the maker spread. That's the steady drip that funds the lottery tickets.

---

## 4. A concrete recommended structure (illustrative allocation of ~$2,000)

Instead of $500 Aug-YES + $1,500 waiting for a 60¢ dip that may never come:

| Bucket | ~$ | Purpose |
|---|---|---|
| **August YES starter** | $200–300 | limit ≤10¢, scale in, ladder-out on spikes. Small — August is the weakest El Niño month. |
| **August spike-fade / income** | $200 | resting YES asks at 30–45¢ to sell overshoots; resting NO bids only when model-gated (P<35%). |
| **September YES-SELL** | $300 | your proven engine on the one un-breakable record (1.41). Funds the rest. |
| **Q4 YES core (Oct/Nov/Dec)** | $700–900 | the real El Niño value; deploy as each opens, sized to book, model-timed. Oct first. |
| **Release-snipe / dry powder** | $300 | for surprise prints and genuine model-confirmed runs (Scenario C add). |

The point isn't the exact split — it's: **less on August, keep selling September, weight the real money to Oct/Nov/Dec, gate every NO buy on the model, and be the resting liquidity instead of the taker.**

---

## 5. The five rules, compressed

1. **Buy YES where the record is soft vs the El Niño trend (Oct best), sell YES where it's a wall (Sep). August is a small starter.**
2. **Gate every NO purchase on the ensemble (P<35% + no fresh forecast high), never on the 60¢ price.** This is July's mistake, pre-empted.
3. **Rest your orders; don't chase.** Sell spikes with resting asks, buy panic with resting bids, sized to the book.
4. **Distinguish overshoot (fade) from real run (ride) by the forecast_log timestamp — you already log it.**
5. **Size to book depth and reserve for Q4.** One oversized record-month against you is the only thing that ends this.
