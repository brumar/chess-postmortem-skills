#!/usr/bin/env python
"""Turn a storyboard JSON into a narrated chess video (board + arrows + eval gauge
+ full move-by-move playthrough + subtitles).

usage: make_video.py storyboard.json out.mp4 [--workdir DIR]
NOTE: the final ffmpeg runs with cwd = the storyboard's directory; pass an
ABSOLUTE out path (a relative one resolves against that directory).

Storyboard format:
{
  "title": "...", "subtitle": "...",
  "pgn": "relative/path/to/game.pgn",      # mainline source; a [FEN] tag sets the start
         # position (single-position videos: no moves, every shot at ply 0)
  "sweep": "relative/path/to/sweep.json",  # per-ply evals (bridge shots' gauge)
  "tts": { "engine": "piper", "model": "voices/en_US-lessac-medium.onnx" },
         # or { "engine": "espeak", "voice": "en-us+m3", "speed": 160 }
  "bridge_sec": 0.45,                      # optional: seconds per auto-inserted
         # bridge move (default BRIDGE_SEC = 1.0). Lower it when a video opens by
         # replaying a long prefix of the game to reach the position it discusses.
  "bridge_run_max": 5.0,                   # optional: cap on one run of bridges;
         # a longer run flips through faster instead of stalling the narration.
  "segments": [
    {
      "narration": "spoken text",          # split into sentences, then handed to
         # the shots below in proportion to their weights. A shot may instead
         # carry its own "narration" for exact control; when ANY shot in a
         # segment does, the segment-level "narration" is ignored.
      "shots": [
        { "ply": 15,                       # position after N plies of the mainline
          "var": "Nxe4 Qxe4",              # optional SAN moves played on top (engine line)
          "arrows": "c3e4g,f4b4r,b2b2y",   # uci pairs + color suffix g/r/b/y; from==to draws a circle
          "caption": "12.Bf4?!",           # big label in side panel
          "note": "Better was 12.Ne4!",    # small label under caption
          "eval": -90,                     # centipawns, White POV; "mate"/"-mate" for decided
          "weight": 1,                     # share of the segment's NARRATION
          "narration": "spoken text",      # optional: this shot's own sentences
          "lead": 6.0,                     # optional: let this shot's narration start
                                           # that many seconds before its bridge run ends
                                           # (default BRIDGE_LEAD). Raise it for an intro
                                           # replay the narration talks over.
          "hold": 2.0 }                    # optional: extra seconds of silence ON this shot —
                                           # use it where the viewer needs time to digest
      ]
    }
  ]
}

Every mainline ply between storyboard shots is auto-inserted as a short "bridge"
shot, so the whole game plays through move by move. Narration is synthesized
sentence by sentence; the timings drive an SRT that is burned into the video and
also written next to the output file.

AUDIO/VIDEO SYNC: each shot is one block that occupies the SAME interval in the
audio and in the video. A block is [bridge moves] + [the shot's sentences] +
[hold], and its sentences are the ones assigned to that shot, so a sentence is
always heard while its own shot is on screen. Narration may start at most
BRIDGE_LEAD seconds before the bridge run ends (so a move is being played as the
narrator introduces it); everything else in the run is real silence, inserted
right there rather than banked up for the end of the segment.

Continuity rule (rewind back, never jump forward): the displayed position never
skips forward over unseen moves. Whenever a shot's position extends what is on
screen, each new move is ANIMATED (the piece slides square to square); entering
an engine line first REWINDS to the branch point with fast undo-slides (beyond
REW_MAX_MOVES it snaps), then plays the line's moves in. Returning to the game
replays the skipped mainline moves the same way. Any frame whose position is
off the mainline carries a "BRANCH" banner across the top of the board.

Settled mainline frames also carry chess.com-style QUALITY BADGES on the
destination square (glyph parsed from the caption, else derived from the
sweep's centipawn loss: ?! at 0.3, ? at 0.9, ?? at 2.0) and an eval DELTA
(up/down arrow + pawns, White POV, vs the previous ply's sweep eval) next to
the eval readout.
"""
import argparse, io, json, math, os, re, subprocess, wave

import cairosvg, chess, chess.pgn, chess.svg
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BOARD = 600
BOARD_XY = (40, 26)
GAUGE_X, GAUGE_W = BOARD_XY[0] + BOARD + 18, 34
PANEL_X = GAUGE_X + GAUGE_W + 36
PAUSE = 0.7            # silence appended after each narration segment
SENT_GAP = 0.12        # silence between sentences
BRIDGE_SEC = 1.0       # seconds per auto-inserted bridge move
BRIDGE_RUN_MAX = 5.0   # cap on ONE uninterrupted run of bridges; longer runs flip faster
BRIDGE_MIN_SEC = 0.30  # ...but never faster than this per move
BRIDGE_LEAD = 1.2      # narration may start this early, over the tail of a bridge run
                       # (per-shot override: "lead")
MIN_SETTLE = 0.8       # a shot with narration still holds its settled frame this long
MIN_SHOT_SEC = 1.2     # a shot that got no sentences at all is held this long
FPS = 30
START_FEN = chess.STARTING_FEN  # overridden by the PGN's [FEN] tag (single-position videos)
BG = (24, 22, 20)
FG = (232, 228, 220)
DIM = (150, 145, 138)

# piece-slide animation (continuity: forward moves are played, never teleported)
ANIM_SLIDE = 0.28      # seconds a piece takes to slide one move
ANIM_SETTLE = 0.17     # dwell on a settled position between chained animated moves
ANIM_FRAMES = 7        # interpolation frames per slide
ANIM_MAX_SHARE = 0.6   # animation never eats more than this share of a shot's duration
REW_SLIDE = 0.12       # backward moves rewind fast (an "undo" slide, no settle)
REW_FRAMES = 5
REW_MAX_MOVES = 8      # beyond this a backward jump snaps instead of rewinding

# chess.com-style move-quality badges, drawn on the destination square's corner
BADGES = {"!!": (27, 172, 166), "!": (129, 182, 76), "!?": (92, 139, 176),
          "?!": (247, 198, 49), "?": (255, 164, 89), "??": (250, 65, 45)}
GLYPH_RE = re.compile(r"([?!]{1,2})$")

# chess.svg board geometry (coordinates=True): 8*45 squares + 15 margin each side
SVG_UNITS, SVG_MARGIN, SVG_SQ = 390.0, 15.0, 45.0

BRANCH_BG = (168, 100, 26)
BRANCH_FG = (255, 240, 220)

ARROW_COLORS = {"g": "#15781BB0", "r": "#992020B0", "b": "#003088B0", "y": "#E6912CB0"}
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
F_TITLE = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 28)
F_SUB = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 20)
F_MOVE = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 44)
F_EVAL = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono-Bold.ttf", 30)
F_NOTE = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 23)
F_LIST = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono.ttf", 21)
F_LIST_B = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono-Bold.ttf", 21)
F_SMALL = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans.ttf", 16)
F_BANNER = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 22)
F_BADGE = ImageFont.truetype(f"{FONT_DIR}/DejaVuSans-Bold.ttf", 16)
F_DELTA = ImageFont.truetype(f"{FONT_DIR}/DejaVuSansMono-Bold.ttf", 22)


def white_share(ev):
    """Lichess-style win-probability mapping, clamped a touch for looks."""
    if ev == "mate":
        return 0.98
    if ev == "-mate":
        return 0.02
    wp = 0.5 + 0.5 * (2 / (1 + math.exp(-0.00368208 * ev)) - 1)
    return min(0.96, max(0.04, wp))


def eval_text(ev):
    if ev == "mate":
        return "#  "
    if ev == "-mate":
        return "  #"
    return f"{ev / 100:+.1f}"


def move_label(ply, san):
    n = (ply + 1) // 2
    return f"{n}.{san}" if ply % 2 else f"{n}...{san}"


def position_for(game_moves, ply, var):
    board = chess.Board(START_FEN)
    for mv in game_moves[:ply]:
        board.push(mv)
    for san in var.split():
        board.push_san(san)
    return board


def board_image(board, arrows_spec="", lastmove=None):
    """Render the board alone to a PIL image."""
    arrows = []
    for spec in filter(None, arrows_spec.split(",")):
        color = ARROW_COLORS.get(spec[4:5], ARROW_COLORS["g"])
        arrows.append(chess.svg.Arrow(chess.parse_square(spec[:2]),
                                      chess.parse_square(spec[2:4]), color=color))
    svg = chess.svg.board(board, lastmove=lastmove, arrows=arrows,
                          size=BOARD, coordinates=True)
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=BOARD)
    return Image.open(io.BytesIO(png)).convert("RGB")


_sprites = {}


def piece_sprite(piece, px):
    key = (piece.symbol(), px)
    if key not in _sprites:
        png = cairosvg.svg2png(bytestring=chess.svg.piece(piece).encode(),
                               output_width=px, output_height=px)
        _sprites[key] = Image.open(io.BytesIO(png)).convert("RGBA")
    return _sprites[key]


def square_topleft(sq):
    """Pixel top-left of a square inside the rendered board image (white POV)."""
    s = BOARD / SVG_UNITS
    x = (SVG_MARGIN + chess.square_file(sq) * SVG_SQ) * s
    y = (SVG_MARGIN + (7 - chess.square_rank(sq)) * SVG_SQ) * s
    return x, y


def compose(board_img, shot, meta, sans, branch, badge=None, delta=None):
    """Full 1280x720 frame around an already-rendered board image.

    badge: (glyph, to_square) — chess.com-style quality marker on the move's
    destination square. delta: eval change in cp vs the previous position
    (White POV), shown as an up/down arrow next to the eval."""
    img = Image.new("RGB", (W, H), BG)
    img.paste(board_img, BOARD_XY)
    d = ImageDraw.Draw(img)

    if badge and badge[0] in BADGES:
        glyph, to_sq = badge
        sq = BOARD / SVG_UNITS * SVG_SQ
        sx, sy = square_topleft(to_sq)
        cx = BOARD_XY[0] + sx + sq * 0.82
        cy = BOARD_XY[1] + sy + sq * 0.18
        r = 16
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BADGES[glyph],
                  outline=(250, 248, 244), width=2)
        d.text((cx, cy - 1), glyph, font=F_BADGE, fill=(255, 255, 255), anchor="mm")

    if branch:
        # banner across the top of the board + orange border: we are OFF the game
        bx, by = BOARD_XY
        d.rectangle([bx, by, bx + BOARD - 1, by + BOARD - 1], outline=BRANCH_BG, width=3)
        d.rectangle([bx, by, bx + BOARD - 1, by + 32], fill=BRANCH_BG)
        label = "BRANCH · engine line"
        tw = d.textlength(label, font=F_BANNER)
        d.text((bx + (BOARD - tw) // 2, by + 4), label, font=F_BANNER, fill=BRANCH_FG)

    # vertical eval gauge, White fills from the bottom
    gy, gh = BOARD_XY[1], BOARD
    share = white_share(shot["eval"])
    split = gy + gh - int(gh * share)
    d.rectangle([GAUGE_X, gy, GAUGE_X + GAUGE_W, split], fill=(45, 42, 40))
    d.rectangle([GAUGE_X, split, GAUGE_X + GAUGE_W, gy + gh], fill=(238, 235, 228))
    d.rectangle([GAUGE_X, gy, GAUGE_X + GAUGE_W, gy + gh], outline=(90, 86, 80), width=2)
    d.line([GAUGE_X, gy + gh // 2, GAUGE_X + GAUGE_W, gy + gh // 2], fill=(130, 60, 60), width=1)

    # side panel
    x = PANEL_X
    d.text((x, 30), meta["title"], font=F_TITLE, fill=FG)
    d.text((x, 68), meta["subtitle"], font=F_SUB, fill=DIM)
    d.line([x, 104, W - 40, 104], fill=(70, 66, 60), width=1)
    d.text((x, 150), shot.get("caption", ""), font=F_MOVE, fill=FG)
    ev = shot["eval"]
    ecol = (235, 235, 230) if ev == "mate" or (ev != "-mate" and ev >= 0) else (120, 120, 120)
    d.text((x, 222), eval_text(ev), font=F_EVAL, fill=ecol)
    if delta is not None:
        up = delta >= 0
        d.text((x + 170, 228), f"{'▲' if up else '▼'} {abs(delta) / 100:.1f}",
               font=F_DELTA, fill=(110, 190, 110) if up else (225, 120, 105))
    if shot.get("var"):
        d.text((x + 160, 232), "engine line", font=F_SMALL, fill=(220, 160, 60))
    note = shot.get("note", "")
    if note:
        yy = 278
        line = ""
        for word in note.split():
            if d.textlength(line + " " + word, font=F_NOTE) > W - 60 - x:
                d.text((x, yy), line.strip(), font=F_NOTE, fill=DIM)
                yy += 32
                line = word
            else:
                line += " " + word
        d.text((x, yy), line.strip(), font=F_NOTE, fill=DIM)

    # recent-moves list, current half-move highlighted
    ply = shot["ply"]
    if ply:
        d.line([x, 370, W - 40, 370], fill=(70, 66, 60), width=1)
        first_move = max(1, (ply + 1) // 2 - 5)
        yy = 388
        for n in range(first_move, (ply + 1) // 2 + 1):
            wp_ply, bp_ply = 2 * n - 1, 2 * n
            d.text((x, yy), f"{n:>2}.", font=F_LIST, fill=DIM)
            wsan = sans[wp_ply - 1] if wp_ply <= len(sans) else ""
            bsan = sans[bp_ply - 1] if bp_ply <= ply and bp_ply <= len(sans) else ""
            cur = (255, 200, 90)
            d.text((x + 44, yy), wsan, font=F_LIST_B if wp_ply == ply and not shot.get("var") else F_LIST,
                   fill=cur if wp_ply == ply and not shot.get("var") else FG)
            if bsan and wp_ply <= ply:
                d.text((x + 180, yy), bsan, font=F_LIST_B if bp_ply == ply and not shot.get("var") else F_LIST,
                       fill=cur if bp_ply == ply and not shot.get("var") else FG)
            yy += 30
    return img


SENT_RE = re.compile(r"(?<=[.!?:])\s+")


def split_sentences(text):
    return [s.strip() for s in SENT_RE.split(text) if s.strip()]


class PiperTTS:
    def __init__(self, model):
        from piper import PiperVoice
        self.voice = PiperVoice.load(model)

    def synth(self, text, out_wav):
        with wave.open(out_wav, "wb") as wf:
            if hasattr(self.voice, "synthesize_wav"):
                self.voice.synthesize_wav(text, wf)
            else:
                self.voice.synthesize(text, wf)
        with wave.open(out_wav) as wf:
            return wf.getnframes() / wf.getframerate(), wf.getparams()


class EspeakTTS:
    def __init__(self, voice="en-us+m3", speed=160):
        self.voice, self.speed = voice, speed

    def synth(self, text, out_wav):
        subprocess.run(["espeak-ng", "-v", self.voice, "-s", str(self.speed),
                        "-w", out_wav, text], check=True)
        with wave.open(out_wav) as wf:
            return wf.getnframes() / wf.getframerate(), wf.getparams()


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms % 3600000 // 60000:02d}:{ms % 60000 // 1000:02d},{ms % 1000:03d}"


def ease(t):
    return 3 * t * t - 2 * t * t * t


def assign_sentences(durs, weights):
    """Hand a segment's sentences to its shots, in order, so each shot gets
    roughly its weight's share of the narration time. Returns one list of
    sentence indices per shot (possibly empty when sentences are scarce)."""
    n, m = len(weights), len(durs)
    groups = [[] for _ in range(n)]
    if not m or not n:
        return groups
    total = sum(d + SENT_GAP for d in durs)
    wsum = sum(weights) or 1.0
    acc, targets = 0.0, []
    for w in weights:
        acc += total * w / wsum
        targets.append(acc)
    i, t = 0, 0.0
    for gi in range(n):
        # keep one sentence in reserve for each shot still to come
        while i < m and m - i > n - gi - 1:
            d = durs[i] + SENT_GAP
            if groups[gi] and gi < n - 1 and abs(t + d - targets[gi]) > abs(t - targets[gi]):
                break
            groups[gi].append(i)
            t += d
            i += 1
    for k in range(i, m):
        groups[-1].append(k)
    return groups


def auto_glyph(loss):
    """Sweep centipawn loss -> quality badge, same bands as the annotations."""
    if loss is None:
        return None
    if loss >= 200:
        return "??"
    if loss >= 90:
        return "?"
    if loss >= 30:
        return "?!"
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard")
    ap.add_argument("out")
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args()

    sb = json.load(open(args.storyboard))
    base = os.path.dirname(os.path.abspath(args.storyboard))
    work = args.workdir or os.path.join(base, "work")
    os.makedirs(work, exist_ok=True)

    game = chess.pgn.read_game(open(os.path.join(base, sb["pgn"])))
    game_moves = list(game.mainline_moves())
    global START_FEN
    START_FEN = game.board().fen()
    b = chess.Board(START_FEN)
    sans = []
    for mv in game_moves:
        sans.append(b.san(mv))
        b.push(mv)

    sweep_evals, sweep_loss = {}, {}
    if sb.get("sweep"):
        for e in json.load(open(os.path.join(base, sb["sweep"]))):
            cp = e["eval_after_played"]
            sweep_evals[e["ply"]] = "mate" if cp >= 9900 else ("-mate" if cp <= -9900 else cp)
            sweep_loss[e["ply"]] = e.get("loss_for_mover")

    bridge_sec = float(sb.get("bridge_sec", BRIDGE_SEC))
    run_max = float(sb.get("bridge_run_max", BRIDGE_RUN_MAX))

    meta = {"title": sb.get("title", ""), "subtitle": sb.get("subtitle", "")}
    tts_cfg = sb.get("tts", {"engine": "espeak"})
    if tts_cfg.get("engine") == "piper":
        tts = PiperTTS(os.path.join(base, tts_cfg["model"]))
    else:
        tts = EspeakTTS(tts_cfg.get("voice", "en-us+m3"), tts_cfg.get("speed", 160))

    # synthesize narration sentence by sentence, remembering which shot owns each
    seg_wavs, seg_groups, params = [], [], None
    for si, seg in enumerate(sb["segments"]):
        shots = seg["shots"]
        per_shot = [s.get("narration") for s in shots]
        if any(per_shot):
            # the author placed the words himself: one group per shot, verbatim
            texts, groups = [], []
            for text in per_shot:
                g = []
                for sent in split_sentences(text or ""):
                    g.append(len(texts))
                    texts.append(sent)
                groups.append(g)
        else:
            texts, groups = split_sentences(seg.get("narration", "")), None
        wavs = []
        for ki, sent in enumerate(texts):
            wav = os.path.join(work, f"s{si:02d}_{ki:02d}.wav")
            dur, params = tts.synth(sent, wav)
            wavs.append((wav, dur, sent))
        if groups is None:
            groups = assign_sentences([d for _, d, _ in wavs],
                                      [s.get("weight", 1) for s in shots])
        seg_wavs.append(wavs)
        seg_groups.append(groups)
        print(f"segment {si}: {sum(d + SENT_GAP for _, d, _ in wavs):.1f}s narration"
              f" over {len(shots)} shot(s) {[len(g) for g in groups]}")

    # bridge shots for the mainline plies no shot stops on
    seg_bridges = []
    mainline_ptr = 0
    for si, seg in enumerate(sb["segments"]):
        bridges = []   # (insert_before_shot_index, ply)
        for ci, shot in enumerate(seg["shots"]):
            if not shot.get("var") and shot["ply"] > mainline_ptr:
                for p in range(mainline_ptr + 1, shot["ply"]):
                    bridges.append((ci, p))
                mainline_ptr = shot["ply"]
        seg_bridges.append(bridges)

    # Lay every segment out as a chain of shot BLOCKS. A block takes exactly the
    # same interval in the audio and in the video, so the narration can never
    # drift away from the position on screen:
    #   video  = [bridge run] [settled shot .. hold .. segment pause]
    #   audio  = [silence   ] [the shot's own sentences, hold, pause]
    # The narration is allowed to start BRIDGE_LEAD before the run ends (a move
    # slides in while the narrator introduces it); the rest of the run is silent.
    layout = []
    for si, seg in enumerate(sb["segments"]):
        shots, blocks = seg["shots"], []
        durs = [d for _, d, _ in seg_wavs[si]]
        for ci, shot in enumerate(shots):
            plies = [p for bci, p in seg_bridges[si] if bci == ci]
            per = max(BRIDGE_MIN_SEC, min(bridge_sec, run_max / len(plies))) if plies else 0.0
            run = per * len(plies)
            sents = seg_groups[si][ci]
            narr = sum(durs[j] + SENT_GAP for j in sents)
            if sents:
                lead = min(run, float(shot.get("lead", BRIDGE_LEAD)),
                           max(0.0, narr - MIN_SETTLE))
                body = narr - lead
            else:
                lead, body = 0.0, MIN_SHOT_SEC
            blocks.append({"shot": shot, "plies": plies, "per": per,
                           "pre": run - lead, "sents": sents, "body": body,
                           "hold": shot.get("hold", 0.0),
                           "tail": PAUSE if ci == len(shots) - 1 else 0.0})
        layout.append(blocks)

    # audio, written block by block in the same order the video emits them
    subs, cursor = [], 0.0
    narration = os.path.join(work, "narration.wav")
    with wave.open(narration, "wb") as out:
        out.setparams(params)

        def silence(sec):
            nonlocal cursor
            out.writeframes(b"\x00\x00" * int(params.framerate * sec) * params.nchannels)
            cursor += sec

        for si, blocks in enumerate(layout):
            for blk in blocks:
                silence(blk["pre"])
                for j in blk["sents"]:
                    wav, dur, sent = seg_wavs[si][j]
                    subs.append((cursor, cursor + dur, sent))
                    with wave.open(wav) as wf:
                        out.writeframes(wf.readframes(wf.getnframes()))
                    cursor += dur
                    silence(SENT_GAP)
                if not blk["sents"]:
                    silence(blk["body"])
                silence(blk["hold"] + blk["tail"])

    # video timeline
    concat_lines = []
    total = 0.0
    frame_idx = 0
    prev_stack = []          # moves of the position currently on screen
    px_sq = int(round(BOARD / SVG_UNITS * SVG_SQ))

    def put(img, dur):
        nonlocal frame_idx, total
        png = os.path.join(work, f"f{frame_idx:04d}.png")
        img.save(png)
        concat_lines.extend([f"file '{png}'", f"duration {dur:.3f}"])
        frame_idx += 1
        total += dur

    def off_mainline(stack):
        return list(stack) != game_moves[:len(stack)]

    def animate(board_before, move, shot, meta_, sans_, branch, slide_t,
                frames=ANIM_FRAMES, reverse=False):
        """Slide the moving piece square to square (K quick frames).
        reverse=True plays the move backward: an undo slide, to → from."""
        frames = max(2, min(frames, int(round(slide_t * FPS)) or 2))
        piece = board_before.piece_at(move.from_square)
        ghost = board_before.copy()
        ghost.remove_piece_at(move.from_square)
        frame = compose(board_image(ghost), shot, meta_, sans_, branch)
        sprite = piece_sprite(piece, px_sq)
        x0, y0 = square_topleft(move.from_square)
        x1, y1 = square_topleft(move.to_square)
        if reverse:
            (x0, y0), (x1, y1) = (x1, y1), (x0, y0)
        for k in range(1, frames + 1):
            t = ease(k / (frames + 1))
            fx = BOARD_XY[0] + x0 + (x1 - x0) * t
            fy = BOARD_XY[1] + y0 + (y1 - y0) * t
            img = frame.copy()
            img.paste(sprite, (int(fx), int(fy)), sprite)
            put(img, slide_t / frames)

    def emit(shot, dur):
        nonlocal prev_stack
        target = position_for(game_moves, shot["ply"], shot.get("var", ""))
        tstack = list(target.move_stack)
        L = 0
        while L < len(tstack) and L < len(prev_stack) and tstack[L] == prev_stack[L]:
            L += 1
        fwd = tstack[L:]
        back = prev_stack[L:]
        if len(back) > REW_MAX_MOVES:
            back = []  # too deep: snap back instead of rewinding
        n = len(fwd)
        ideal = len(back) * REW_SLIDE + n * (ANIM_SLIDE + ANIM_SETTLE)
        f = min(1.0, (ANIM_MAX_SHARE * dur) / ideal) if ideal else 0.0
        slide_t, settle_t, rew_t = ANIM_SLIDE * f, ANIM_SETTLE * f, REW_SLIDE * f
        spent = 0.0

        # backward jump: fast undo slides, most recent move first
        if back:
            pb = chess.Board(START_FEN)
            for mv in prev_stack:
                pb.push(mv)
            while len(pb.move_stack) > L:
                was_off = off_mainline(pb.move_stack)
                mv = pb.pop()
                animate(pb, mv, shot, meta, sans, was_off, rew_t,
                        frames=REW_FRAMES, reverse=True)
                spent += rew_t

        rb = chess.Board(START_FEN)
        for mv in tstack[:L]:
            rb.push(mv)

        for i, mv in enumerate(fwd):
            branch = bool(shot.get("var")) if i == n - 1 else off_mainline(rb.move_stack + [mv])
            animate(rb, mv, shot, meta, sans, branch, slide_t)
            spent += slide_t
            rb.push(mv)
            if i < n - 1:
                put(compose(board_image(rb, lastmove=mv), shot, meta, sans, branch), settle_t)
                spent += settle_t

        # settled final position: shot arrows, quality badge, eval delta
        branch = bool(shot.get("var")) or off_mainline(tstack)
        badge = delta = None
        if not shot.get("var") and shot["ply"] > 0 and target.move_stack:
            m = GLYPH_RE.search(shot.get("caption", ""))
            glyph = m.group(1) if m else auto_glyph(sweep_loss.get(shot["ply"]))
            if glyph:
                badge = (glyph, target.move_stack[-1].to_square)
            prev_ev = sweep_evals.get(shot["ply"] - 1)
            if isinstance(shot["eval"], int) and isinstance(prev_ev, int):
                delta = shot["eval"] - prev_ev
        last = target.move_stack[-1] if target.move_stack else None
        img = compose(board_image(target, shot.get("arrows", ""), last), shot, meta, sans,
                      branch, badge=badge, delta=delta)
        put(img, max(0.05, dur - spent))
        prev_stack = tstack

    for blocks in layout:
        for blk in blocks:
            shot = blk["shot"]
            for ply in blk["plies"]:
                emit({"ply": ply, "caption": move_label(ply, sans[ply - 1]),
                      "eval": sweep_evals.get(ply, shot["eval"])}, blk["per"])
            emit(shot, blk["body"] + blk["hold"] + blk["tail"])
    concat_lines.append(concat_lines[-2])  # concat demuxer needs the last frame repeated

    srt = os.path.join(work, "subs.srt")
    with open(srt, "w") as f:
        for i, (t0, t1, text) in enumerate(subs, 1):
            f.write(f"{i}\n{srt_time(t0)} --> {srt_time(t1)}\n{text}\n\n")
    out_srt = os.path.splitext(args.out)[0] + ".srt"
    open(out_srt, "w").write(open(srt).read())

    lst = os.path.join(work, "shots.txt")
    open(lst, "w").write("\n".join(concat_lines) + "\n")
    style = ("FontName=DejaVu Sans,FontSize=12,PrimaryColour=&H00F0EEE8,"
             "OutlineColour=&HA0000000,Outline=1,Shadow=0,MarginV=10")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-i", narration,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-vf", f"fps={FPS},subtitles={srt}:force_style='{style}',format=yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-shortest", args.out],
                   check=True, cwd=base)
    print(f"wrote {args.out} ({total:.0f}s video, {frame_idx} frames) + {out_srt}")


if __name__ == "__main__":
    main()
