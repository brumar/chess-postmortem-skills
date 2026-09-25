#!/usr/bin/env python
"""Propose the ONE position in a game that deserves a strategic "plan pause".

usage: pick_pause.py <sweep.json> [--side white|black|both] [--window 8]
                     [--top 5] [--blunder 200] [--min-drift 60] [--from-ply 12]
                     [--w-phase 1] [--w-settled 1] [--w-drift 1] [--w-strays 1]
                     [--w-crash .4] [--drift-full 150] [--stable 6] [--stray 10]

A plan pause is a QUIET position (no check, no capture wanted by the engine,
the eval already settled) where the question the game asks is *what is the
plan?* and a move-by-move mistake review has nothing to say, because no single
move there is bad enough to flag.

Two families of criteria decide it, and neither is sufficient alone.

POSITIONAL, what kind of position this is. A plan is the question a position
asks once the terrain is fixed and the pieces are out:
  phase    middlegame: kings committed (castled or the right gone), minors off
           their home squares, material still substantial. An endgame tapers
           this to zero, since plans there are a different subject.
  settled  the pawn skeleton has stopped churning: no pawn capture pending,
           some pawns fixed head to head, and the skeleton this position sits
           in holds for `--stable` plies (counted both ways, so the FIRST
           position of a long stable stretch scores as well as the middle).

OUTCOME, what the player then did with it:
  drift    centipawns bled from here forward, stopping at the first loss
           >= `--blunder` (that one is the crash, not drift)
  strays   how CONSISTENTLY the player left the engine's line during that run:
           moves that both differ from the engine's choice and cost at least
           `--stray` cp, over the moves in the run (min 3, so a one-move run
           cannot score full marks). One bad move among four fine ones is a
           tactical oversight, not a missing plan, and gets ranked as such.
  crash    the first big loss, if it lands inside the window. Small weight: it
           is the bill, not the reason.

score = weighted mean of the five, each normalised to 0..1. Every weight is a
flag and the breakdown prints for every candidate, so a ranking you disagree
with tells you which knob to turn: --w-settled 2 to insist on a fixed
structure, --w-drift 2 to go back to punishing the bleed above all.

Because drift accumulates forward to the crash and the strays fraction covers
the whole run, the EARLIEST quiet position of a drift run scores highest on the
outcome side: the moment the player still had every option and no plan, not
the last one before the bill arrived. The positional side then decides between
the positions inside that run.

If nothing clears --min-drift the game was played cleanly; the script falls
back to ranking on the positional criteria alone and says so, so there is
always a candidate to look at.

Prints candidates best-first with the FEN to analyse and the `"ply"` value to
put in a video storyboard (= the ply BEFORE the move under consideration).
The script ranks; you decide, with your eyes on the position.
"""
import argparse, json
import chess

CRASH_CAP = 800          # cp: a mate score must not swamp the ranking
MIN_RUN = 3              # moves the strays fraction is divided by, at least
MAT_FULL, MAT_BARE = 30, 10   # non-pawn material: middlegame / bare endgame
MINOR_HOME = {
    (chess.WHITE, chess.KNIGHT): {chess.B1, chess.G1},
    (chess.WHITE, chess.BISHOP): {chess.C1, chess.F1},
    (chess.BLACK, chess.KNIGHT): {chess.B8, chess.G8},
    (chess.BLACK, chess.BISHOP): {chess.C8, chess.F8},
}
VALUE = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

p = argparse.ArgumentParser()
p.add_argument("sweep")
p.add_argument("--side", default="both", choices=["white", "black", "both"],
               help="for a self-review, pass the player's side")
p.add_argument("--window", type=int, default=8, help="plies to look ahead")
p.add_argument("--top", type=int, default=5)
p.add_argument("--blunder", type=int, default=200, help="cp loss that is a crash, not drift")
p.add_argument("--min-drift", type=int, default=60, help="cp of drift a candidate must show")
p.add_argument("--from-ply", type=int, default=12, help="skip the opening")
p.add_argument("--stable", type=int, default=6, help="plies of unchanged pawn skeleton = fully settled")
p.add_argument("--stray", type=int, default=10, help="cp a non-engine move must cost to count as a stray")
p.add_argument("--drift-full", type=int, default=150, help="cp of drift that scores full marks")
p.add_argument("--w-phase", type=float, default=1.0)
p.add_argument("--w-settled", type=float, default=1.0)
p.add_argument("--w-drift", type=float, default=1.0)
p.add_argument("--w-strays", type=float, default=1.0)
p.add_argument("--w-crash", type=float, default=0.4)
a = p.parse_args()

rows = json.load(open(a.sweep))
by_ply = {r["ply"]: r for r in rows}
sides = ["White", "Black"] if a.side == "both" else [a.side.capitalize()]
boards = {r["ply"]: chess.Board(r["fen_before"]) for r in rows}


def clamp(x):
    return max(0.0, min(1.0, x))


def quiet(row):
    """No check anywhere, and neither the engine nor the player wants a capture."""
    b = boards[row["ply"]]
    if b.is_check():
        return False
    for san in (row["best_san"], row["san"]):
        try:
            mv = b.parse_san(san)
        except ValueError:
            return False
        if b.is_capture(mv) or b.gives_check(mv):
            return False
    return True


def phase(b):
    """Middlegame-ness in 0..1: developed and committed, but not yet an endgame."""
    material = sum(VALUE[pt] * len(b.pieces(pt, c))
                   for pt in VALUE for c in (chess.WHITE, chess.BLACK))
    minors = [(pt, c, sq) for pt in (chess.KNIGHT, chess.BISHOP)
              for c in (chess.WHITE, chess.BLACK) for sq in b.pieces(pt, c)]
    home = sum(1 for pt, c, sq in minors if sq in MINOR_HOME[(c, pt)])
    dev = 1.0 if not minors else 1 - home / len(minors)
    kings = sum(0.5 for c in (chess.WHITE, chess.BLACK) if not b.has_castling_rights(c))
    taper = clamp((material - MAT_BARE) / (MAT_FULL - MAT_BARE))
    return (0.6 * kings + 0.4 * dev) * taper, len(minors) - home, len(minors), material, kings


def skeleton(b):
    return b.pawns & b.occupied_co[chess.WHITE], b.pawns & b.occupied_co[chess.BLACK]


def pawn_pairs(b):
    """(tension, fixed): pawn captures pending, and pawns blocked head to head."""
    tension = fixed = 0
    for sq in b.pieces(chess.PAWN, chess.WHITE):
        f, r = chess.square_file(sq), chess.square_rank(sq)
        if r + 1 > 7:
            continue
        for df, kind in ((-1, "t"), (1, "t"), (0, "f")):
            if not 0 <= f + df <= 7:
                continue
            pc = b.piece_at(chess.square(f + df, r + 1))
            if pc and pc.piece_type == chess.PAWN and pc.color == chess.BLACK:
                if kind == "t":
                    tension += 1
                else:
                    fixed += 1
    return tension, fixed


def settled(ply):
    """The pawn skeleton is fixed here: nothing pending, something locked, and
    the skeleton this position sits in lasts (counting both directions)."""
    b = boards[ply]
    key = skeleton(b)
    back = fwd = 0
    while (p2 := ply - 1 - back) in boards and skeleton(boards[p2]) == key:
        back += 1
    while (p2 := ply + 1 + fwd) in boards and skeleton(boards[p2]) == key:
        fwd += 1
    tension, fixed = pawn_pairs(b)
    span = back + fwd
    score = (0.40 * clamp(1 - tension / 3)
             + 0.20 * clamp(fixed / 2)
             + 0.40 * clamp(span / a.stable))
    return score, tension, fixed, span, back


def loss_text(cp):
    return "loses the game" if cp >= 1000 else f"-{cp / 100:.1f}"


cands = []
for r in rows:
    if r["mover"] not in sides or r["ply"] < a.from_ply or not quiet(r):
        continue
    prev = by_ply.get(r["ply"] - 1)
    if prev and abs(r["eval_best"] - prev["eval_after_played"]) > 60:
        continue                      # the evaluation has not settled yet
    drift, crash, crash_ply, moves, strays, detail = 0, 0, None, 0, 0, []
    for p2 in range(r["ply"], r["ply"] + a.window):
        r2 = by_ply.get(p2)
        if not r2 or r2["mover"] != r["mover"]:
            continue
        loss = max(0, r2["loss_for_mover"])
        if loss >= a.blunder:
            crash, crash_ply = loss, p2       # the run ends here: this is the bill
            break
        drift += loss
        moves += 1
        if r2["san"] != r2["best_san"] and loss >= a.stray:
            strays += 1
        if loss >= 20:
            detail.append(f"{r2['label']}{r2['san']} {loss_text(loss)}")
    ph, out, tot, material, kings = phase(boards[r["ply"]])
    st, tension, fixed, span, back = settled(r["ply"])
    parts = {
        "phase": (a.w_phase, ph),
        "settled": (a.w_settled, st),
        "drift": (a.w_drift, clamp(drift / a.drift_full)),
        "strays": (a.w_strays, strays / max(moves, MIN_RUN)),
        "crash": (a.w_crash, min(crash, CRASH_CAP) / CRASH_CAP),
    }
    weight = sum(w for w, _ in parts.values()) or 1
    score = sum(w * v for w, v in parts.values()) / weight
    cands.append(dict(score=score, parts=parts, row=r, drift=drift, crash=crash,
                      crash_ply=crash_ply, detail=detail, moves=moves, strays=strays,
                      out=out, tot=tot, material=material, kings=kings,
                      tension=tension, fixed=fixed, span=span, back=back))

drifters = [c for c in cands if c["drift"] >= a.min_drift]
if drifters:
    cands = drifters
elif cands:
    print(f"no drift run reaches {a.min_drift}cp. The game was played cleanly, or its\n"
          f"losses are all tactical. Ranking every quiet position instead, which leaves\n"
          f"the positional criteria to decide:\n")
else:
    print("no quiet candidate at all. Try --from-ply lower / --window larger")

cands.sort(key=lambda c: -c["score"])

for i, c in enumerate(cands[:a.top], 1):
    r = c["row"]
    prev = by_ply.get(r["ply"] - 1)
    pv = {k: v for k, (_, v) in c["parts"].items()}
    print(f"#{i}  {r['mover']} to move, pause before {r['label']}{r['san']}   score {c['score']:.2f}")
    print(f"    position   after ply {r['ply']-1}"
          f" ({prev['label'] + prev['san'] if prev else 'start'})"
          f"   -> storyboard \"ply\": {r['ply']-1}")
    print(f"    fen        {r['fen_before']}")
    print(f"    eval       {r['eval_best']/100:+.2f}   engine wants {r['best_san']},"
          f" {r['mover']} played {r['san']}")
    print(f"    phase      {pv['phase']:.2f}   kings committed {c['kings']*2:.0f}/2,"
          f" minors out {c['out']}/{c['tot']}, material {c['material']}")
    print(f"    settled    {pv['settled']:.2f}   pawn tension {c['tension']},"
          f" pawns fixed {c['fixed']}, skeleton holds {c['span']} plies"
          f" ({c['back']} behind)")
    print(f"    drift      {pv['drift']:.2f}   {c['drift']/100:.2f} over {c['moves']}"
          f" moves: {', '.join(c['detail']) or 'no single move loses 20cp'}")
    print(f"    strays     {pv['strays']:.2f}   {c['strays']}/{c['moves']} moves left"
          f" the engine's line and cost something")
    if c["crash"]:
        cr = by_ply[c["crash_ply"]]
        print(f"    crash      {pv['crash']:.2f}   {cr['label']}{cr['san']}"
              f" {loss_text(c['crash'])} at ply {c['crash_ply']}")
    print()
