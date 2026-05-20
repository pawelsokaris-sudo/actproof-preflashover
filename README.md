# ActProof — Pre-Flashover Detection

A preregistered empirical test of the ActProof framework's central temporal claim:
**that informational flashovers systematically precede classical turning points
in adversarial games.**

## Status

**FROZEN — preregistration phase.** No data has been collected at the time of
the `freeze-v1.0` signed tag. All definitions, parameters, datasets, and
statistical procedures are committed to the repository in advance.

Read `PREREGISTRATION.md` first.

## Files

| File | Purpose |
|------|---------|
| `PREREGISTRATION.md` | Binding experimental protocol. Frozen at `freeze-v1.0` tag. |
| `actproof_chess.py`  | ActProof Chess Sensor — measurement instrument. Frozen. |
| `actproof_dynamics.py` | Trajectory dynamics, flashover detection, β-scan. Frozen. |
| `data_collection.py` | (post-freeze) Lichess Elite downloader + Stockfish evaluator + flashover extractor + statistics. To be added after freeze. |
| `results/` | (post-data) Raw evals, sensor traces, lag distribution, final report. Will be added regardless of outcome. |

## Verifying the freeze

```bash
git verify-tag freeze-v1.0      # GPG signature check
git log freeze-v1.0 -1          # commit hash + date
sha256sum PREREGISTRATION.md    # document hash
```

The signed tag is the authoritative timestamp. Any change to frozen files
after the tag invalidates the preregistration and is documented in a public
addendum.

## Hypothesis (one sentence)

In grandmaster classical chess games with a decisive result, the top-1
flashover identified by the ActProof Chess Sensor occurs at median lag
≥ 1 ply *before* the first turning point as defined by a Stockfish
evaluation drop of ≥ 150 cp from the moving side's perspective.

## Honest-failure clause

This repository commits to publishing the result regardless of direction.
A negative result (no temporal pre-flashover structure) is a valid and
intended possible outcome of this experiment.

## Author

Paweł, Sokaris Oprogramowanie — independent ActProof research.
Document drafted in collaboration with Claude (Anthropic) in advisory capacity;
all scientific decisions and accountability are the author's.

## License

MIT (code), CC-BY-4.0 (preregistration and report).
