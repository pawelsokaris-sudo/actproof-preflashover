"""
data_collection.py — ActProof Pre-Flashover Detection: data acquisition and analysis pipeline.

POST-FREEZE-v1.2 module. Implements (does not redefine) the protocol fixed in
PREREGISTRATION-v1.2.md. All scientific decisions live in that document; this
file is mechanical realisation.

Changes from previous (Lichess) version, per ADDENDUM-002:
  - Source: TWIC issues #1500–#1524 instead of Lichess Elite 2024-06.
  - Filter: classical-by-exclusion on Event/Section literals replaces
    numeric TimeControl threshold (TWIC TimeControl header is heterogeneous).
  - Everything else (sensor params, TP/FO definitions, statistics, n=50,
    decision matrix) — unchanged.

Pipeline stages:
  1. download   — TWIC issue ZIPs, extract PGNs, concatenate in issue order
  2. filter     — select games matching frozen criteria, deterministic order
  3. evaluate   — Stockfish per-position eval at frozen depth, cached
  4. extract    — first turning point (TP) and top-1 flashover (FO) per game
  5. analyse    — Wilcoxon one-sided + permutation baseline + verdict per matrix

Usage:
  # Smoke test — 5 games, reduced depth (NOT a valid result; sanity check only)
  python data_collection.py --smoke-test --stockfish /path/to/stockfish

  # Full preregistered run
  python data_collection.py --full --stockfish /path/to/stockfish
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import urlretrieve

import chess
import chess.engine
import chess.pgn
import numpy as np
from scipy.stats import wilcoxon

from actproof_chess import ActProofSensor
from actproof_dynamics import analyze_trajectory, detect_flashovers


# =====================================================================
# Constants — sourced from PREREGISTRATION-v1.2.md, FROZEN.
# Any change requires ADDENDUM-003 + new freeze tag.
# =====================================================================

# Source — TWIC #1500–#1524 inclusive
TWIC_BASE_URL = "https://theweekinchess.com/zips/twic{n}g.zip"
TWIC_ISSUES   = list(range(1500, 1525))  # inclusive [1500..1524] = 25 issues

DATA_DIR    = Path("data")
CACHE_DIR   = Path("cache")
RESULTS_DIR = Path("results")

# Frozen filter
MIN_ELO              = 2600
MIN_PLIES            = 30
ALLOWED_RESULTS      = {"1-0", "0-1"}
# Classical-by-exclusion: Event/Section header substrings (case-insensitive)
EXCLUDED_EVENT_LITERALS = ("blitz", "rapid", "bullet", "armageddon")

# Frozen evaluation
STOCKFISH_DEPTH       = 22
STOCKFISH_DEPTH_SMOKE = 12             # NOT valid for preregistered claim
STOCKFISH_THREADS     = 1
STOCKFISH_HASH_MB     = 256
MATE_SCORE_BASE       = 20000          # mate_in_N → sign · (20000 − 100·N)

# Frozen TP / FO definitions
TP_THRESHOLD_CP    = 150
MAX_TP_SEARCH_PLY  = 80
FO_PROMINENCE      = 0.8
FO_MIN_DISTANCE    = 2

# Frozen statistics
WILCOXON_ALPHA      = 0.01
MIN_MEDIAN_LAG_PLY  = 1.0
N_PERMUTATIONS      = 1000
PERMUTATION_SEED    = 42                # baseline only; not for primary inference

# Frozen sample sizes
N_GAMES_FULL  = 50
N_GAMES_SMOKE = 5


# =====================================================================
# Stage 1: Download TWIC issues + concatenate
# =====================================================================

def ensure_pgn() -> Path:
    """Download TWIC issues #1500–#1524, extract and concatenate into one PGN.

    Frozen: ascending issue order, first PGN file inside each ZIP.
    Cached on disk; re-runs skip download.
    """
    DATA_DIR.mkdir(exist_ok=True)
    combined_path = DATA_DIR / f"twic_{TWIC_ISSUES[0]}_{TWIC_ISSUES[-1]}_combined.pgn"

    if combined_path.exists():
        print(f"Using cached combined archive: {combined_path}")
        print(f"  ({combined_path.stat().st_size / 1e6:.1f} MB)")
        return combined_path

    # Download missing ZIPs
    for issue in TWIC_ISSUES:
        zip_path = DATA_DIR / f"twic{issue}g.zip"
        if zip_path.exists():
            continue
        url = TWIC_BASE_URL.format(n=issue)
        print(f"Downloading TWIC #{issue}: {url}")
        try:
            urlretrieve(url, zip_path)
            print(f"  → {zip_path.stat().st_size / 1e3:.0f} KB")
        except Exception as e:
            raise RuntimeError(
                f"Failed to download TWIC #{issue} from {url}: {e}"
            ) from e

    # Extract and concatenate in ASCENDING ISSUE ORDER
    print(f"\nConcatenating {len(TWIC_ISSUES)} TWIC issues...")
    n_chars = 0
    with open(combined_path, "w", encoding="utf-8") as out:
        for issue in TWIC_ISSUES:
            zip_path = DATA_DIR / f"twic{issue}g.zip"
            with zipfile.ZipFile(zip_path) as zf:
                pgn_files = sorted(
                    n for n in zf.namelist() if n.lower().endswith(".pgn")
                )
                if not pgn_files:
                    raise RuntimeError(f"No PGN in TWIC #{issue} archive")
                # First PGN file by name (TWIC convention: main games file)
                main_pgn = pgn_files[0]
                with zf.open(main_pgn) as src:
                    raw = src.read()
                    # TWIC files are typically latin-1; try utf-8 then fallback
                    try:
                        text = raw.decode("utf-8")
                    except UnicodeDecodeError:
                        text = raw.decode("iso-8859-1")
                    out.write(text)
                    if not text.endswith("\n\n"):
                        out.write("\n\n")
                    n_chars += len(text)

    print(f"Combined → {combined_path} ({n_chars / 1e6:.1f} MB)")

    # Record SHA-256 of combined archive for replicability audit
    h = hashlib.sha256()
    with open(combined_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    print(f"Archive SHA-256: {h.hexdigest()}")
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "archive_sha256.txt").write_text(
        f"{h.hexdigest()}  {combined_path.name}\n"
        f"Source: TWIC #{TWIC_ISSUES[0]}-#{TWIC_ISSUES[-1]}\n"
    )
    return combined_path


# =====================================================================
# Stage 2: Filter & Select
# =====================================================================

def passes_filter(game: chess.pgn.Game, ply_count: int) -> bool:
    """Frozen filter for PREREGISTRATION-v1.2 §4. Returns True iff all criteria pass."""
    h = game.headers

    if h.get("Result") not in ALLOWED_RESULTS:
        return False

    try:
        if int(h.get("WhiteElo", 0)) < MIN_ELO or int(h.get("BlackElo", 0)) < MIN_ELO:
            return False
    except ValueError:
        return False

    # Classical-by-exclusion (PREREGISTRATION-v1.2 §3.6):
    # Reject if Event or Section header contains any non-classical literal.
    event   = h.get("Event",   "").lower()
    section = h.get("Section", "").lower()
    for lit in EXCLUDED_EVENT_LITERALS:
        if lit in event or lit in section:
            return False

    if ply_count < MIN_PLIES:
        return False

    if "FEN" in h:                       # standard starting position only
        return False

    # Bot exclusion (defense-in-depth; TWIC OTB games should never contain bots).
    # Kept from ADDENDUM-001 fix as tripwire.
    if h.get("WhiteTitle", "").upper() == "BOT":
        return False
    if h.get("BlackTitle", "").upper() == "BOT":
        return False

    return True


def select_games(pgn_path: Path, n: int) -> List[chess.pgn.Game]:
    """Stream concatenated TWIC PGN, filter, take FIRST n matching games in file order.

    Archive order = ascending TWIC issue x within-issue PGN order. Deterministic.
    """
    print(f"\nSelecting first {n} games matching frozen filter")
    selected: List[chess.pgn.Game] = []
    file_idx = 0

    with open(pgn_path, encoding="utf-8") as f:
        while len(selected) < n:
            game = chess.pgn.read_game(f)
            if game is None:
                break
            file_idx += 1
            n_plies = sum(1 for _ in game.mainline_moves())
            if passes_filter(game, n_plies):
                game._file_idx = file_idx  # attach for traceability
                selected.append(game)
                wt    = game.headers.get("WhiteTitle", "-")
                bt    = game.headers.get("BlackTitle", "-")
                event = game.headers.get("Event", "?")[:32]
                print(f"  [{len(selected):>2}/{n}]  idx={file_idx:>6d}  "
                      f"{h_short(game,'White'):<18}[{wt:<3}] vs "
                      f"{h_short(game,'Black'):<18}[{bt:<3}]  "
                      f"Elo {game.headers.get('WhiteElo','?')}/{game.headers.get('BlackElo','?')}  "
                      f"plies={n_plies}  <{event}>")

    if len(selected) < n:
        raise RuntimeError(
            f"Found only {len(selected)} matching games in archive. "
            f"Need {n}. Archive may be incomplete."
        )

    # Sanity-check tripwire (per ADDENDUM-001): no bots should pass the filter.
    bots_found = [g for g in selected
                  if g.headers.get("WhiteTitle","").upper() == "BOT"
                  or g.headers.get("BlackTitle","").upper() == "BOT"]
    if bots_found:
        raise RuntimeError(
            f"SANITY CHECK FAILED: {len(bots_found)} bot-titled games passed the filter. "
            f"This is a regression of the ADDENDUM-001 fix. Aborting."
        )

    return selected


def h_short(game: chess.pgn.Game, key: str) -> str:
    s = game.headers.get(key, "?")
    return s[:18]


# =====================================================================
# Stage 3: Stockfish evaluation
# =====================================================================

def make_engine(stockfish_path: str) -> chess.engine.SimpleEngine:
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    engine.configure({
        "Threads":  STOCKFISH_THREADS,
        "Hash":     STOCKFISH_HASH_MB,
        # MultiPV is automatically managed by python-chess; engine.analyse()
        # without `multipv` arg requests MultiPV=1 — semantically identical
        # to our frozen requirement (PREREGISTRATION-v1.2 §3.2).
    })
    return engine


def stockfish_version(engine: chess.engine.SimpleEngine) -> str:
    return engine.id.get("name", "unknown")


def score_to_cp_white(score: chess.engine.PovScore) -> int:
    """White-perspective centipawns per preregistration mate-conversion."""
    w = score.white()
    if w.is_mate():
        m = w.mate()
        if m == 0:
            return 0
        return (1 if m > 0 else -1) * (MATE_SCORE_BASE - 100 * abs(m))
    return w.score()


def game_id(game: chess.pgn.Game) -> str:
    return hashlib.sha1(str(game).encode()).hexdigest()[:12]


def evaluate_game(game: chess.pgn.Game, engine: chess.engine.SimpleEngine,
                  depth: int) -> List[int]:
    """Stockfish evals at every position. evals[t] = eval after t plies (White-perspective cp).

    Cached to disk by (game_id, depth, engine_version).
    """
    gid = game_id(game)
    ver = stockfish_version(engine).replace(" ", "_")
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"eval_{gid}_d{depth}_{ver}.json"

    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)

    board = game.board()
    evals: List[int] = []
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    evals.append(score_to_cp_white(info["score"]))

    for mv in game.mainline_moves():
        board.push(mv)
        info = engine.analyse(board, chess.engine.Limit(depth=depth))
        evals.append(score_to_cp_white(info["score"]))

    with open(cache_path, "w") as f:
        json.dump(evals, f)
    return evals


# =====================================================================
# Stage 4: TP and FO extraction
# =====================================================================

def find_first_turning_point(game: chess.pgn.Game, evals: List[int]) -> Optional[int]:
    """Frozen definition:
        For ply t (where t-th half-move was just played by side S):
            Delta_t = (eval_after - eval_before) from S's perspective
            t is TP iff Delta_t <= -150 cp
        First TP = min{ t : TP_t = true }, restricted to t < 80.
    Returns ply index (0-based half-moves) or None.
    """
    board = game.board()
    moves = list(game.mainline_moves())
    for t, mv in enumerate(moves):
        if t >= MAX_TP_SEARCH_PLY:
            return None
        side_sign = 1 if board.turn == chess.WHITE else -1
        delta_w = evals[t + 1] - evals[t]
        delta_stm = delta_w * side_sign
        if delta_stm <= -TP_THRESHOLD_CP:
            return t
        board.push(mv)
    return None


def find_top1_flashover(game: chess.pgn.Game, sensor: ActProofSensor) -> Optional[int]:
    """Frozen definition: top-1 from composite |d/dt| z-score via find_peaks
    (prominence=0.8, distance=2). Fallback to argmax if find_peaks empty.
    """
    pgn_text = str(game)
    traj = analyze_trajectory(sensor, pgn_text)
    if not traj:
        return None
    fos = detect_flashovers(
        traj, prominence=FO_PROMINENCE, top_k=1, min_distance=FO_MIN_DISTANCE,
    )
    if not fos:
        return None
    return fos[0].ply


# =====================================================================
# Stage 5: Statistics
# =====================================================================

@dataclass
class GameResult:
    game_id: str
    file_idx: int
    white: str
    black: str
    elo_white: int
    elo_black: int
    event: str
    result: str
    n_plies: int
    tp_ply: Optional[int]
    fo_ply: Optional[int]
    lag: Optional[int]
    excluded_reason: Optional[str] = None


def permutation_baseline(game_lengths: List[int], tp_plies: List[int],
                         n_perms: int = N_PERMUTATIONS) -> np.ndarray:
    rng = np.random.default_rng(seed=PERMUTATION_SEED)
    medians = np.empty(n_perms)
    for p in range(n_perms):
        lags = []
        for game_len, tp in zip(game_lengths, tp_plies):
            pseudo_fo = int(rng.integers(0, game_len))
            lags.append(tp - pseudo_fo)
        medians[p] = float(np.median(lags))
    return medians


def run_analysis(results: List[GameResult]) -> Dict:
    valid    = [r for r in results if r.lag is not None]
    excluded = [r for r in results if r.lag is None]

    if not valid:
        return {
            "n_valid": 0,
            "n_excluded": len(excluded),
            "verdict": "INSUFFICIENT DATA - no games with both TP and FO",
        }

    lags = np.array([r.lag for r in valid])
    median_lag = float(np.median(lags))

    try:
        stat, p_value = wilcoxon(lags, alternative="greater")
        stat = float(stat); p_value = float(p_value)
    except Exception as e:
        stat, p_value = float("nan"), float("nan")
        print(f"  ! Wilcoxon failed: {e}")

    perm_medians = permutation_baseline(
        [r.n_plies for r in valid],
        [r.tp_ply  for r in valid],
    )
    perm_p95 = float(np.percentile(perm_medians, 95))

    primary_pass  = (not np.isnan(p_value)) and (p_value < WILCOXON_ALPHA) and (median_lag >= MIN_MEDIAN_LAG_PLY)
    baseline_pass = median_lag > perm_p95

    if primary_pass and baseline_pass:
        verdict = "HYPOTHESIS SUPPORTED - proceed to Go replication with KataGo"
    elif primary_pass and not baseline_pass:
        verdict = "INCONCLUSIVE - signal exists but not distinguishable from chance ply distribution; reformulation REQUIRED"
    else:
        verdict = "HYPOTHESIS FALSIFIED - temporal pre-flashover structure not present at preregistered effect size"

    return {
        "n_valid":                  len(valid),
        "n_excluded":               len(excluded),
        "median_lag_ply":           median_lag,
        "mean_lag_ply":             float(np.mean(lags)),
        "wilcoxon_W":               stat,
        "wilcoxon_p_value":         p_value,
        "permutation_baseline_p95": perm_p95,
        "primary_pass":             bool(primary_pass),
        "baseline_pass":            bool(baseline_pass),
        "verdict":                  verdict,
        "lags":                     lags.tolist(),
        "alpha":                    WILCOXON_ALPHA,
        "min_effect_ply":           MIN_MEDIAN_LAG_PLY,
    }


# =====================================================================
# Orchestration
# =====================================================================

def run_pipeline(stockfish_path: str, n_games: int, depth: int, mode: str) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    print("=" * 70)
    print(f"ActProof Pre-Flashover Detection - {mode.upper()}")
    print(f"  PREREGISTRATION-v1.2 - TWIC #{TWIC_ISSUES[0]}-#{TWIC_ISSUES[-1]}")
    print(f"  n_games = {n_games}, depth = {depth}")
    print(f"  stockfish = {stockfish_path}")
    print("=" * 70)

    pgn_path = ensure_pgn()
    games    = select_games(pgn_path, n_games)

    engine = make_engine(stockfish_path)
    print(f"\nEngine: {stockfish_version(engine)}")
    sensor = ActProofSensor(beta=0.01)

    results: List[GameResult] = []
    try:
        for i, game in enumerate(games, 1):
            gid     = game_id(game)
            n_plies = sum(1 for _ in game.mainline_moves())
            print(f"\n[{i}/{len(games)}] {gid}  "
                  f"{h_short(game,'White')} vs {h_short(game,'Black')}  ply={n_plies}")

            evals = evaluate_game(game, engine, depth=depth)
            tp    = find_first_turning_point(game, evals)
            fo    = find_top1_flashover(game, sensor)

            reason = None
            lag    = None
            if tp is None:
                reason = "no_tp_in_first_80_plies"
            elif fo is None:
                reason = "no_flashover_detected"
            else:
                lag = tp - fo

            results.append(GameResult(
                game_id=gid, file_idx=getattr(game, "_file_idx", -1),
                white=game.headers.get("White","?"), black=game.headers.get("Black","?"),
                elo_white=int(game.headers.get("WhiteElo",0)),
                elo_black=int(game.headers.get("BlackElo",0)),
                event=game.headers.get("Event","?"),
                result=game.headers.get("Result","?"),
                n_plies=n_plies, tp_ply=tp, fo_ply=fo, lag=lag, excluded_reason=reason,
            ))

            if lag is not None:
                print(f"    TP={tp:>3d}  FO={fo:>3d}  lag={lag:+d}")
            else:
                print(f"    EXCLUDED - {reason}")
    finally:
        engine.quit()

    raw_path = RESULTS_DIR / f"raw_results_{mode}.json"
    with open(raw_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    print("\n" + "=" * 70)
    print("Statistical analysis (frozen procedure)")
    print("=" * 70)
    analysis = run_analysis(results)
    ana_path = RESULTS_DIR / f"analysis_{mode}.json"
    with open(ana_path, "w") as f:
        json.dump(analysis, f, indent=2)

    print(f"  Valid games            : {analysis['n_valid']} / {len(results)}")
    print(f"  Excluded               : {analysis['n_excluded']}")
    if analysis.get("median_lag_ply") is not None:
        print(f"  Median lag (ply)       : {analysis['median_lag_ply']:+.2f}")
        print(f"  Mean lag (ply)         : {analysis['mean_lag_ply']:+.2f}")
        print(f"  Wilcoxon W             : {analysis['wilcoxon_W']}")
        print(f"  Wilcoxon p (one-sided) : {analysis['wilcoxon_p_value']}")
        print(f"  Permutation P95        : {analysis['permutation_baseline_p95']:+.2f}")
        print(f"  Primary test           : {'PASS' if analysis['primary_pass']  else 'FAIL'}"
              f"  (p<{WILCOXON_ALPHA} AND median>={MIN_MEDIAN_LAG_PLY})")
        print(f"  Baseline test          : {'PASS' if analysis['baseline_pass'] else 'FAIL'}"
              f"  (median > permutation P95)")
    print(f"\n  VERDICT: {analysis['verdict']}")
    print(f"\nRaw results -> {raw_path}")
    print(f"Analysis    -> {ana_path}")

    if mode == "smoke":
        print("\n! This was a SMOKE TEST.")
        print(f"  depth={depth} and n={n_games} are below frozen parameters.")
        print("  Result is NOT a valid claim. Verifies pipeline only.")


def main() -> int:
    p = argparse.ArgumentParser(description="ActProof Pre-Flashover Detection - data pipeline")
    grp = p.add_mutually_exclusive_group(required=True)
    grp.add_argument("--smoke-test", action="store_true", help=f"n={N_GAMES_SMOKE}, depth={STOCKFISH_DEPTH_SMOKE}  (sanity check)")
    grp.add_argument("--full",       action="store_true", help=f"n={N_GAMES_FULL}, depth={STOCKFISH_DEPTH}  (preregistered)")
    p.add_argument("--stockfish", required=True, help="Path to Stockfish binary (e.g. /usr/local/bin/stockfish)")
    args = p.parse_args()

    if not Path(args.stockfish).exists():
        print(f"ERROR: stockfish binary not found: {args.stockfish}", file=sys.stderr)
        return 2

    if args.smoke_test:
        run_pipeline(args.stockfish, N_GAMES_SMOKE, STOCKFISH_DEPTH_SMOKE, "smoke")
    else:
        run_pipeline(args.stockfish, N_GAMES_FULL,  STOCKFISH_DEPTH,       "full")
    return 0


if __name__ == "__main__":
    sys.exit(main())
