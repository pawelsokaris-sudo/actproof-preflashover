# ADDENDUM-004 — Stockfish per-position timeout, partial run abort, freeze-v1.4

**Status:** Issued **during** the first preregistered run under `freeze-v1.3`, after 18h 19min of compute on game [20/50] showed no progress (single position pure-CPU lock with zero output syscalls over an instrumented 10-second `strace` window). Per PREREGISTRATION-v1.2 §6, the run is aborted, the defect documented, and a new preregistration tag (`freeze-v1.4`) is filed before re-running.
**Affected code state:** `data_collection.py` at SHA-256 `e6fecb0539b35058dcb19cc01757b4a4e93b52edd81c85e9706c1356f88a9dcb` (committed at `d634a508`, frozen at `freeze-v1.3`).
**Aborted run:** started 2026-05-20 ~21:00 CEST, aborted at game [20/50] after ~18.5h compute.
**Affected runs:** zero preregistered runs were completed under `freeze-v1.3`. Data from the aborted run **MUST NOT** be used in any analysis under any preregistration; 19 partially evaluated game caches remain on disk for replicability inspection only.
**Corrected commit:** `<TO BE FILLED ON COMMIT>`
**New preregistration tag:** `freeze-v1.4` (supersedes `freeze-v1.3`; statistical and sensor protocol unchanged).

---

## 1. What happened

The first preregistered run under `freeze-v1.3` began with 19 successfully analysed games (11 valid lags, 8 excluded for `no_tp_in_first_80_plies`). On game [20/50] — Kollars,Dmitrij (2614) vs Ponomariov,R (2622), 153 plies, FIDE World Cup 2023 — Stockfish 18 entered a single-position analysis call (`engine.analyse(board, Limit(depth=22))`) that did not return for over 15 hours.

Diagnostic `strace` on the engine's worker thread captured zero `write` syscalls over a 10-second window, while the thread maintained 99.9% CPU. This pattern is consistent with either:

- **Scenario A:** Honest iterative deepening on a pathologically resistant position (deep tactical or table-base-boundary endgame).
- **Scenario C:** A search-tree state that does not converge in practical time due to either engine internals or input position structure.

The diagnostic cannot distinguish A from C without `gdb` attachment, which would interfere with the running process. Either scenario indicates that the frozen specification `depth=22, no time limit` (PREREGISTRATION-v1.2 §3.2) is operationally unsafe for the dataset: positions exist for which it produces unbounded wall-clock time.

## 2. Root cause

PREREGISTRATION-v1.2 §3.2 specified `Mode: deterministic — Threads=1, Hash=256MB, MultiPV=1, depth = 22 fixed (no time limit)`. The clause `no time limit` was written under the implicit assumption that depth=22 is always reachable in bounded time on any chess position. This assumption is empirically false: search-tree shape for some positions resists alpha-beta pruning sufficiently that depth-22 convergence requires wall-clock times incompatible with a 50-game run.

This is a defect of the original specification, not of the implementation. The implementation faithfully executed `engine.analyse(Limit(depth=22))` exactly as written.

## 3. Why this requires a new preregistration tag

ADDENDUM-001 and ADDENDUM-003 were classified as implementation fixes — they corrected code to faithfully execute frozen criteria. ADDENDUM-002 was a Source change — same criteria, different dataset.

ADDENDUM-004 is **different in kind**: it changes a frozen criterion (`no time limit` → `with 600s per-position timeout`). The justification is operational, not scientific (we do not learn from waiting weeks for one position), but the change is substantive enough to warrant full preregistration treatment: new document section, new freeze tag, public addendum.

## 4. Correction

### 4.1 Frozen criterion change (PREREGISTRATION-v1.4 §3.2)

`Mode: deterministic — Threads=1, Hash=256MB, MultiPV=1, depth = 22 fixed, **with per-position wall-clock timeout of 600 seconds**.`

A position evaluation that has not returned a result at the requested depth within 600 seconds raises `PositionTimeoutError`. Rationale for the specific value: 600s is approximately 2× the longest observed honest depth-22 evaluation on tactically rich middlegame positions in pilot testing; positions exceeding this are empirically pathological (rich endgame frontiers, table-base boundaries, or non-converging search states). The value is chosen **before** examining the lag distribution of the 19 already-evaluated games to prevent confounding parameter choice with observed effect.

### 4.2 New exclusion category (PREREGISTRATION-v1.4 §4)

A game in which any single position evaluation hits the 600s timeout is **excluded as a whole** from the analysis with reason `position_timeout`. Partial-depth evaluations are not mixed with full-depth evaluations. The choice to exclude the whole game rather than interpolate or use the timed-out position's depth-N (< 22) result is the safer one: it preserves the homogeneity of the analysed dataset at the cost of potentially reducing valid-game count.

### 4.3 Implementation

`data_collection.py` is updated:

1. New module-level constant `STOCKFISH_TIMEOUT_S = 600`.
2. New exception `PositionTimeoutError`.
3. `evaluate_game` wraps each `engine.analyse` call with timeout detection via `chess.engine.Limit(depth=22, time=600)` combined with a sentinel check on returned `info["depth"]` vs requested depth.
4. `run_pipeline` catches `PositionTimeoutError`, reinitialises the engine (which may be in undefined state after timeout), and continues to the next game with the current game marked excluded.

### 4.4 What did NOT change

- The hypothesis (H₀ and H₁) — unchanged.
- Turning Point definition — unchanged.
- Top-1 Flashover definition and sensor parameters — unchanged.
- Lag definition — unchanged.
- Statistical procedure (Wilcoxon one-sided, α=0.01, minimum effect 1.0 ply, permutation baseline, decision matrix) — unchanged.
- Dataset (TWIC #1500–#1524, classical-by-exclusion, n=50) — unchanged.
- Honest-failure clause — unchanged.

### 4.5 Sample size implication

n=50 means **50 games selected from the archive in deterministic order**. The number of *valid* games (with both TP and FO ply identified, neither excluded) may be smaller. Under freeze-v1.4, three exclusion reasons exist: `no_tp_in_first_80_plies`, `no_flashover_detected`, `position_timeout`. The decision matrix is applied to whatever valid subset emerges. If the valid subset is too small for Wilcoxon to be meaningful (e.g., n_valid < 10), the analysis script returns `INSUFFICIENT DATA` and we treat that as a separate verdict requiring reformulation — not as silent absence of result.

## 5. Use of partial cache from aborted v1.3 run

The 19 game eval caches from the aborted run remain on disk at `cache/eval_*_d22_*.json`. These caches are deterministic functions of (game_id, depth, engine_version) — they are **bit-identical** to what the v1.4 run would produce for the same 19 games, because the timeout change does not alter the result of evaluations that did successfully complete under v1.3.

Therefore the cache is **valid** to reuse in the v1.4 run: the v1.4 pipeline will check the cache first for games [1-19], find existing files, and skip re-evaluation. This is acceptable because the cached files are causally independent of any unseen data (they were written before this addendum, before any lag-distribution inspection).

If the author has any concern about this — for example, that engine state at the time of caching may have been somehow contaminated — the cache can be wiped before restart. This is the author's call. The honest default is to keep cache (saves ~6 hours of re-compute), but discarding it would not violate any preregistration; it would simply cost time.

## 6. Honest assessment

Four pre-data ADDENDUMS are not nothing. The pattern is consistent: the implementation author (Claude) has repeatedly delivered code tested for syntax and import structure but not sufficiently for live operational behaviour against the actual environment. Three of four ADDENDUMS (001, 003, 004) trace to this systemic deficit. ADDENDUM-002 was a dataset-design oversight of similar nature.

The author of the experiment (Paweł) has, throughout, maintained the discipline of refusing to merge data collection with parameter tuning, even when the temptation was structural (e.g., the v2.0 paradigm proposal of 2026-05-21 morning, which was set aside before this run-recovery decision was made and is therefore not relevant here). This is the function of preregistration working as intended.

The cost of this addendum is: 18.5h of v1.3 compute (recovered as cache for 19 games), one new freeze tag, one public addendum. The cost of having proceeded without timeout would have been: indefinite wall-clock time on some unknown subset of TWIC games, potentially weeks per pathological position, with no defined termination criterion.

## 7. Files at issue

- `data_collection.py` — patched as above.
- `PREREGISTRATION-v1.4.md` — new file (will be added in next commit), differs from v1.2 in §3.2 (timeout) and §4 (exclusion category) only.
- `PREREGISTRATION-v1.2.md`, `PREREGISTRATION.md` — historical, unchanged.
- Sensor code (`actproof_chess.py`, `actproof_dynamics.py`) — unchanged.

## Sign-off

- **Author:** Paweł Łuczak
- **Addendum date:** `<TO BE FILLED ON COMMIT>`
- **Commit hash of corrected `data_collection.py`:** `<TO BE FILLED ON COMMIT>`
- **New preregistration tag:** `freeze-v1.4` (annotated; supersedes `freeze-v1.3`)
