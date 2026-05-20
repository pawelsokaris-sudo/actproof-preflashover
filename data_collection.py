"""
data_collection.py — ActProof Pre-Flashover Detection: data acquisition and analysis pipeline.

POST-FREEZE module. This file is added AFTER the `freeze-v1.0` tag and implements
(does not redefine) the protocol fixed in PREREGISTRATION.md.

All scientific decisions live in PREREGISTRATION.md. This file is mechanical
realisation. Any divergence from the preregistration here is a bug to be fixed,
not a freedom to be exercised.

Pipeline stages:
  1. download   — Lichess Elite PGN archive (2024-06)
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
# Constants — all sourced from PREREGISTRATION.md, FROZEN.
# Do NOT change without filing a new preregistration.
# =====================================================================

LICHESS_ELITE_URL = "https://database.nikonoel.fr/lichess_elite_2024-06.zip"
DATA_DIR    = Path("data")
CACHE_DIR   = Path("cache")
RESULTS_DIR = Path("results")

# Frozen filter
MIN_ELO              = 2600
MIN_PLIES            = 30
MIN_BASE_TIME_SEC    = 1800            # 30+0 classical
ALLOWED_RESULTS      = {"1-0", "0-1"}

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
# Stage 1: Download
# =====================================================================

def ensure_pgn(url: str = LICHESS_ELITE_URL) -> Path:
    """Download + extract Lichess Elite PGN archive. Returns path to .pgn."""
    DATA_DIR.mkdir(exist_ok=True)
    zip_path = DATA_DIR / "lichess_elite_2024-06.zip"
    pgn_path = DATA_DIR / "lichess_elite_2024-06.pgn"

    if pgn_path.exists():
        return pgn_path

    if not zip_path.exists():
        print(f"Downloading {url}")
        print(f"  → {zip_path}")
        urlretrieve(url, zip_path)
        print(f"  done ({zip_path.stat().st_size / 1e6:.1f} MB)")

    print(f"Extracting {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        pgn_names = [n for n in zf.namelist() if n.endswith(".pgn")]
        if not pgn_names:
            raise RuntimeError(f"No .pgn file inside {zip_path}")
        with zf.open(pgn_names[0]) as src, open(pgn_path, "wb") as dst:
            dst.write(src.read())
    print(f"  → {pgn_path} ({pgn_path.stat().st_size / 1e6:.1f} MB)")
    return pgn_path


# =====================================================================
# Stage 2: Filter & Select
# =====================================================================

def passes_filter(game: chess.pgn.Game, ply_count: int) -> bool:
    """Check single game against every frozen criterion. Returns True iff all pass."""
    h = game.headers

    if h.get("Result") not in ALLOWED_RESULTS:
        return False

    try:
        if int(h.get("WhiteElo", 0)) < MIN_ELO or int(h.get("BlackElo", 0)) < MIN_ELO:
            return False
    except ValueError:
        return False

    tc = h.get("TimeControl", "")
    if "+" not in tc:
        return False
    try:
        base = int(tc.split("+")[0])
    except ValueError:
        return False
    if base < MIN_BASE_TIME_SEC:
        return False

    if ply_count < MIN_PLIES:
        return False

    if "FEN" in h:                       # exclude non-standard starts
        return False

    # Bot exclusion — Lichess canonical convention:
    #   [WhiteTitle "BOT"] / [BlackTitle "BOT"] is the authoritative tag set
    #   by Lichess for verified bot accounts. Our preregistration §4 specifies
    #   "no engine games" — this is the implementation of that criterion.
    #
    # Note: the Lichess Elite Database (nikonoel) is filtered by Elo only, NOT
    # by player type, so bot accounts with rating ≥2600 are present and must
    # be excluded here. See ADDENDUM-001.md for the bug history.
    if h.get("WhiteTitle", "").upper() == "BOT":
        return False
    if h.get("BlackTitle", "").upper() == "BOT":
        return False

    return True


def select_games(pgn_path: Path, n: int) -> List[chess.pgn.Game]:
    """Stream PGN, filter, take FIRST n matching games in file order.

    Deterministic by virtue of PGN file ordering — Lichess archives are
    ordered chronologically; the same archive yields the same selection.
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
                wt = game.headers.get("WhiteTitle", "—")
                bt = game.headers.get("BlackTitle", "—")
                print(f"  [{len(selected):>2}/{n}]  idx={file_idx:>6d}  "
                      f"{h_short(game,'White'):<15}[{wt:<3}] vs "
                      f"{h_short(game,'Black'):<15}[{bt:<3}]  "
                      f"Elo {game.headers.get('WhiteElo','?')}/{game.headers.get('BlackElo','?')}  "
                      f"{game.headers.get('UTCDate','?')}  plies={n_plies}")

    if len(selected) < n:
        raise RuntimeError(
            f"Found only {len(selected)} matching games in archive. "
            f"Need {n}. Archive may be incomplete."
        )

    # Sanity check — surface any bot-titled players that slipped through.
    # After the ADDENDUM-001 fix this should NEVER fire; kept as a tripwire.
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
    return s[:15]


# =====================================================================
# Stage 3: Stockfish evaluation
# =====================================================================

def make_engine(stockfish_path: str) -> chess.engine.SimpleEngine:
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    engine.configure({
        "Threads":  STOCKFISH_THREADS,
        "Hash":     STOCKFISH_HASH_MB,
        # MultiPV is automatically managed by python-chess and cannot be set
        # via configure(). The frozen requirement MultiPV=1 (PREREGISTRATION
        # §3.2) is satisfied because engine.analyse() called without an explicit
        # `multipv` kwarg internally requests MultiPV=1 from the engine and
        # returns a single info dict — semantically identical to MultiPV=1.
        # Verified in python-chess source: chess/engine.py SimpleEngine.analyse.
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
            Δ_t = (eval_after − eval_before) from S's perspective
            t is TP iff Δ_t ≤ −150 cp
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
    result: str
    n_plies: int
    tp_ply: Optional[int]
    fo_ply: Optional[int]
    lag: Optional[int]
    excluded_reason: Optional[str] = None


def permutation_baseline(game_lengths: List[int], tp_plies: List[int],
                         n_perms: int = N_PERMUTATIONS) -> np.ndarray:
    """For each game and permutation, draw random pseudo-FO uniformly from
    [0, n_plies). Compute pseudo-lag distribution; return median per permutation.
    """
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
    """Apply frozen statistical procedure to result list."""
    valid    = [r for r in results if r.lag is not None]
    excluded = [r for r in results if r.lag is None]

    if not valid:
        return {
            "n_valid": 0,
            "n_excluded": len(excluded),
            "verdict": "INSUFFICIENT DATA — no games with both TP and FO",
        }

    lags = np.array([r.lag for r in valid])
    median_lag = float(np.median(lags))

    # Wilcoxon one-sided (H1: median > 0)
    try:
        stat, p_value = wilcoxon(lags, alternative="greater")
        stat = float(stat); p_value = float(p_value)
    except Exception as e:
        stat, p_value = float("nan"), float("nan")
        print(f"  ⚠ Wilcoxon failed: {e}")

    # Permutation baseline
    perm_medians = permutation_baseline(
        [r.n_plies for r in valid],
        [r.tp_ply  for r in valid],
    )
    perm_p95 = float(np.percentile(perm_medians, 95))

    primary_pass  = (not np.isnan(p_value)) and (p_value < WILCOXON_ALPHA) and (median_lag >= MIN_MEDIAN_LAG_PLY)
    baseline_pass = median_lag > perm_p95

    if primary_pass and baseline_pass:
        verdict = "HYPOTHESIS SUPPORTED — proceed to Go replication with KataGo"
    elif primary_pass and not baseline_pass:
        verdict = "INCONCLUSIVE — signal exists but not distinguishable from chance ply distribution; reformulation REQUIRED"
    else:
        verdict = "HYPOTHESIS FALSIFIED — temporal pre-flashover structure not present at preregistered effect size"

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
    print(f"ActProof Pre-Flashover Detection — {mode.upper()}")
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
                result=game.headers.get("Result","?"),
                n_plies=n_plies, tp_ply=tp, fo_ply=fo, lag=lag, excluded_reason=reason,
            ))

            if lag is not None:
                print(f"    TP={tp:>3d}  FO={fo:>3d}  lag={lag:+d}")
            else:
                print(f"    EXCLUDED — {reason}")
    finally:
        engine.quit()

    # Persist raw + analysis
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
              f"  (p<{WILCOXON_ALPHA} AND median≥{MIN_MEDIAN_LAG_PLY})")
        print(f"  Baseline test          : {'PASS' if analysis['baseline_pass'] else 'FAIL'}"
              f"  (median > permutation P95)")
    print(f"\n  VERDICT: {analysis['verdict']}")
    print(f"\nRaw results → {raw_path}")
    print(f"Analysis    → {ana_path}")

    if mode == "smoke":
        print("\n⚠ This was a SMOKE TEST.")
        print(f"  depth={depth} and n={n_games} are below frozen parameters.")
        print("  Result is NOT a valid claim. Verifies pipeline only.")


def main() -> int:
    p = argparse.ArgumentParser(description="ActProof Pre-Flashover Detection — data pipeline")
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
