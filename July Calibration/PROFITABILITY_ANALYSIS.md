# KXHMONTH — Full Profitability Analysis & Money-Making Gaps

*Grounded in the live account (225 real fills, settlements, positions pulled 2026-07-23) and the full public trade flow for the June & July markets. Every P&L number is reconciled against Kalshi's authoritative `position_fp` / `realized_pnl` fields, not estimated.*

---

## 0. The money map (TL;DR)

There are **six** distinct ways this market pays, ranked by proven edge and by how much room is left:

| # | Money source | Proven? | Capacity | Status in your book |
|---|---|---|---|---|
| 1 | **Longshot-premium decay** (sell YES / buy NO on a market that verifies NO) | ✅ 6/6 months settled NO | ~\$1–3k/mo | **This is your engine.** Running it. |
| 2 | **Maker spread capture** (post resting orders, 0 fee, get lifted by impatient retail) | ✅ 93% maker in June | book-bound | Doing it, not maximally. |
| 3 | **Fade the forecast-fear overshoot** (market spikes above model on a scare) | ⚠️ capturable, **you did the opposite** | small | **Gap — cost you ~\$256 in July.** |
| 4 | **Ride the surge** (buy cheap YES when your model detects heat the market hasn't priced) | ⚠️ real on Jul 15→18 (22¢→48¢) | small | **Untapped — the "double your money" play.** |
| 5 | **NOAA release snipe** (fire on the print before the book reprices) | ✅ directionally (June exact hit) | \$1–3k/event | **Untapped — no order code yet.** |
| 6 | **Cross-platform basis** (Kalshi-NOAA vs Polymarket-GISTEMP, ~+0.09 gap) | ⚠️ structural, unmonitored | Poly depth | **Untapped.** |

**Bottom line:** your bread-and-butter (1+2) is real and working, but it's capacity-capped and carries concentrated tail risk. The incremental money is in (3), (4), (5) — all of which are **signal-driven and automatable**, and two of which (3, 4) were sitting in the July data this month and you either missed or fought.

---

## 1. What actually happened — the real track record

**Every KXHMONTH month in 2026 has settled NO.** No month has been a record. The settlement feed confirms it:

| Month | Result | Net NO into settle | Your play |
|---|---|---|---|
| JAN | NO | 0 (round-tripped flat) | scalped decay |
| FEB | NO | 0 | scalped decay |
| MAR | NO | 0 | scalped decay |
| APR | NO | 0 | scalped decay |
| MAY | NO | 0 | scalped decay |
| JUN | NO | **937 held** → \$937.29 paid | held to settlement |
| JUL | *open* | **1,922 NO** | oversized, underwater |

### Reconciled P&L (the fills window, May 18 → now)

| Month | NO bought | Closed early | Net NO | Maker % | Cash flow | Fees | **Realized/Marked P&L** |
|---|---|---|---|---|---|---|---|
| MAY (partial) | 1,248 | 1,247 | 0 | 41% | +\$51 | \$3.3 | **+\$48** |
| JUN | 4,629 | 3,692 | 937 | **93%** | −\$683 | \$3.5 | **+\$251** |
| JUL (open) | 3,696 | 1,774 | 1,922 | 67% | −\$1,740 | \$25.3 | **−\$420** (mark @70¢) |

**The strategy, revealed by the fills:** you systematically **buy NO at ~85–96¢ and sell YES at ~2–7¢** (both are the same bet: "not a record"), overwhelmingly as a **maker** (resting orders, 0 fee). You close a chunk mid-month for a scalp and carry a residual into settlement. June is the clean win: bought NO averaging 91.7¢, closed 3,692 for a scalp, held 937 to collect \$937 when June printed 1.09 (< 1.18). **+\$251 net.**

**The July problem is visible in the same table:** 1,922 net NO, **\$1,484 exposure** — roughly **5× the \$300 model risk cap** — and \$25 in fees (7× June's) because you crossed the spread (only 67% maker) during the volatility. The −\$256 realized piece of that −\$420 is the specific thing Section 5 dissects.

---

## 2. Profit engine #1 — longshot-premium decay + maker spread

### Why it works
"Hottest month ever" is a **lottery ticket**. Retail wants to *buy* YES (the exciting outcome), so YES carries a persistent premium above its true probability, and that premium **bleeds to zero as the month verifies NO**. You are the house selling the lottery ticket.

The flow proves the decay cleanly. **June YES price path** (public trades, daily high):

```
May29  Jun05  Jun10  Jun15  Jun20  Jun25  Jun30   → settle
 21¢    15¢    18¢     9¢     5¢     5¢     7¢     → NO (0)
```

YES melted from ~21¢ to low-single-digits over the month. Anyone long NO / short YES from early on rode that to par. **You captured it as a 93%-maker** — you didn't pay the spread, you *earned* it, because impatient YES buyers lifted your resting NO.

### The even-cleaner signal: model-vs-market gap
The best entries are when the model says the longshot is already dead but the market hasn't caught up. **July 11–15** is textbook: the dip had verified, the ensemble said **P(YES) = 0.0–2.9%**, yet **market YES sat at 20–24¢** (`track_log` lines 7–10). Selling YES / buying NO there was ~18–24¢ of edge on a near-certainty. That is free money and you were on the right side of it.

### The limits (why this alone isn't enough)
- **Capacity:** ~\$1–3k of resting depth per month → hundreds of dollars, not thousands.
- **Tail risk:** you're short a lottery ticket. **One record month pays −\$1 per contract** and erases many months of pennies. July is showing you exactly this fang (see §7).

---

## 3. Making money in a ~\$10 book (the thin-liquidity regime)

You asked specifically about the tiny-liquidity days. They're real and they're in the July launch flow:

```
Jun27  Jun30  Jul03  Jul04  Jul05   (July market, first week)
719v   62v    163v   19v    37v      ← daily volume in contracts
8 tr   3 tr   12 tr  2 tr   5 tr     ← that's ~$10–150 of real flow
YES range: 7–27¢  (Jun27)  ← a 20¢-wide spread on the launch day
```

**Why a patient NO maker still profits in a \$10 book:** the spread is enormous (7–27¢ on launch) because there's no competition. Someone *always* eventually shows up wanting the "hottest month" lottery YES. If your NO bid is resting at, say, 88¢ (YES 12¢) and an impatient YES-lottery buyer crosses, you're instantly holding NO you'll ride to par. **In thin books the edge isn't volume, it's the width** — you get filled at prices that are absurd relative to fair, precisely because no one else is quoting. The cost is patience (capital sits idle) and the risk is that the one fill you get is on a day that turns into a record.

**Implication for you:** the thin early-month days are *higher* edge-per-contract than the liquid late days, just lower total size. Don't ignore them for being "only \$10" — quote them, because your fill price is best there.

---

## 4. Volatility spikes, cross-validated across sources

Volatility in this market is not random — it fires on **four identifiable triggers**, each traceable to a specific data source:

| Trigger | Signature in flow | Source that caused it |
|---|---|---|
| **Contract launch** | wide range, tiny volume (Jul YES 7–27¢, 8 trades) | uncertainty, no quotes |
| **Print approach** | volume explosion (June: Jul 1–9 ran **10k–21k/day** vs ~1k mid-month) | NOAA settlement clock |
| **Forecast surge/scare** | intraday range blows out (Jul 17–18: YES **20→45→51¢**, 25¢ range) | ECMWF/GFS/ICON model runs |
| **The print itself** | collapse to settlement (June → **1¢ on Jul 10**) | NOAA value released |

### The July 17–18 surge spike — the case study

This is the important one, and it cross-validates perfectly against your own instruments:

| Date | ERA5 signal (`dev3`) | Ensemble P(YES) | Market YES | What it means |
|---|---|---|---|---|
| Jul 13 | +0.015 | 0.0% | 24¢ | dip verified, market asleep |
| Jul 15 | **+0.064** (tripwire FIRES) | 2.9% ↑ | 21–22¢ | actuals running warm, market hasn't noticed |
| Jul 18 | **+0.134** | 6.4% → 24.7% | **spike to 48–51¢** | market violently reprices the surge |
| Jul 19 | +0.145 | 24.7% | back to 24–31¢ | overshoot reverts |
| Jul 21 | +0.175 | **40.8%** | 20–21¢ | surge confirmed; now market *below* model |

Three independent sources agreed a real heat surge was coming (the `dev3` deviation of observed ERA5 warmer than forecast, the rising 51-member ensemble tail, and all three weather centers' runs). The market's **intraday spike to 48–51¢ on Jul 18 was an overshoot** (even the bullish ensemble said 6–25% at that moment), but the **sustained move to ~28¢ was correct** (the ensemble caught up to 40% by Jul 21). **This is the anatomy of every tradable spike in this market: a real signal, over-amplified intraday by retail fear, then partially reverting.**

---

## 5. The contrarian +EV plays — were they capturable *before* the move?

You asked the sharp question: when playing *against* the market's fair-looking odds paid off, was that **capturable on a prior observation of expected value**, or just luck? For July, the answer is **capturable, with a named trigger, both directions.**

### Play A — Ride the surge (the "double your money" example, real this month)

**Setup (Jul 15):** market YES **21–22¢**. Your `dev3` tripwire had just fired (+0.064, three straight days of actuals warmer than forecast) and the 51-member ensemble tail-P had started climbing (0.0% → 2.9%, with the 12z runs showing the surge). **Prior observation = a live, strengthening warm signal the market had not priced.**

**Action:** buy YES at 22¢.
**Outcome (Jul 18):** market spikes to 45–51¢. Sell at ~45¢.
**Result: +23¢ on a 22¢ ticket ≈ +105%. You doubled it in 3 days.**

**Was it +EV *ex ante*?** Yes. Frame it as your example (risk to double):
$$EV = P(\text{surge reprices}) \cdot (+23) - P(\text{fizzle}) \cdot (\text{decay} \approx 17)$$
On Jul 15 the surge signal was *strengthening* across all three centers, so $P(\text{reprices in 3 days})$ was well above the break-even $\frac{17}{23+17}=43\%$. Even a coin-flip read gives $EV = 0.5(23) - 0.5(17) = +3¢$ (+14% on risk). The asymmetry (capped ~17¢ downside from a longshot that can't fall far, open upside as fear amplifies) plus a live warming trigger = **clearly positive EV, and it's exactly the "lose \$200 or double it" structure you described.** The trigger was mechanical: **`dev3` firing + ensemble tail-P rising + market YES still cheap.**

### Play B — Fade the overshoot (the one you got backwards)

**Setup (Jul 18, 05:00Z):** market YES **48¢**. At that exact moment your ensemble said **P(YES) = 6.4%** (`track_log` line 11). Fair NO ≈ 93.6¢; the market was offering NO at ~52¢.

**The +EV action was to BUY NO at 52¢** (edge ≈ +41¢ vs the model; even against the *later*, higher 24.7% ensemble read the fair NO was ~75¢, so still +23¢).

**What you actually did:** you **sold** NO into the spike (closed at ~52¢), realizing the **−\$256** that dominates your July loss. You traded *against your own model* at the single most dislocated moment of the month.

**Why this is the highest-value lesson:** the fade was capturable on a prior observation — the observation being *your own live ensemble number*. The gap wasn't analytical (the model was right, P was 6–25% not 48%); it was **behavioral/operational** — in a fear spike you followed price instead of the model. A rule ("**never reduce NO when market YES > 2× ensemble-P and data is fresh**") would have flipped that −\$256 into a gain.

> The honest caveat: the surge was *real information*, so the correct fade target was 48→~30 (revert the overshoot), **not** 48→6. Fading all the way to the deterministic point estimate would have been the old 0.0%-model mistake. The ensemble, not the point estimate, is the anchor.

---

## 6. The gaps — where more money is (ranked, actionable)

**1. Stop trading against your own model during spikes.** Hard rule: *no reducing NO while market-YES > 2× ensemble-P(YES) and data is not stale.* Directly recovers the July −\$256 pattern. Zero new infrastructure.

**2. Systematic two-sided maker quoting.** You're 93% maker in calm months, 67% when it matters. Post resting NO bids **and** YES asks continuously, size up when the spread is wide (the thin days, §3), and **stay maker through spikes** instead of crossing (July's \$25 fee vs June's \$3.50 is you paying the taker tax at the worst time). You earn the spread *plus* the decay, at 0 fee.

**3. Automate the model-vs-market divergence trigger.** You already compute ensemble-P every 15 min (`update_data.py`) and the market bid/ask sits in the same `data.js`. Add one alert: `|market_YES − ens51.p_yes| > 15¢ → fire`. Direction: if market ≫ model → the fade (buy NO); if market ≪ model with `dev3` warm → the ride (buy YES). This mechanizes both §5 plays. **Highest EV-per-hour of build.**

**4. Position-size discipline (the July lesson).** 1,922 NO / \$1,484 exposure is ~5× your own \$300 cap. The longshot engine only survives if a single record month can't wipe you. Enforce the cap in code before any order fires, not after.

**5. The NOAA release snipe.** The June flow shows the print resolving on Jul 9–10 with 21k volume collapsing to 1¢. The snipe pays *big only on a surprise print* (market priced no-record, print is a record, or vice versa) — which clusters in El Niño Q4. It needs (a) order-placement code (you have read-only only), (b) an always-on runner (the laptop slept through the June poll). Build it cheap before ~Aug 13. It's the one edge with genuine conviction and no directional-forecast risk.

**6. Cross-platform basis (Kalshi-NOAA vs Polymarket-GISTEMP).** GISTEMP runs ~+0.09 warmer, so Polymarket YES *should* trade richer. When the gap between the two platforms diverges **beyond** that structural ~0.09 (translated to price), sell the rich, buy the cheap — a **basis trade, not arbitrage** (different datasets never perfectly offset). Requires monitoring both books; currently unmonitored.

**7. Cross-month portfolio / El Niño tail hedge.** Selling YES every month = concentrated short-lottery risk that all fires together in a hot burst. In a very-strong El Niño Q4 (CPC ~63%), records cluster — "NO everything" becomes the losing habit. Either **size down** in those months or **buy one cheap YES** on the most-likely record month as tail insurance funded by the other months' premium.

**8. Sell the variance collapse.** Late month, when the required-remaining-average becomes physically implausible (e.g., "needs +0.82 with 11 days left"), YES is a near-lock to decay. These are your safest, lowest-variance sells — smaller premium but near-certain. Weight size toward these when the tie-band cushion (7–11% print exactly 1.18 → NO) is also working for you.

**9. Fee optimization.** Kalshi's taker fee peaks at p≈0.5. Never take at mid-prices; that's the most expensive place to trade. Maker-only discipline (gap #2) mostly solves this.

---

## 7. What kills this (risk)

- **The concentrated NO tail.** You are short a basket of correlated lottery tickets. July is the warning shot: a genuine near-record turned your longshot short into a −\$420 open loss at 5× your cap. One actual record month at full size is a multi-month wipe.
- **Oversizing.** The single biggest realized mistake this cycle wasn't the direction — the model NO thesis is fine — it was **size** (5× cap) and **fighting the model in the spike** (−\$256).
- **The sleeping sniper.** The highest-conviction edge (release snipe) is worthless if it runs on a laptop that sleeps through the 11:00 ET print, which already happened in June. Cloud/`caffeinate`, not a loop on the Mac.
- **Model overshoot the other way.** Fading a spike all the way to the deterministic point estimate (the dead 0.0% habit) re-introduces the underdispersion error. Anchor fades to the 51-member ensemble, never the point.

---

## 8. The playbook (decision rules with triggers)

| Condition (prior observation) | Trigger | Action | EV logic |
|---|---|---|---|
| Model P ≪ market YES, data fresh, month verifying NO | `market_YES − ens_P > 15¢` | **Buy NO / sell YES**, maker | longshot decay + divergence |
| `dev3 > +0.05` warm AND ensemble tail-P rising AND YES still cheap | 3-day warm run | **Buy YES** (ride surge) | asymmetric: capped downside, fear-amplified upside |
| Market YES spikes > 2× ensemble-P intraday | fear overshoot | **Add NO / do NOT reduce** | fade the overshoot to the ensemble, not the point |
| Wide spread, thin book (launch/off-hours) | range > 10¢, low vol | **Quote both sides, size up** | best fill price is in thin books |
| Required-remaining-avg physically implausible, late month | variance collapsed | **Sell YES near-lock** | low-variance premium + tie-band cushion |
| Surprise-prone print approaching (El Niño Q4) | print day, big pre-gap | **Release snipe** (needs order code) | latency edge on known release time |
| Exposure approaching \$300 / data stale / structural break | risk gate | **Halt, do not add** | survive the record-month tail |

**One-line synthesis:** your longshot-selling engine is genuinely profitable and correctly run most months, but the incremental money is not in selling more longshots — it's in (a) **automating the model-vs-market divergence trigger** to systematically capture the fear spikes you currently trade by hand (and sometimes backwards), (b) **staying maker and within the size cap** so one record month can't erase the year, and (c) **building the release snipe** before the ~Aug 13 print. The July surge handed you both a +105% ride (missed) and a +41¢ fade (fought) inside 72 hours — both were capturable on signals you already compute.

---

## 9. Cause & consequence — the event chain, reconstructed from the tape

The daily bars in §4 show *that* July was volatile. The intraday tape (trade-by-trade, times in UTC) shows **why**, and the answer is not what it looks like. **The spike was a liquidity event, not an information event** — the information had already arrived days earlier.

### 9.1 The chain, with timestamps

| When (UTC) | Event | Source | Market YES |
|---|---|---|---|
| **Jul 13 13:06** | Model forecasts the **dip**: late-July (Jul 19–25) mean **+0.396** | ECMWF run (`forecast_log`) | 24¢ |
| **Jul 15 11:40** | **Surge is born:** same forecast jumps to **+0.648** (+0.25 in 2 days) | ECMWF run | 22¢ |
| Jul 15–17 | ERA5 actuals verify warm; `dev3` climbs +0.064 → +0.134 | ERA5 daily | drifts 22→28¢ |
| **Jul 18 04:06:55** | **THE TRIGGER: one 1,614-lot yes-taker sweeps the book** 32¢→48¢ | *a single order* | **30→48¢** |
| Jul 18 05:00–05:58 | Follow-on yes-takers → **peak 49–51¢**; **you dump 787 NO here as taker** | momentum + you | 51¢ |
| Jul 18 12:00 | No-takers revert the overshoot 50¢→31¢ | fade | **back to 30¢** |
| Jul 19–22 | **Calm:** 1,200–1,900-lot blocks trade at 20–25¢ with **~0 price impact** | deep MM liquidity | 20–26¢ flat |
| Jul 23 | Model at fresh high (+0.598); yes-takers drive 24→45¢ | new fundamental | rising |

### 9.2 The trigger, dissected

Zooming the tape from 03:43 to 05:02 on Jul 18:

```
03:43:45   ~750 lots yes-taker      29¢ → 32¢    (first probe)
04:06:55   1,614 lots yes-taker     → 48¢         ← the sweep
05:00–05:02  ~150 lots yes-taker     49¢          (followers)
05:02:50   67 lots NO-taker         48¢          (first fade)
```

**One order did it.** At 04:06:55 a single 1,614-contract market buy lifted the entire resting YES-ask stack from ~32¢ to 48¢ — a **16¢ move from one print**. For scale, three days later the *same* size (1,875 lots on Jul 20 18:05, 1,876 on Jul 22 12:04) traded at **21¢ with zero price impact**. Identical order size, opposite outcome. The difference was **the state of the book, not the size of the trade.**

### 9.3 Why it spiked, and why it reverted

- **Why it moved 16¢:** Jul 18 04:06 is an overnight/low-liquidity hour, *and* it was the peak of surge-fear — market makers had **pulled their YES offers** (no one wants to sell the lottery cheap while a record is confirming). Thin one-sided book + one large buyer = a **liquidity vacuum**. The price gapped because there was nothing resting to absorb it.
- **Why it reverted by noon:** the spike carried **no new information** — the surge fundamental was 2.7 days old (born Jul 15 11:40, §9.1). Once the overshoot printed at 50¢ vs an ensemble that said 6–25%, no-takers stepped in (Jul 18 12:00, 8% yes-taker) and pushed it back to 30¢. Same-day round trip.
- **Proof it's a repeatable mechanism, not a one-off:** the *previous* day did the same thing in miniature — Jul 17 13:46, a 1,000-lot yes-taker spiked YES to 45¢ intraday, reverted within the hour. **Two single-order spikes, both into thin books, both reverting.** That's a mechanism, not luck.

### 9.4 The calm was also caused — by two things, neither a single trade

You asked whether the *low-volatility ongoing trade* was itself a consequence of a specific action. The tape says the calm (Jul 19–22) is the joint consequence of:

1. **Information stopped moving.** `forecast_log` shows the all-July forecast flat at ~0.53–0.57 across Jul 18–22 — no new model surprises. With nothing to reprice, there's nothing to trade on.
2. **Market makers returned with deep two-sided size.** The signature is unmistakable: 1,233-, 1,875-, 1,876-lot blocks trading at 20–25¢ with **no price move**. That only happens when someone is resting hundreds-to-thousands of contracts on *both* sides. The calm is not the absence of trading (volume was high — 4,182 lots on Jul 20 18:00); it's the presence of **depth** that absorbs flow without moving price.

So: **calm ≠ quiet. Calm = deep liquidity + stable information.** Remove either (a big order at an illiquid hour, or a fresh model surprise) and you get a spike. The Jul 23 move is the second kind returning (new fundamental high).

### 9.5 Your own action in the chain (you were an amplifier, not a cause)

You were not the trigger — the 1,614-lot buyer was external. But your fills sit *inside* the chain as a reaction that cost you:
- As YES crept 22→30¢ (Jul 17 23:00 → Jul 18 03:00) you began **closing NO** (763 lots at ~29¢).
- At the **05:00–05:58 peak** you dumped **787 more NO as a taker at ~49–51¢** (the 774-lot print at 05:58:32 is yours). Per your own model at that minute (ensemble P = 6.4%, fair NO ≈ 94¢) you sold NO worth ~94¢ for ~49¢. **That single window is ~\$220 of the −\$256 July realized loss.**
- Then in the calm you *added* 980 NO at 21¢ (Jul 20 18:00) — into the deep liquidity — at a moment the ensemble had risen to ~40% (fair NO ≈ 60¢), i.e., paying up for NO right as your model said NO was getting rich.

The pattern: you **sold NO at the fear peak and bought NO in the calm** — the exact inverse of the liquidity-vacuum edge. The mechanism that hurt you is the one to trade *with*.

### 9.6 What this buys you (the rules that fall out of the causality)

1. **The fundamental leads the price by ~2–3 days.** The surge was in the model on Jul 15; the price spiked Jul 18. That lag *is* the ride-the-surge window (§5A) — you can act on the model run before the tape catches up.
2. **Spikes are liquidity vacuums that revert — fade them toward the ensemble.** When a single large taker gaps the price at an illiquid hour with **no new model run behind it**, it is mechanically likely to revert. Buy the NO the panic is throwing away (or sell the spiked YES), targeting the ensemble level, not the point estimate.
3. **Post resting depth *before* the vacuum, not into the calm.** The money is in being the resting offer that the 1,614-lot buyer has to lift at 48¢ — i.e., quoting YES asks into the fear when others pull. That requires pre-positioned maker orders and nerve, and it is the exact opposite of what you did.
4. **Distinguish the two spike types in real time.** Spike + no fresh `forecast_log` change = **fade** (liquidity event, Jul 18). Spike + a new model high = **respect/ride** (information event, Jul 23). The `forecast_log` timestamp vs the trade timestamp is the discriminator, and you already log both.
