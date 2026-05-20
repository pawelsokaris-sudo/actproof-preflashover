# ActProof — Pre-Flashover Detection

A preregistered empirical test of the ActProof framework's central temporal claim:
**that informational flashovers systematically precede classical turning points
in adversarial games.**

## Status

**FROZEN at `freeze-v1.2` — preregistration phase.** No data collected.

The authoritative protocol is `PREREGISTRATION-v1.2.md`. The original
`PREREGISTRATION.md` (`freeze-v1.0` / `freeze-v1.1`) is preserved in the repository
for historical record but is superseded.

Read in this order:
1. `PREREGISTRATION-v1.2.md` — current binding protocol.
2. `ADDENDUM-001.md` — bot-filter fix (between v1.0 and v1.1).
3. `ADDENDUM-002.md` — dataset migration from Lichess Elite to TWIC (between v1.1 and v1.2).
4. `PREREGISTRATION.md` — historical, superseded.

## Files

| File | Purpose |
|------|---------|
| `PREREGISTRATION-v1.2.md`        | **Current** binding experimental protocol. Frozen at `freeze-v1.2`. |
| `PREREGISTRATION.md`             | Historical (v1.0/v1.1). Superseded. Kept for record. |
| `ADDENDUM-001.md`                | Bot-filter defect documentation. |
| `ADDENDUM-002.md`                | Dataset inadequacy + migration to TWIC. |
| `actproof_chess.py`              | ActProof Chess Sensor — measurement instrument. Frozen at `freeze-v1.0` (unchanged). |
| `actproof_dynamics.py`           | Trajectory dynamics, flashover detection. Frozen at `freeze-v1.0` (unchanged). |
| `data_collection.py`             | Data pipeline: TWIC downloader + Stockfish evaluator + flashover extractor + statistics. |
| `requirements.txt`               | Runtime dependencies with pinned versions. |
| `results/`                       | (post-data) Raw evals, sensor traces, lag distribution, archive SHA-256, final report. |

## Verifying the freeze

```bash
git verify-tag freeze-v1.2     # tag signature / annotation check
git log freeze-v1.2 -1         # commit hash + date
sha256sum PREREGISTRATION-v1.2.md
```

The annotated tag is the authoritative timestamp. Any change to frozen files
after the tag invalidates the preregistration and is documented in a public
addendum.

External archival: search the repository URL on https://archive.softwareheritage.org/

## Hypothesis (one sentence)

In TWIC tournament classical chess games at GM level (Elo >= 2600), the top-1
flashover identified by the ActProof Chess Sensor occurs at median lag
>= 1 ply *before* the first turning point as defined by a Stockfish
evaluation drop of >= 150 cp from the moving side's perspective.

## Honest-failure clause

This repository commits to publishing the result regardless of direction.
A negative result (no temporal pre-flashover structure) is a valid and
intended possible outcome of this experiment.

## Author

Pawel Luczak, Sokaris Oprogramowanie — independent ActProof research.
Documents drafted in collaboration with Claude (Anthropic) in advisory capacity;
all scientific decisions and accountability are the author's.

## License

MIT (code), CC-BY-4.0 (preregistration and reports).
