#!/usr/bin/env python
"""Build an annotated PGN from a source PGN + an annotations.json spec.

usage: build_annotated.py annotations.json

annotations.json schema:
{
  "source_pgn": "path/to/game.pgn",
  "output_pgn": "path/to/game-annotated.pgn",
  "annotator": "Claude + Stockfish 17.1 (depth 22)",
  "game_comment": "text before move 1",
  "final_comment": "text appended after the last move",
  "moves": {
    "<ply>": {                       # 1-based half-move index of the PLAYED move
      "glyph": "?!",                 # optional: ! ? !! ?? !? ?!
      "comment": "why this move is good/bad",   # optional
      "variations": [                # alternatives to THIS ply's move, from the same
                                     # position, starting with a move by the SAME side.
                                     # A refutation beginning with the opponent's better
                                     # reply belongs on the opponent's ply, not this one.
        {
          "line": [
            {"san": "Ne4"},
            {"san": "Qxa2", "comment": "the only try; declining loses to Nd6+"},
            {"san": "Rd1", "comment": "..."}
          ],
          "comment": "summary placed on the last move of the line"
        }
      ]
    }
  }
}

Per-move comments inside variations are first-class: use them liberally —
every non-obvious move in a line should carry its own short why.
Validates the result by re-parsing before writing is declared done.
"""
import json, sys
import chess, chess.pgn

NAG = {"!": 1, "?": 2, "!!": 3, "??": 4, "!?": 5, "?!": 6}

spec = json.load(open(sys.argv[1]))
game = chess.pgn.read_game(open(spec["source_pgn"]))
new = chess.pgn.Game()
new.headers.update(game.headers)
if spec.get("annotator"):
    new.headers["Annotator"] = spec["annotator"]
if spec.get("game_comment"):
    new.comment = spec["game_comment"]

ann_by_ply = {int(k): v for k, v in spec.get("moves", {}).items()}
node = new
board = new.board()
def add_line(parent_node, parent_board, var):
    """Attach var["line"] as a variation of parent_node; steps may carry their
    own nested "variations" (alternatives to that step's move)."""
    vb = parent_board.copy()
    vnode = parent_node
    for step in var["line"]:
        step_parent_node, step_parent_board = vnode, vb.copy()
        m = vb.parse_san(step["san"])
        vb.push(m)
        vnode = vnode.add_variation(m)
        if step.get("glyph"):
            vnode.nags.add(NAG[step["glyph"]])
        if step.get("comment"):
            vnode.comment = step["comment"]
        for sub in step.get("variations", []):
            add_line(step_parent_node, step_parent_board, sub)
    if var.get("comment"):
        prev = (vnode.comment or "").rstrip()
        sep = "" if not prev else (" " if prev.endswith((".", "!", "?", ":")) else ". ")
        vnode.comment = prev + sep + var["comment"]

for i, mv in enumerate(game.mainline_moves()):
    ply = i + 1
    parent_board = board.copy()
    node = node.add_variation(mv)
    ann = ann_by_ply.get(ply)
    if ann:
        if ann.get("glyph"):
            node.nags.add(NAG[ann["glyph"]])
        if ann.get("comment"):
            node.comment = ann["comment"]
        for var in ann.get("variations", []):
            add_line(node.parent, parent_board, var)
    board.push(mv)

if spec.get("final_comment"):
    node.comment = (node.comment + " " if node.comment else "") + spec["final_comment"]

out = spec["output_pgn"]
print(new, file=open(out, "w"), end="\n")
check = chess.pgn.read_game(open(out))
if check.errors:
    for e in check.errors:
        print("PARSE ERROR:", e, file=sys.stderr)
    sys.exit(1)
print("wrote", out, "- parse clean")
