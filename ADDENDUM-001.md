# ADDENDUM-001 — Bot-filter defect, detection, and correction

**Status:** Issued **before** primary data collection. No preregistered run has been performed under the affected code.
**Affected code state:** Smoke test (n=5, depth=12) executed on Stockfish 18 / Ubuntu 24.04, 2026-05-20.
**Repo state at affected run:** `freeze-v1.0` (commits `ea68db3`, `9d150ba`). `data_collection.py` was a post-freeze working file, intentionally uncommitted until smoke verification per the original procedure — see §6 of PREREGISTRATION.md.
**Affected file (never committed):** `data_collection.py` with SHA-256 `71290191c837a1891c3c743f4cb4722ac5162fa78d336bfb3c7db8710b64d040`. The defective line in `passes_filter()` read: `if "[Bot]" in h.get("White", "") or "[Bot]" in h.get("Black", ""):` (verifiable by inspection of any reviewer who reconstructs the file content from this addendum's "Root cause" section).
**Corrected commit:** `574f69bd2f3fb6e71e0c50b89c87df8a875dcd71` (2026-05-20T19:51:01+02:00).
**New preregistration tag:** `freeze-v1.1` (supersedes `freeze-v1.0`; scientific protocol unchanged).

## 1. What happened

The first smoke test of the post-freeze data pipeline (`data_collection.py`) selected 5 games from Lichess Elite 2024-06 under the frozen filter (Elo ≥ 2600, classical, decisive, ≥ 30 plies, "no engine games", standard start). All 5 games were excluded downstream with reason `no_tp_in_first_80_plies`. The verdict line read `INSUFFICIENT DATA — no games with both TP and FO`.

Inspection of the player names revealed that all 10 players in the 5 selected games were **bot accounts** (`Nikitosik-ai`, `abcbot`, `PetersBot`, `BitByByte`, `ELO_1500`, `Mr-Chess-Berserker`). The pipeline had run correctly in mechanical terms; the *defect was in the implementation of the "no engine games" filter criterion specified in PREREGISTRATION.md §4*.

## 2. Root cause

The function `passes_filter()` checked only for the literal substring `"[Bot]"` in the `White` or `Black` PGN headers. This was based on an incorrect assumption about how Lichess marks bot accounts. The canonical convention is:

```
[WhiteTitle "BOT"]
[BlackTitle "BOT"]
```

These header lines are absent from the player-name fields and were not inspected.

Additionally, the Lichess Elite Database (`nikonoel`) is filtered by Elo only — not by player type — so bot accounts with rating ≥ 2600 are routinely present. The author had implicitly (and incorrectly) assumed the dataset was human-only. PREREGISTRATION.md §4 explicitly required `no engine games`; the implementation failed to enforce that frozen criterion.

## 3. Why this matters scientifically

The ActProof hypothesis under test concerns the **temporal structure of cognitive flashover preceding human strategic errors**. Engine-vs-engine games do not contain instances of the phenomenon under investigation:

- Strong engines rarely commit ≥150cp blunders within the first 80 plies of classical games (the frozen TP definition).
- Even when they do, the underlying cause is search-horizon limitation, not the strategic-plan / preparation phase the framework hypothesises.

A 50-game sample populated by engine games would therefore have produced either (a) near-zero valid TP detections, or (b) lag distributions whose interpretation under the ActProof hypothesis would be undefined. Either result would falsify the hypothesis *for the wrong reason*.

## 4. Correction

### 4.1 Code change

In `data_collection.py`, function `passes_filter()`, the line:

```python
if "[Bot]" in h.get("White", "") or "[Bot]" in h.get("Black", ""):
    return False
```

is replaced with:

```python
if h.get("WhiteTitle", "").upper() == "BOT":
    return False
if h.get("BlackTitle", "").upper() == "BOT":
    return False
```

This brings the implementation into compliance with the preregistered criterion "no engine games".

### 4.2 Additional safeguard

A tripwire sanity check has been added to `select_games()`: after assembling the selection of N games, the function inspects all selected games' titles and raises `RuntimeError` if any bot-titled game has slipped through. This is defensive code; under the corrected filter it should never fire.

### 4.3 What did NOT change

- PREREGISTRATION.md is unchanged. The frozen scientific protocol is unchanged.
- Sensor code (`actproof_chess.py`, `actproof_dynamics.py`) is unchanged.
- Statistical procedure, α, effect threshold, decision matrix — unchanged.
- Dataset source, n=50, sampling rule (deterministic by file order after filter) — unchanged.

## 5. Decision: clarification vs. re-preregistration

PREREGISTRATION.md §6 states: *"If a defect is discovered mid-experiment, the run is aborted, the defect documented in a public addendum, and a new preregistration is filed with a new timestamp before re-running."*

This defect was discovered during smoke testing, **before** any preregistered run. No data under the broken filter has been committed to results or analysed under the frozen statistical procedure.

We treat this as a **clarifying implementation fix to a frozen criterion** rather than a change to the criterion itself. The criterion ("no engine games") was always frozen at `freeze-v1.0`; only the code that implements it has been corrected. To maximise transparency, the fix is published with this addendum and a new tag `freeze-v1.1` is created so the corrected implementation is itself cryptographically timestamped before data collection resumes.

## 6. Honest assessment

The smoke test served its function exactly: it surfaced a critical filter defect that would have invalidated the full preregistered run. Had we proceeded to full run without smoke, the cost would have been ~10 hours of Stockfish compute and a meaningless result. The pre-data-collection cost of this addendum is one commit and one paragraph of clarification.

The author acknowledges that the original implementation in `freeze-v1.0` was buggy, and that no informal review caught the bug before smoke. The path forward is: corrected code, new freeze tag, smoke re-run on visibly human-only games, then proceed to full run.

## 7. Files at issue

- `data_collection.py` — patched as above.
- `PREREGISTRATION.md` — **unchanged.**
- All sensor / dynamics code — **unchanged.**

## Sign-off

- **Author:** Paweł Łuczak
- **Addendum date:** `2026-05-20T19:51:01+02:00`
- **Commit hash of corrected `data_collection.py`:** `574f69bd2f3fb6e71e0c50b89c87df8a875dcd71`
- **New preregistration tag:** `freeze-v1.1` (annotated)
