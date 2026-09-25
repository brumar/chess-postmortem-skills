#!/usr/bin/env python
"""Ask Stockfish about a position: eval + PV in SAN.

usage: query.py "<fen>" [--moves "e4 e5 ..."] [--multipv N] [--depth D] [--restrict "uci1,uci2"] [--log analysis.json]
--moves: SAN moves applied to the FEN before analysis.
--restrict: only search these root moves (uci), to answer "what if I play X?".
--log: also record the lines into an analysis sidecar JSON
       ({engine, positions: {"<fen>": {depth, lines: [{cp, mate, pv, restricted}]}}},
       evals white-POV, pv in UCI). The HTML viewer (build_viewer.py) shows
       these as cached engine lines when no local Stockfish is available.
"""
import argparse, json, sys
import chess, chess.engine

import os
SF = os.environ.get("STOCKFISH", "stockfish")

p = argparse.ArgumentParser()
p.add_argument("fen")
p.add_argument("--moves", default="")
p.add_argument("--multipv", type=int, default=3)
p.add_argument("--depth", type=int, default=24)
p.add_argument("--restrict", default="")
p.add_argument("--log", default="")
a = p.parse_args()

board = chess.Board(a.fen)
for san in a.moves.split():
    board.push_san(san)
print("position:", board.fen())
engine = chess.engine.SimpleEngine.popen_uci(SF)
engine.configure({"Threads": 4, "Hash": 512})
kw = {}
if a.restrict:
    kw["root_moves"] = [chess.Move.from_uci(u) for u in a.restrict.split(",")]
infos = engine.analyse(board, chess.engine.Limit(depth=a.depth), multipv=a.multipv, **kw)
for info in infos:
    score = info["score"].white()
    pv = info.get("pv", [])
    b2 = board.copy()
    sans = []
    for mv in pv[:14]:
        sans.append(b2.san(mv))
        b2.push(mv)
    print(f"  eval(white)={score}  pv: {' '.join(sans)}")

if a.log:
    data = {"engine": engine.id.get("name", "Stockfish"), "positions": {}}
    if os.path.exists(a.log):
        with open(a.log) as f:
            data = json.load(f)
        data.setdefault("positions", {})
    key = board.fen()
    # merge under the fen's first 4 fields (the viewer ignores the counters)
    key4 = " ".join(key.split()[:4])
    for k in list(data["positions"]):
        if " ".join(k.split()[:4]) == key4:
            key = k
            break
    entry = data["positions"].setdefault(key, {"depth": 0, "lines": []})
    restricted = bool(a.restrict)
    for info in infos:
        score = info["score"].white()
        pv = [m.uci() for m in info.get("pv", [])[:20]]
        if not pv:
            continue
        line = {"cp": score.score(mate_score=10000), "mate": score.mate(),
                "pv": pv, "depth": info.get("depth", a.depth),
                "restricted": restricted}
        # one line per first move: deeper info wins; once any full search saw
        # the move, it stays unrestricted (a restricted probe's eval for its
        # own root move is valid — only the "best of position" rank differs)
        for i, old in enumerate(entry["lines"]):
            if old["pv"][0] == pv[0]:
                keep_restricted = restricted and old.get("restricted", True)
                if line["depth"] >= old.get("depth", 0):
                    line["restricted"] = keep_restricted
                    entry["lines"][i] = line
                else:
                    old["restricted"] = keep_restricted
                break
        else:
            entry["lines"].append(line)
    entry["depth"] = max(entry.get("depth", 0), a.depth)
    # full-search lines first, then best-for-side-to-move first
    stm_white = board.turn == chess.WHITE
    entry["lines"].sort(key=lambda L: (L.get("restricted", False),
                                       -L["cp"] if stm_white else L["cp"]))
    with open(a.log, "w") as f:
        json.dump(data, f, indent=1)
    print(f"logged {len(infos)} line(s) to {a.log}")

engine.quit()
