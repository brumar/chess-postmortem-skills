#!/usr/bin/env python3
"""Bundle a game into a standalone HTML analysis viewer (lichess-style).

usage: build_viewer.py <game>.pgn [--sweep sweep.json] [--analysis a.json b.json ...]
                       [--name "display name"] [-o out.html]

Produces a single self-contained HTML file (no fetch, works from file://):
board, move list with the PGN's comments/variations/glyphs, eval bar and
clickable eval graph (from the sweep), keyboard navigation, and an engine
panel. The engine panel prefers a local Stockfish (looked up at the relative
path engine/stockfish-17.1-lite-single.{js,wasm}, HTTP-served, from
the `stockfish` npm package); WITHOUT it, the panel falls back to the
cached Stockfish lines from:

- the sweep JSON (best + played move eval for every mainline position), and
- the analysis sidecars written by query.py --log (deep MultiPV lines and
  what-if refutations discovered during the investigation). Parallel
  investigators must each log to their OWN file (concurrent --log appends
  to one file race); pass them all here and they are merged.

So always pass --sweep, and pass --analysis when the investigators logged
sidecars: that is what makes the viewer useful offline.

Default output: <game>-viewer.html next to the PGN.
The page template + vendored JS live in ../assets/.
"""
import argparse
import json
import pathlib
import sys

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"


def merge_sidecars(paths):
    """Merge several query.py --log sidecars: union of positions; on the same
    position, one line per first pv move, preferring unrestricted then deeper."""
    merged = {"engine": None, "positions": {}}
    for path in paths:
        data = json.loads(pathlib.Path(path).read_text())
        merged["engine"] = merged["engine"] or data.get("engine")
        for fen, entry in (data.get("positions") or {}).items():
            key4 = " ".join(fen.split()[:4])
            tgt = None
            for k in merged["positions"]:
                if " ".join(k.split()[:4]) == key4:
                    tgt = k
                    break
            if tgt is None:
                merged["positions"][fen] = json.loads(json.dumps(entry))
                continue
            dst = merged["positions"][tgt]
            dst["depth"] = max(dst.get("depth") or 0, entry.get("depth") or 0)
            dst.setdefault("lines", [])
            for line in entry.get("lines", []):
                for i, old in enumerate(dst["lines"]):
                    if old["pv"][0] == line["pv"][0]:
                        keep_r = old.get("restricted", False) and line.get("restricted", False)
                        if line.get("depth", 0) >= old.get("depth", 0):
                            line = dict(line, restricted=keep_r)
                            dst["lines"][i] = line
                        else:
                            old["restricted"] = keep_r
                        break
                else:
                    dst["lines"].append(line)
            dst["lines"].sort(key=lambda L: L.get("restricted", False))
    return merged


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pgn")
    p.add_argument("--sweep", default="")
    p.add_argument("--analysis", nargs="*", default=[])
    p.add_argument("--name", default="")
    p.add_argument("-o", "--out", default="")
    a = p.parse_args()

    pgn_path = pathlib.Path(a.pgn)
    game = {"name": a.name or pgn_path.stem, "pgn": pgn_path.read_text()}
    if a.sweep:
        game["sweep"] = json.loads(pathlib.Path(a.sweep).read_text())
    if a.analysis:
        game["analysis"] = merge_sidecars(a.analysis)

    html = (ASSETS / "viewer.html").read_text()
    inlines = {
        'vendor/chess.js': (ASSETS / "chess.js").read_text(),
        'vendor/pieces.js': (ASSETS / "pieces.js").read_text(),
        'games.js': "window.EMBEDDED_GAMES = " + json.dumps([game]) + ";",
    }
    for src, js in inlines.items():
        tag = f'<script src="{src}"></script>'
        if tag not in html:
            sys.exit(f"template drift: {tag} not found in assets/viewer.html")
        js = js.replace("</", "<\\/")  # keep </script> etc. from closing the tag
        html = html.replace(tag, f"<script>\n// ---- inlined: {src} ----\n{js}\n</script>")

    out = pathlib.Path(a.out) if a.out else pgn_path.with_name(
        pgn_path.stem.removesuffix("-annotated") + "-viewer.html")
    out.write_text(html)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
