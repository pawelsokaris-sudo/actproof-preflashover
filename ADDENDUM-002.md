# ADDENDUM-002 — Dataset inadequacy, abort, and migration to TWIC

**Status:** Issued **before** any preregistered run. Diagnostic exploratory analysis under §7 of PREREGISTRATION-v1.0 revealed that the frozen Source (Lichess Elite Database 2024-06) contains **zero** games matching the frozen filter criteria of §4. Per §6, the run is aborted and a new preregistration is filed.

**Supersedes:** `freeze-v1.1` (which superseded `freeze-v1.0` via ADDENDUM-001).
**Replaced by:** `freeze-v1.2`, anchored on `PREREGISTRATION-v1.2.md`.
**Affected code state:** `data_collection.py` at SHA-256 `16a4817b16645bcc964d46a8d5e473880c9f70d7919c2df25b9efc184d3b94e9` (committed at `574f69bd` per ADDENDUM-001).
**Diagnostic log:** `results/diagnostic_breakdown.log` (committed with this addendum as supporting evidence).

---

## 1. What happened

After ADDENDUM-001 fixed the bot-filter implementation, smoke v3 ran the corrected pipeline against Lichess Elite 2024-06. It selected zero games and raised `RuntimeError: Found only 0 matching games in archive`. A read-only diagnostic (`diagnostic_filter_breakdown.py`, §7-compliant exploratory analysis) was executed to locate the failure point in the frozen filter cascade. Results below.

## 2. Diagnostic findings

Total games in archive: **253,321**.

| Criterion (independent) | Count | % of archive |
|---|---:|---:|
| Elo ≥ 2600, both players | 45,682 | 18.03% |
| Classical (TC base ≥ 1800s) | 388 | **0.15%** |
| Decisive (1-0 / 0-1) | 224,027 | 88.44% |
| Plies ≥ 30 | 246,412 | 97.27% |
| Standard start (no FEN header) | 253,321 | 100.00% |
| Not a bot | 239,644 | 94.60% |

Cascade in frozen filter order:

| Step | Cumulative count |
|---|---:|
| Elo ≥ 2600 both | 45,682 |
| + classical | **141** |
| + decisive | 17 |
| + plies ≥ 30 | 17 |
| + standard start | 17 |
| + no bot | **0** |

The frozen criteria yield zero matching games. The 17 games that survived the chain until the bot filter were, without exception, bot-vs-bot encounters.

## 3. Root cause

**The Lichess Elite Database is structurally inadequate for the frozen criteria, not marginally so.**

Online play on Lichess is overwhelmingly fast time controls. Of all games in the 2024-06 archive, **0.15% are classical (≥30+0)** — and the intersection with Elo ≥ 2600, decisive, and human-vs-human is empty. Top grandmasters who do play classical games play them over-the-board in tournaments, not online. The author's original choice of dataset implicitly assumed Lichess Elite would supply classical GM-vs-GM games at meaningful rate; this assumption is empirically false.

This is **not** an implementation bug. The implementation of the frozen filter is correct. The dataset itself does not contain the population of games the experiment requires.

## 4. Correction — Source change only

Under PREREGISTRATION-v1.0 §6, this defect is treated as requiring abort + new preregistration. The replacement preregistration `PREREGISTRATION-v1.2.md` differs from `PREREGISTRATION-v1.0.md` in exactly two operational elements; every other element — hypothesis, statistical procedure, decision matrix, effect-size threshold, honest-failure clause — is **bit-for-bit identical**.

### 4.1 Source replacement (§4)

The dataset Source is changed from `Lichess Elite Database 2024-06` to:

> **TWIC (The Week in Chess) archive, issues #1500–#1524 inclusive** (25 weekly issues, ~6 months of GM tournament coverage). Downloaded from `https://theweekinchess.com/zips/twic{NNNN}g.zip`. Concatenated in ascending issue order.

Rationale:
- TWIC is a free, public archive of over-the-board tournament chess games, established 1994, widely used in chess research.
- OTB tournaments are by physical reality classical-time-control (FIDE classical regulations).
- TWIC includes Elo ratings, dates, event and section identifiers; format is standard PGN parsable by `python-chess`.
- Issue range #1500–#1524 is fixed by issue number (not by date) for absolute replicability across time.

### 4.2 Time-control operationalisation reformulation (§3.x)

PREREGISTRATION-v1.0 §4 specified "classical time control (≥ 30+0)" enforced by reading the PGN `TimeControl` header. TWIC's `TimeControl` header is heterogeneous: often absent, sometimes encoded as `40/7200`, sometimes `40/120:G/30`, sometimes empty for events where only round-level time controls are recorded. Direct TimeControl-based filtering is therefore impractical for TWIC.

PREREGISTRATION-v1.2 replaces this with **classical-by-exclusion**, decision (ii) from the design discussion:

> A game is excluded if the `Event` header or the `Section` header contains any of the following literals (case-insensitive): `"Blitz"`, `"Rapid"`, `"Bullet"`, `"Armageddon"`. All other TWIC games are accepted as classical.

The author acknowledges this is a **substantive operational change** to the §3-equivalent criterion, not a cosmetic adjustment. The justification is that all TWIC OTB tournaments are classical by default, with non-classical events explicitly flagged in event names by TWIC convention. Empirical verification of this assumption is part of the smoke test under `freeze-v1.2`.

### 4.3 What did NOT change

The following frozen elements are identical between PREREGISTRATION-v1.0 and v1.2:

- The hypothesis (H₀ and H₁).
- Turning Point definition (eval flip ≥ 150 cp, Stockfish deterministic, depth 22).
- Top-1 Flashover definition (composite z-score, `find_peaks` prominence 0.8, distance 2).
- Lag definition.
- Sensor parameters (grid resolution 64, ε=0.1, signed potential, masses {P:1,N:3,B:3,R:5,Q:9,K:100}, β=0.01).
- Statistical procedure (Wilcoxon one-sided, α=0.01, minimum effect 1.0 ply, permutation baseline with seed 42).
- Decision matrix (supported / inconclusive / falsified).
- Sample size n=50.
- All sensor code (`actproof_chess.py`, `actproof_dynamics.py`) — bit-for-bit unchanged.
- Honest-failure clause.

## 5. Procedural classification

PREREGISTRATION-v1.0 §6: *"If a defect is discovered mid-experiment, the run is aborted, the defect documented in a public addendum, and a new preregistration is filed with a new timestamp before re-running."*

This defect was discovered before any preregistered run (smoke testing only). No data has been collected against any version of the preregistration. The current step strictly follows §6: abort, public addendum, new preregistration tag (`freeze-v1.2`) with separate timestamp.

## 6. Honest assessment

The author's original dataset selection was based on convenience (free, easily downloadable, Elo-curated) without empirical verification that the frozen criteria intersect with the dataset content. The diagnostic step that surfaced this — running a read-only filter breakdown before committing to a 10-hour analysis run — performed exactly the function it was designed for. As with ADDENDUM-001, the pre-data-collection cost of this correction is a public document and one new tag; the cost had it been discovered post-data would have been a meaningless null result interpreted as "ActProof falsified" for the wrong reason.

The author additionally acknowledges that allowing two ADDENDUMS before any data collection is not a sign of poor preregistration — it is a sign that the preregistration is functioning as intended by surfacing defects pre-data, where they can still be corrected without ambiguity.

## 7. Files at issue

- `PREREGISTRATION.md` — unchanged; remains in repository for historical record as `freeze-v1.0` / `freeze-v1.1` reference.
- `PREREGISTRATION-v1.2.md` — **new file**, the authoritative protocol from `freeze-v1.2` onwards.
- `data_collection.py` — **updated** to TWIC downloader + Event/Section-literal filter.
- `actproof_chess.py`, `actproof_dynamics.py` — **unchanged**.
- `ADDENDUM-001.md` — historical, unchanged.
- `ADDENDUM-002.md` — this document.
- `results/diagnostic_breakdown.log` — supporting evidence for this addendum.

## Sign-off

- **Author:** Paweł Łuczak
- **Addendum date:** `2026-05-20T20:56:48+02:00`
- **Commit hash of `data_collection.py` (TWIC version):** `e3f6ce356545f8e9605b8866536104b0af1df5cf`
- **SHA-256 of `PREREGISTRATION-v1.2.md` at freeze:** `feee71c20ab5171aa927bc9b9eb4eca9631b8b911d37a395891f9b62f75ad02b`
- **New preregistration tag:** `freeze-v1.2` (annotated; supersedes `freeze-v1.0` and `freeze-v1.1`)
