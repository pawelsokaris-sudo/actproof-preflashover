"""
ActProof Chess — dynamics, flashover detection, symmetric β scan, plotting.

Builds on actproof_chess.ActProofSensor. We do NOT predict moves; we measure
the temporal dynamics of the field metrics along the game trajectory and look
for `flashovers` — sharp transitions in T, S, or E that should mark
informationally critical moments (sacrifices, decisive errors, key prophylaxis).

Outputs:
  - Trajectory dict with first derivatives of E, T_max, S
  - Composite flashover signal (max over z-scored |d/dt| channels)
  - Peak detection via scipy.signal.find_peaks
  - Symmetric β fit over [-10, +10] to test the max-tension hypothesis
  - Multi-panel PNG with peaks annotated by SAN move
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import chess
import chess.pgn
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

from actproof_chess import ActProofSensor, FieldConfig, KASPAROV_TOPALOV_1999


# ---------- Data records ----------

@dataclass
class Flashover:
    ply: int
    san: str          # e.g. "24. Rxd4"
    dominant_channel: str  # "E" | "T_max" | "S"
    magnitude_z: float
    rank: int


# ---------- Trajectory analysis ----------

def _ply_to_san_list(pgn_text: str) -> List[str]:
    """Rebuild SAN labels '24. Rxd4' / '24... cxd4' for each ply."""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return []
    board = game.board()
    labels: List[str] = []
    for i, mv in enumerate(game.mainline_moves()):
        san = board.san(mv)
        move_no = (i // 2) + 1
        prefix = f"{move_no}." if i % 2 == 0 else f"{move_no}..."
        labels.append(f"{prefix} {san}")
        board.push(mv)
    return labels


def _zscore(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - x.mean()) / (sd + 1e-9)


def analyze_trajectory(sensor: ActProofSensor, pgn_text: str) -> Dict:
    """Full per-ply trajectory + first derivatives + composite flashover signal."""
    rows = sensor.analyze_game(pgn_text)
    if not rows:
        return {}

    sans = _ply_to_san_list(pgn_text)
    plies = np.arange(len(rows))

    E     = np.array([r["field_energy"]     for r in rows])
    T_max = np.array([r["max_tension"]      for r in rows])
    T_L1  = np.array([r["total_tension_L1"] for r in rows])
    S     = np.array([r["causal_entropy"]   for r in rows])
    pmax  = np.array([r["policy_max_prob"]  for r in rows])

    dE = np.gradient(E)
    dT = np.gradient(T_max)
    dS = np.gradient(S)

    dE_z = _zscore(np.abs(dE))
    dT_z = _zscore(np.abs(dT))
    dS_z = _zscore(np.abs(dS))

    composite = np.maximum.reduce([dE_z, dT_z, dS_z])

    return {
        "plies": plies, "sans": sans,
        "E": E, "T_max": T_max, "T_L1": T_L1, "S": S, "pmax": pmax,
        "dE": dE, "dT": dT, "dS": dS,
        "dE_z": dE_z, "dT_z": dT_z, "dS_z": dS_z,
        "composite": composite,
        "rows": rows,
    }


def detect_flashovers(traj: Dict, prominence: float = 0.8, top_k: int = 10,
                      min_distance: int = 2) -> List[Flashover]:
    sig = traj["composite"]
    peaks, _ = find_peaks(sig, prominence=prominence, distance=min_distance)
    if len(peaks) == 0:
        peaks = np.argsort(-sig)[:top_k]

    peaks = sorted(peaks, key=lambda p: -sig[p])[:top_k]

    out: List[Flashover] = []
    for rank, p in enumerate(peaks, start=1):
        # Dominant channel at this peak
        channels = {"E": traj["dE_z"][p], "T_max": traj["dT_z"][p], "S": traj["dS_z"][p]}
        dom = max(channels, key=channels.get)
        san = traj["sans"][p] if p < len(traj["sans"]) else "?"
        out.append(Flashover(
            ply=int(traj["plies"][p]),
            san=san,
            dominant_channel=dom,
            magnitude_z=float(sig[p]),
            rank=rank,
        ))
    return out


# ---------- Symmetric β scan ----------

def _boltzmann_stable(energies: np.ndarray, beta: float) -> np.ndarray:
    logits = -beta * energies
    logits -= logits.max()
    w = np.exp(logits)
    return w / w.sum()


def fit_beta_symmetric(sensor: ActProofSensor, pgn_text: str,
                       n_per_side: int = 25) -> Tuple[float, np.ndarray, np.ndarray]:
    """Scan β over signed log-grid [-10, +10] to test:
       - β > 0 → 'GM minimises field energy'
       - β < 0 → 'GM maximises field energy'
       - β ≈ 0 → 'energy is orthogonal to GM choice'.
    Returns (β*, β_grid, log-likelihood-curve).
    """
    pos_side = np.logspace(-4, 1, n_per_side)
    beta_grid = np.concatenate([-pos_side[::-1], [0.0], pos_side])

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        return 0.0, beta_grid, np.zeros_like(beta_grid)
    board = game.board()

    per_pos: List[Tuple[np.ndarray, int]] = []
    for played in game.mainline_moves():
        moves = list(board.legal_moves)
        if not moves:
            board.push(played)
            continue
        energies = np.empty(len(moves))
        for i, mv in enumerate(moves):
            board.push(mv)
            energies[i] = sensor.field.dirichlet_energy(sensor.field.potential(board))
            board.pop()
        try:
            idx = moves.index(played)
            per_pos.append((energies, idx))
        except ValueError:
            pass
        board.push(played)

    ll = np.empty_like(beta_grid)
    for k, b in enumerate(beta_grid):
        lls = []
        for energies, idx in per_pos:
            p = _boltzmann_stable(energies, b)
            lls.append(np.log(p[idx] + 1e-12))
        ll[k] = float(np.mean(lls))
    best = int(np.argmax(ll))
    return float(beta_grid[best]), beta_grid, ll


# ---------- Plotting ----------

def plot_trajectory(traj: Dict, flashovers: List[Flashover],
                    beta_grid: np.ndarray, ll_curve: np.ndarray,
                    title: str, output_path: str) -> None:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig = plt.figure(figsize=(15, 11), constrained_layout=True)
    gs = fig.add_gridspec(5, 4)

    ax_E   = fig.add_subplot(gs[0, :3])
    ax_T   = fig.add_subplot(gs[1, :3], sharex=ax_E)
    ax_S   = fig.add_subplot(gs[2, :3], sharex=ax_E)
    ax_C   = fig.add_subplot(gs[3, :3], sharex=ax_E)
    ax_B   = fig.add_subplot(gs[0:2, 3])
    ax_tbl = fig.add_subplot(gs[2:5, 3])
    ax_tbl.axis("off")
    ax_zoom = fig.add_subplot(gs[4, :3])

    p = traj["plies"]

    # Panel 1: Field energy (Dirichlet)
    ax_E.plot(p, traj["E"], color="#1f77b4", lw=1.4, label="E (Dirichlet energy)")
    ax_E.set_ylabel("E")
    ax_E.legend(loc="upper right", frameon=False)
    ax_E.set_title(title, loc="left", fontweight="bold", fontsize=11)

    # Panel 2: Tension (max + L1)
    ax_T.plot(p, traj["T_max"], color="#d62728", lw=1.4, label="T_max")
    ax_T2 = ax_T.twinx()
    ax_T2.plot(p, traj["T_L1"], color="#ff7f0e", lw=1.0, alpha=0.65,
               label="∫T dA (L¹)")
    ax_T.set_ylabel("T_max", color="#d62728")
    ax_T2.set_ylabel("∫T dA", color="#ff7f0e")
    ax_T.tick_params(axis="y", colors="#d62728")
    ax_T2.tick_params(axis="y", colors="#ff7f0e")
    ax_T2.grid(False)

    # Panel 3: Causal entropy
    ax_S.plot(p, traj["S"], color="#2ca02c", lw=1.4, label="S (causal entropy, bits)")
    ax_S.set_ylabel("S [bits]")
    ax_S.legend(loc="upper right", frameon=False)

    # Panel 4: Composite flashover signal with peaks
    ax_C.plot(p, traj["composite"], color="#7b3294", lw=1.4,
              label="composite |d/dt| z-score")
    ax_C.axhline(0.0, color="grey", lw=0.5)
    for f in flashovers:
        ax_C.axvline(f.ply, color="#7b3294", lw=0.6, alpha=0.35, ls="--")
        ax_C.text(f.ply, traj["composite"][f.ply] + 0.15, f"#{f.rank}",
                  ha="center", va="bottom", fontsize=8, color="#7b3294")
    ax_C.set_ylabel("z-score")
    ax_C.legend(loc="upper right", frameon=False)
    ax_C.set_xlabel("ply")

    # Mark flashovers on all upper panels
    for ax in (ax_E, ax_T, ax_S):
        for f in flashovers[:5]:
            ax.axvline(f.ply, color="#7b3294", lw=0.5, alpha=0.25, ls="--")

    # Panel β-curve
    ax_B.plot(beta_grid, ll_curve, color="#222222", lw=1.4)
    ax_B.axvline(0.0, color="grey", lw=0.7, ls=":")
    star = int(np.argmax(ll_curve))
    ax_B.scatter([beta_grid[star]], [ll_curve[star]],
                 color="#d62728", s=40, zorder=5,
                 label=f"β* = {beta_grid[star]:.4f}")
    ax_B.set_xscale("symlog", linthresh=1e-4)
    ax_B.set_xlabel("β  (symlog;  <0 = prefers max-energy)")
    ax_B.set_ylabel("mean log p(GM-move)")
    ax_B.set_title("β-scan", fontsize=10, fontweight="bold", loc="left")
    ax_B.legend(loc="lower center", frameon=False, fontsize=8)

    # Panel: zoom on critical phase (last third of game)
    n = len(p)
    zoom_start = max(0, int(n * 0.55))
    ax_zoom.plot(p[zoom_start:], traj["T_max"][zoom_start:],
                 color="#d62728", lw=1.4, label="T_max")
    ax_zoom_b = ax_zoom.twinx()
    ax_zoom_b.plot(p[zoom_start:], traj["S"][zoom_start:],
                   color="#2ca02c", lw=1.4, label="S")
    ax_zoom.set_xlabel("ply (critical phase zoom)")
    ax_zoom.set_ylabel("T_max", color="#d62728")
    ax_zoom_b.set_ylabel("S", color="#2ca02c")
    ax_zoom.tick_params(axis="y", colors="#d62728")
    ax_zoom_b.tick_params(axis="y", colors="#2ca02c")
    ax_zoom_b.grid(False)
    for f in flashovers:
        if f.ply >= zoom_start:
            ax_zoom.axvline(f.ply, color="#7b3294", lw=0.6, alpha=0.45, ls="--")
            ax_zoom.text(f.ply, ax_zoom.get_ylim()[1] * 0.97, f.san,
                         rotation=90, va="top", ha="right",
                         fontsize=7, color="#222222")

    # Side panel: flashover table
    tbl_lines = ["TOP FLASHOVERS  (rank | ply | SAN | channel | z)"]
    tbl_lines.append("─" * 46)
    for f in flashovers:
        tbl_lines.append(
            f"#{f.rank:<2d}  p={f.ply:>3d}  {f.san:<14s}  {f.dominant_channel:<5s}  z={f.magnitude_z:5.2f}"
        )
    ax_tbl.text(0.0, 1.0, "\n".join(tbl_lines),
                family="monospace", fontsize=8.5, va="top", ha="left")

    fig.suptitle("ActProof Chess Sensor — trajectory dynamics & flashovers",
                 fontsize=12, fontweight="bold", y=1.01)
    fig.savefig(output_path, dpi=140, bbox_inches="tight")
    plt.close(fig)


# ---------- Main ----------

def main() -> None:
    sensor = ActProofSensor(beta=0.01)

    print("Analysing trajectory…")
    traj = analyze_trajectory(sensor, KASPAROV_TOPALOV_1999)
    print(f"  plies: {len(traj['plies'])}")

    print("Detecting flashovers…")
    flashovers = detect_flashovers(traj, prominence=0.7, top_k=10)
    for f in flashovers:
        print(f"  #{f.rank}  ply {f.ply:3d}  {f.san:<14s}  ch={f.dominant_channel:<5s}  z={f.magnitude_z:.2f}")

    print("\nSymmetric β scan…")
    beta_star, beta_grid, ll = fit_beta_symmetric(sensor, KASPAROV_TOPALOV_1999, n_per_side=20)
    print(f"  β* = {beta_star:+.5f}")
    print(f"  log-lik at β*    : {ll.max():+.3f}")
    print(f"  log-lik at β = 0 : {ll[len(ll) // 2]:+.3f}    (uniform baseline)")
    if abs(beta_star) < 1e-4:
        verdict = "β* ≈ 0 → energy orthogonal to GM choice"
    elif beta_star > 0:
        verdict = "β* > 0 → GM tends to MINIMISE field energy"
    else:
        verdict = "β* < 0 → GM tends to MAXIMISE field energy (max-tension play)"
    print(f"  verdict          : {verdict}")

    print("\nRendering plot…")
    out = "/mnt/user-data/outputs/kasparov_topalov_1999_dynamics.png"
    plot_trajectory(
        traj, flashovers, beta_grid, ll,
        title="Kasparov–Topalov, Wijk aan Zee 1999  ('Kasparov's Immortal')",
        output_path=out,
    )
    print(f"  saved → {out}")


if __name__ == "__main__":
    main()
