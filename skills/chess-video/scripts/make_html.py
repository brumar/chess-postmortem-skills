#!/usr/bin/env python
"""Build a self-contained interactive HTML viewer from an annotated PGN.

usage: make_html.py <game>-annotated.pgn out.html [--sweep sweep.json] [--title "..."]

The page shows the annotated game as a readable document — mainline moves,
comments, engine variations in parentheses — where every move is clickable:
the board, the last-move highlight and the vertical eval gauge follow along.
Arrow keys step through the moves in reading order. No external assets.
"""
import argparse, html, json, math, os

import chess, chess.pgn

GLYPHS = {1: "!", 2: "?", 3: "!!", 4: "??", 5: "!?", 6: "?!"}


def white_share(ev):
    if ev == "mate":
        return 0.98
    if ev == "-mate":
        return 0.02
    return min(0.96, max(0.04, 0.5 + 0.5 * (2 / (1 + math.exp(-0.00368208 * ev)) - 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pgn")
    ap.add_argument("out")
    ap.add_argument("--sweep", default=None)
    ap.add_argument("--title", default=None)
    args = ap.parse_args()

    game = chess.pgn.read_game(open(args.pgn))
    tags = game.headers
    title = args.title or f'{tags.get("White","?")} vs {tags.get("Black","?")}'

    sweep_evals = {}
    if args.sweep:
        for e in json.load(open(args.sweep)):
            cp = e["eval_after_played"]
            sweep_evals[e["ply"]] = "mate" if cp >= 9900 else ("-mate" if cp <= -9900 else cp)

    nodes = {}       # id -> {fen, uci, eval}
    doc = []         # html fragments in reading order
    order = []       # clickable ids in reading order
    counter = [0]

    def label(board, move):
        n = board.fullmove_number
        return f"{n}.{board.san(move)}" if board.turn == chess.WHITE else f"{n}...{board.san(move)}"

    def emit_comment(text, cls):
        text = " ".join(text.split())
        if text:
            doc.append(f'<span class="{cls}">{html.escape(text)}</span> ')

    def walk(node, board, depth, mainline_ply):
        """Emit node's mainline continuation, with variations after each move."""
        while node.variations:
            main = node.variations[0]
            move = main.move
            nid = counter[0]; counter[0] += 1
            lbl = label(board, move)
            glyph = "".join(GLYPHS.get(n, "") for n in sorted(main.nags))
            board.push(move)
            ply = mainline_ply + 1 if depth == 0 else None
            ev = sweep_evals.get(ply) if ply else None
            nodes[nid] = {"fen": board.fen(), "uci": move.uci(), "eval": ev}
            order.append(nid)
            cls = "mv main" if depth == 0 else "mv var"
            doc.append(f'<span class="{cls}" data-id="{nid}">{html.escape(lbl + glyph)}</span> ')
            if main.comment:
                emit_comment(main.comment, "cm" if depth == 0 else "cm cmv")
            for alt in node.variations[1:]:
                doc.append('<span class="paren">(</span> ')
                walk_variation(node, alt, board.copy(stack=True), depth + 1)
                doc.append('<span class="paren">)</span> ')
            node = main
            if depth == 0:
                mainline_ply += 1

    def walk_variation(parent, first, board, depth):
        """Emit the line starting at `first` (an alternative to the move on top of
        `board`'s stack). Alternatives to a move inside the line are emitted right
        after that move, from the position it was played in; siblings of `first`
        itself belong to the caller."""
        board.pop()
        node, n = parent, first
        while n is not None:
            move = n.move
            nid = counter[0]; counter[0] += 1
            lbl = label(board, move)
            glyph = "".join(GLYPHS.get(g, "") for g in sorted(n.nags))
            board.push(move)
            nodes[nid] = {"fen": board.fen(), "uci": move.uci(), "eval": None}
            order.append(nid)
            doc.append(f'<span class="mv var" data-id="{nid}">{html.escape(lbl + glyph)}</span> ')
            if n.comment:
                emit_comment(n.comment, "cm cmv")
            if node is not parent:
                for alt in node.variations[1:]:
                    doc.append('<span class="paren">(</span> ')
                    walk_variation(node, alt, board.copy(stack=True), depth + 1)
                    doc.append('<span class="paren">)</span> ')
            node, n = n, (n.variations[0] if n.variations else None)

    start = chess.Board()
    nodes["start"] = {"fen": start.fen(), "uci": None, "eval": 20}
    if game.comment:
        doc.append(f'<p class="intro">{html.escape(" ".join(game.comment.split()))}</p>')
    walk(game, chess.Board(), 0, 0)

    meta_line = " · ".join(filter(None, [tags.get("Event"), tags.get("Date"),
                                         f'Result {tags.get("Result")}' if tags.get("Result") else None,
                                         tags.get("Annotator")]))

    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ --bg:#181614; --fg:#e8e4dc; --dim:#969088; --lt:#f0d9b5; --dk:#b58863;
           --hl:#aaa23a; --accent:#ffc85a; }}
  * {{ box-sizing:border-box }}
  body {{ margin:0; background:var(--bg); color:var(--fg);
         font:16px/1.55 Georgia,serif; }}
  header {{ padding:18px 28px 6px }}
  h1 {{ font:700 24px/1.2 "DejaVu Sans",sans-serif; margin:0 }}
  .meta {{ color:var(--dim); font:13px "DejaVu Sans",sans-serif; margin-top:4px }}
  .wrap {{ display:flex; gap:26px; padding:16px 28px 40px; align-items:flex-start; flex-wrap:wrap }}
  .left {{ position:sticky; top:14px; display:flex; gap:10px }}
  #board {{ display:grid; grid-template-columns:repeat(8,52px); grid-auto-rows:52px;
            border:3px solid #4a453e; user-select:none }}
  .sq {{ display:flex; align-items:center; justify-content:center; font-size:40px;
         line-height:1 }}
  .sq.l {{ background:var(--lt) }} .sq.d {{ background:var(--dk) }}
  .sq.hl {{ background:var(--hl) }}
  .wp {{ color:#fff; text-shadow:0 0 2px #000,0 0 2px #000 }}
  .bp {{ color:#111 }}
  #gauge {{ width:26px; height:calc(8*52px + 6px); border:2px solid #5a564f;
            display:flex; flex-direction:column; overflow:hidden }}
  #gtop {{ background:#2d2a28; transition:height .25s }}
  #gbot {{ background:#eeebe4; flex:1 }}
  .gwrap {{ text-align:center; font:700 13px "DejaVu Sans Mono",monospace }}
  #ev {{ margin-top:6px; color:var(--fg) }}
  .right {{ flex:1; min-width:340px; max-width:760px }}
  .mv {{ cursor:pointer; font:600 15px "DejaVu Sans",sans-serif; white-space:nowrap;
         padding:0 1px; border-radius:3px }}
  .mv.main {{ color:var(--fg) }}
  .mv.var {{ color:#a8c4e0; font-weight:400; font-size:14px }}
  .mv.sel {{ background:var(--accent); color:#20180a }}
  .mv:hover {{ outline:1px solid var(--accent) }}
  .cm {{ color:var(--dim) }}
  .cm.cmv {{ font-size:14px }}
  .paren {{ color:#6e6a63 }}
  .intro {{ color:var(--dim); border-left:3px solid var(--accent); padding-left:12px }}
  .hint {{ color:#6e6a63; font:12px "DejaVu Sans",sans-serif; margin-top:18px }}
</style></head><body>
<header><h1>{html.escape(title)}</h1><div class="meta">{html.escape(meta_line)}</div></header>
<div class="wrap">
  <div class="left">
    <div class="gwrap"><div id="gauge"><div id="gtop"></div><div id="gbot"></div></div>
      <div id="ev"></div></div>
    <div id="board"></div>
  </div>
  <div class="right" id="text">{"".join(doc)}
    <div class="hint">Click any move — arrow keys step through in reading order.
    Blue moves are engine lines. Eval gauge: White from the bottom, from the
    Stockfish sweep (mainline moves only).</div>
  </div>
</div>
<script>
const NODES = {json.dumps(nodes)};
const ORDER = {json.dumps(["start"] + order)};
const PIECES = {{"P":"\\u2659","N":"\\u2658","B":"\\u2657","R":"\\u2656","Q":"\\u2655","K":"\\u2654",
                "p":"\\u265f","n":"\\u265e","b":"\\u265d","r":"\\u265c","q":"\\u265b","k":"\\u265a"}};
const board = document.getElementById("board");
const cells = [];
for (let r = 8; r >= 1; r--) for (let f = 0; f < 8; f++) {{
  const c = document.createElement("div");
  c.className = "sq " + ((r + f) % 2 ? "l" : "d");
  c.dataset.sq = "abcdefgh"[f] + r;
  board.appendChild(c); cells.push(c);
}}
let cur = "start", lastEval = 20;
function show(id) {{
  const n = NODES[id]; if (!n) return;
  cur = id;
  const fen = n.fen.split(" ")[0];
  let sqs = {{}};
  let r = 8, f = 0;
  for (const ch of fen) {{
    if (ch === "/") {{ r--; f = 0; }}
    else if (ch >= "1" && ch <= "8") f += +ch;
    else {{ sqs["abcdefgh"[f] + r] = ch; f++; }}
  }}
  for (const c of cells) {{
    const p = sqs[c.dataset.sq];
    c.textContent = p ? PIECES[p] : "";
    c.classList.remove("wp","bp","hl");
    if (p) c.classList.add(p === p.toUpperCase() ? "wp" : "bp");
    if (n.uci && (c.dataset.sq === n.uci.slice(0,2) || c.dataset.sq === n.uci.slice(2,4)))
      c.classList.add("hl");
  }}
  if (n.eval !== null && n.eval !== undefined) lastEval = n.eval;
  const ev = lastEval;
  let share = 0.5, txt = "";
  if (ev === "mate") {{ share = 0.98; txt = "#"; }}
  else if (ev === "-mate") {{ share = 0.02; txt = "#"; }}
  else {{ share = Math.min(.96, Math.max(.04, .5 + .5*(2/(1+Math.exp(-0.00368208*ev))-1)));
         txt = (ev >= 0 ? "+" : "") + (ev/100).toFixed(1); }}
  document.getElementById("gtop").style.height = (100*(1-share)) + "%";
  document.getElementById("ev").textContent = (n.eval === null || n.eval === undefined) ? "\\u2014" : txt;
  document.querySelectorAll(".mv.sel").forEach(e => e.classList.remove("sel"));
  const el = document.querySelector(`.mv[data-id="${{id}}"]`);
  if (el) {{ el.classList.add("sel");
             el.scrollIntoView({{block: "nearest", behavior: "smooth"}}); }}
}}
document.getElementById("text").addEventListener("click", e => {{
  const t = e.target.closest(".mv"); if (t) show(t.dataset.id);
}});
document.addEventListener("keydown", e => {{
  const i = ORDER.indexOf(isNaN(+cur) ? cur : +cur);
  if (e.key === "ArrowRight" && i < ORDER.length - 1) {{ show(ORDER[i+1]); e.preventDefault(); }}
  if (e.key === "ArrowLeft" && i > 0) {{ show(ORDER[i-1]); e.preventDefault(); }}
}});
show("start");
</script></body></html>
"""
    open(args.out, "w").write(page)
    print(f"wrote {args.out} ({len(order)} moves, {os.path.getsize(args.out)//1024} KB)")


if __name__ == "__main__":
    main()
