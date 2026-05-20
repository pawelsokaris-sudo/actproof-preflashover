# Preregistration — ActProof Pre-Flashover Detection in Grandmaster Chess

**Author:** Paweł Łuczak, Sokaris Oprogramowanie / ActProof
**Co-author of preregistration:** Claude (Anthropic), in advisory capacity
**Document status:** FROZEN — to be timestamped by Git commit + signed tag before any data collection begins.
**Commit hash of analysis code at time of freeze:** `<TO BE FILLED ON COMMIT>`
**Date of freeze:** `<TO BE FILLED ON COMMIT>`

---

## 1. Background and motivation

The ActProof framework posits that complex adaptive systems exhibit *flashovers* — phase-transition-like events in informational tension — that **temporally precede** classical turning points (errors, sacrifices, regime changes). Prior anecdotal evidence: the AlphaGo–Lee Sedol Game 2 analysis suggested the true critical event was Lee's move 38 (response), not AlphaGo's celebrated move 37. A pilot run of the ActProof Chess Sensor on Kasparov–Topalov 1999 identified the "mysterious" 12.Kb1 as the strongest flashover, twelve plies before the rook sacrifice. Both observations are n=1. This preregistration converts the hypothesis into a falsifiable test on n=50 independent grandmaster games.

## 2. Hypothesis

- **H₀ (null):** The temporal distribution of top-1 flashovers, relative to first turning points within the same game, has median lag = 0 plies (i.e., flashovers are uniformly distributed with respect to turning points).
- **H₁ (ActProof):** Median lag > 0 plies — flashovers systematically precede turning points.

## 3. Operational definitions — FROZEN

### 3.1 Turning Point (TP)
Let `eval(P)` be the Stockfish evaluation of position `P` in centipawns, White-perspective, with mate scores converted via `mate_in_N → sign × (20000 − 100·N)`. For ply `t` where side `S` just moved:

- `Δ_t = eval_after − eval_before`, both expressed from S's perspective.
- `t` is a Turning Point iff `Δ_t ≤ −150` cp (S blundered by ≥ 1.5 pawns).
- **First TP of the game** = `min{ t : TP_t = true }`.
- Games with no TP in first 80 plies → **excluded** (treated as balanced, ineligible for the test).

### 3.2 Stockfish configuration — FROZEN
- Engine: **Stockfish 16 or newer**, single binary version recorded per game.
- Mode: **deterministic** — `Threads=1`, `Hash=256MB`, `MultiPV=1`, **depth = 22** fixed (no time limit).
- Identical configuration for every position in every game. No re-evaluation under different settings.

### 3.3 Top-1 Flashover (FO)
From the ActProof Chess Sensor (`actproof_chess.py`, `actproof_dynamics.py`):

- Compute composite signal: `composite[t] = max( z(|dE/dt|), z(|dT_max/dt|), z(|dS/dt|) )` where z(·) is per-game z-score of absolute first differences (np.gradient).
- Top-1 Flashover ply = first peak found by `scipy.signal.find_peaks(composite, prominence=0.8, distance=2)`, ranked by composite magnitude. If `find_peaks` returns empty, fallback = `argmax(composite)`.
- Only top-1 used in primary test. Top-3 saved for descriptive secondary analysis only.

### 3.4 Lag
`lag = ply(first_TP) − ply(top-1_FO)`.
Positive lag → flashover precedes turning point (ActProof prediction).

### 3.5 Sensor parameters — FROZEN
- `FieldConfig(grid_resolution=64, epsilon=0.1, signed=True)`
- Masses: `{P:1, N:3, B:3, R:5, Q:9, K:100}` — standard, no tuning permitted.
- `ActProofSensor.beta = 0.01` (irrelevant for top-1 FO, but frozen for reproducibility).
- Kernel: `1 / (r + ε)`. No switch to `−log(r)` after freeze.

## 4. Dataset — FROZEN

- **Source:** Lichess Elite Database (https://database.nikonoel.fr/), monthly archive **2024-06**, single file.
- **Filter:** both players Elo ≥ 2600, classical time control (≥ 30+0), decisive result (1-0 or 0-1), ≥ 30 plies, no engine games, no opening-book truncation.
- **Sampling:** after filter, sort PGN by event date then game-in-file index; take first **50 games** that pass. RNG seed not needed because sampling is deterministic by sort order. Game IDs published in repository at freeze time.
- **Sample size:** **n = 50**. No top-up sampling. No replacement of excluded games beyond the first 50 that match filter.

## 5. Statistical procedure — FROZEN

### 5.1 Primary test
- **Wilcoxon signed-rank test, one-sided** (`scipy.stats.wilcoxon(lags, alternative='greater')`).
- **Significance threshold:** α = **0.01**.
- **Minimum effect size for "positive" verdict:** median(lag) ≥ **1.0 ply**.
- **Both criteria must be met** for ActProof to be considered supported.

### 5.2 Random-permutation baseline
For each game, draw 1000 random plies uniformly from `[1, game_length]` as pseudo-flashover. Compute pseudo-lag distribution. Test that observed median lag exceeds 95th percentile of permutation-distribution median lags.

### 5.3 Decision matrix — FROZEN

| Primary test (p, median) | Permutation baseline | Verdict |
|---|---|---|
| p < 0.01 AND median ≥ 1.0 | observed > 95th pct | **Hypothesis supported** — proceed to Go replication with KataGo |
| p < 0.01 AND median ≥ 1.0 | observed ≤ 95th pct | **Inconclusive** — signal exists but not distinguishable from chance ply distribution; reformulation REQUIRED before further claims |
| p ≥ 0.01 OR median < 1.0 | — | **Hypothesis falsified** — temporal pre-flashover structure not present at preregistered effect size. No reframing under same prediction permitted. |

## 6. Frozen degrees of freedom — what CANNOT change after timestamp

- Definitions of TP, FO, lag, composite signal.
- All sensor and Stockfish parameters listed above.
- Dataset source, filter criteria, n=50, sampling order.
- Statistical test, α, minimum effect size, baseline procedure, decision matrix.
- Inclusion / exclusion rules.

**Any change to the above invalidates the preregistration.** If a defect is discovered mid-experiment, the run is aborted, the defect documented in a public addendum, and a new preregistration is filed with a new timestamp before re-running.

## 7. What CAN change

- Visualisation, reporting format, secondary descriptive analyses (clearly labeled as exploratory).
- Compute infrastructure, parallelisation, caching strategy — provided outputs are bit-identical.

## 8. Outputs and publication commitment

- Full results (raw lag values, p-value, median, baseline percentile) published in repository **regardless of outcome** within 14 days of analysis completion.
- Negative or inconclusive result published with **equal prominence** as positive.
- All 50 game IDs, Stockfish evals, sensor traces, and analysis logs released as supplementary data.
- Repository: `github.com/pawelsokaris-sudo/actproof-preflashover` (to be created at freeze time).

## 9. Honest-failure clause

I, the author, commit explicitly to **not** rescuing the framework by:
- redefining "flashover" or "turning point" after seeing results,
- excluding games post-hoc,
- changing parameters in response to observed data,
- adding new "channels" to the composite signal,
- selecting a subset of games for sub-analysis presented as primary,
- testing additional hypotheses on the same dataset and reporting only the favourable one.

If any of the above is required to obtain a positive result, the result is **null** by definition of this document.

---

## Sign-off

- **Author signature (timestamp via GPG-signed Git tag):** `<TO BE FILLED>`
- **Repository commit hash at freeze:** `<TO BE FILLED>`
- **SHA-256 of this document at freeze:** `<TO BE FILLED, computed on final version>`

---

*This preregistration follows the spirit of AsPredicted.org and the OSF Standard Pre-Data-Collection Registration. It is a binding intellectual contract between the author and future-self.*
