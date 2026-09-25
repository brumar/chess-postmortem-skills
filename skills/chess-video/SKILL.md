---
name: chess-video
description: Produce a narrated video post-mortem of an analyzed chess game (stage 3), plus an interactive HTML viewer of the full annotations. Builds on the chess-analysis skill's outputs (annotated PGN + eval sweep) — runs that skill first if they don't exist. The video shows the whole game move by move with commentary arrows, a vertical eval gauge, a running move list, piper TTS narration and burned-in subtitles, and stops once on the game's quiet turning point to lay out both sides' strategic plans; the HTML page lets the user click through every move and engine line. Use when the user asks for a video of a game, a "stage 3", a narrated/video review, a game recap video, or a shareable post-mortem package.
---

# Chess video post-mortem: storyboard, narrate, package

Goal: a 3–10 minute video a human enjoys watching PLUS an interactive HTML
page for the details the video can't hold. The video tells the game's
*story* (the annotated PGN already knows it); the HTML keeps every engine
line clickable. Both ship together.

Tools live in this skill's `scripts/` folder: `make_video.py` (storyboard JSON →
narrated mp4 + srt) and `make_html.py` (annotated PGN → self-contained
HTML viewer). Read their docstrings before writing the storyboard.

## 0. Prerequisites — stage 2, and the level you are writing for

You need `<game>-annotated.pgn` and a sweep JSON (per-ply evals). If either
is missing, run the **chess-analysis** skill first — do not improvise
annotations for the video; the narration's authority comes from the
verified engine work.

You also need the **audience level**. Take it from `annotations.json`
(`audience.level`), and if that file predates the field, redo the stage-0
decision here: for the user's own games, the level they gave you (ask
once if unknown), whatever the PGN's Elo header says. For anyone else's
game, the PGN's Elo for the reviewed side; ask if it is
missing or provisional.

Two rules come out of that number, and the video breaks them more easily
than the PGN does, because narration wants to round off every beat with a
lesson:

- **Never spend narration proving what the player can see.** At 1800: that
  a piece hangs, that a one-move fork works, that a rook may not step onto
  a defended square. State it in a clause, then talk about the part that
  is hard — the move order, the plan, the cost of the trade. Full table in
  the chess-analysis skill's `references/style.md`.
- **A fact once is a fact; a fact three times is a lecture.** Say "both
  checks drop the rook" where it happens. Do not then close the segment
  with it and repeat it in the finale.

A past video shipped with all three occurrences of exactly that line, and
the viewer's reaction is the reason this section exists.

## 1. Setup

- System: `sudo apt-get install ffmpeg espeak-ng`.
- Venv (repo convention `.venv-chess` at repo root):
  `pip install python-chess cairosvg pillow piper-tts`.
- Piper voice (better than espeak; ~60 MB, one-time):
  ```sh
  mkdir -p chess-games/video/voices && cd chess-games/video/voices
  curl -sSLO "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
  curl -sSLO "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
  ```
  No network? Set `"tts": {"engine": "espeak"}` in the storyboard instead.

## 2. Write the storyboard — this is the craft step

One JSON per game (`chess-games/video/storyboard-NNN.json`; full format in
`make_video.py`'s docstring). Author it FROM the annotated PGN: the
game_comment gives the arc, the `$2/$4` moves give the beats.

**Structure.** ~2.5–3 segments per minute of target duration. A 3-minute
video ≈ 8 segments: one intro (players, opening, what the game will be
about), one segment per major swing or lesson (every ≥0.7-pawn mistake
deserves one; group smaller ones), **exactly one plan-pause segment** (see
below), one finale (how it ended + the transferable lesson). Longer
targets: spend the extra time on more engine lines played out on the
board, not on faster talking.

**Narration.** Plain spoken English, NO algebraic notation — write
"bishop takes g7", "knight to e4", never "Bxg7" (the TTS will spell it).
Piper speaks ~160 words/minute including pauses: budget
`words ≈ 160 × minutes`. Steal the annotated PGN's best phrases — the
narration should sound like the annotator talking, not a summary of him.
Short sentences read best AND make better subtitles (one sentence = one
subtitle).

**Shots.** Each segment has 1–4 shots. The segment's narration is split into
sentences and handed to the shots in proportion to their `weight`, and each
shot's sentences are heard while that shot is on screen (see "Sync" below).
When the automatic split puts a sentence on the wrong board, give the shots
their own `narration` strings instead of the segment one; that is exact.
- `ply`: halfmove index from the start (1.e4 = ply 1, 1...c5 = ply 2).
  Recount against the PGN — an off-by-one shows the wrong position.
- `var`: SAN moves played on top of the mainline to show an engine line
  on the board while the narration explains it. Use for every "White had
  X!!" moment — show the line, don't just say it.
- `arrows`: `from+to+color` (`c3e4g`), from==to circles a square.
  Semantics: green = the engine's idea, red = threat/refutation,
  yellow = attention ("look here"), blue = pin/geometry.
  Two arrows over the same pair of squares collide into an unreadable
  blob — use one arrow plus a circle instead. A route through an empty
  square reads fine as two arrows (`g6f5r,f5d4r`).
- `eval`: copy `eval_after_played` from the sweep row of that ply
  (`"mate"`/`"-mate"` when decided). For `var` shots use the eval the
  annotation gives for that line.
- `caption`/`note`: the move label and a ≤8-word hook ("Better: 12.Ne4!").
  On a `var` shot, caption the LINE, not its first move — by the time the
  shot settles the board is several plies past it (`"...Nd4, ...Ne2+"`).
  Never put the eval in the caption; the panel already prints it.
- `weight`: this shot's share of the segment narration (default 1). It buys
  sentences, not seconds: a shot's screen time IS the time its sentences take.
- `narration`: optional, this shot's own sentences. If ANY shot in a segment
  has one, the segment-level `narration` is ignored and every line the segment
  speaks must live on a shot. Use it whenever the wording ties to a specific
  position ("and then he takes on g5" belongs on the shot that shows it).
- `lead`: optional, seconds this shot's narration may start BEFORE its bridge
  run finishes (default 1.2). Raise it on an intro shot whose words are about
  the flip-through itself ("thirteen moves in, watch it fly past"): `"lead": 6`
  puts six seconds of replay under the narration instead of ahead of it.

Moves you don't discuss are inserted automatically as 1-second bridge
shots, so the game always plays through completely — you only storyboard
the moments worth stopping at. The top-level `"bridge_sec"` key changes
that rate: use it when the video opens by replaying a long prefix to reach
the position it discusses (0.45 turns a 25-ply intro replay into 11 s
instead of 25, which reads as a fast flip-through rather than dead air).
One uninterrupted run of bridges is also capped at `"bridge_run_max"`
(default 5 s, floor 0.3 s per move), so a 20-ply gap flips past instead of
stalling the video.

**Sync (why the narration can't drift).** Each shot is one block that takes
the SAME interval in the audio and in the video: `[its bridge moves]` then
`[its own sentences]` then `[its hold]`. Silence for the bridges is inserted
right where the bridges play, not banked up for the end of the segment, so a
sentence is always heard while its shot is on screen. Narration may start up
to 1.2 s before a bridge run ends, so the last move slides in as the narrator
introduces it, and a shot can ask for more of that with `lead`. The practical
consequence for storyboarding: **a shot's screen
time is exactly the time its sentences take** (plus `hold`), so a shot you
want held longer needs more words or more `hold`, not a bigger `weight`. Big
ply gaps no longer steal time from the shot that follows them.

**The plan pause — exactly one, in every video.** The chess-analysis skill
picks one quiet position per game and derives both sides' plans for it
(that skill's §3b, briefing in its `references/plan-pause.md`); the video
spends one segment there, and only one. Place it at the pause ply, right
after the segment covering the move before it. Four shots:

1. **the frozen position** — circle the pieces the plan is about
   (`b1b1y,c1c1y`), `hold` 2.0, and say out loud that there is no tactic
   here, only a question. Quote the think-aloud if it caught the player
   asking it.
2. **the player's plan** — route arrows for where the pieces are going,
   then a 4-6 ply `var` playing it out on the board.
3. **the opponent's plan** — same shape in red. If the two plans are about
   the same square or the same piece, say so; that is the insight.
4. **the verdict** — what the drift cost, and the crash (if there was one)
   that the plan would have made structurally impossible.

Narrate the RULES, not the move list ("the pawn never leaves d4", "knight
to c3, never a3"), and give the honesty-gate number whenever the candidate
moves were close: "five plans within a quarter of a pawn, so the move does
not matter — the plan does". This is the segment that most needs `hold`; it
is about thinking slowly. Budget ~60-70 s of narration across its shots.

**Pacing.** Dense tactical explanations read too fast at narration speed
(user feedback). Put `"hold": seconds` on the shot where the
viewer needs to digest (a fork's geometry, a mate net, the refutation
shot): it adds that much silence on that shot, while the board lingers on
it. 1.5-2.0s on the 3-5 hardest shots is the right dose; don't sprinkle
holds everywhere.

**Continuity & animation** (automatic, but storyboard with it in mind):
the position never teleports FORWARD — every forward move is animated
(the piece slides), including the auto-bridges, the moves of a `var`, and
the mainline moves replayed when returning from a `var`. Backward jumps
(entering a variation = rewinding to the branch point) are allowed and
instantaneous. Any frame off the mainline carries an orange "BRANCH ·
engine line" banner across the board top, so keep `var` lines short
(3-5 moves): every move of the line is played on screen and long lines
eat the shot's time budget.

**Narration voice.** For a self-review of the user's own game, address
the player as "you" and weave in what they said or thought at the board
(a think-aloud transcript is gold here — see the chess-analysis skill's
"Think-aloud recording" section); for a third-party game, narrate in
third person.

**Quote a note only where it belongs.** A note covers **its own ply, plus any move its own text explicitly names**
— a note at move 13 that writes out "c3, then Qh5, then e5" covers those
three moves, because that is what it is about. It covers nothing else. It
may never be produced as the reason for a decision it does not mention,
and it may never be refuted at a ply it was not written for. A segment may
quote, confirm or contradict the entries that cover the plies it is
showing, and no others. Never carry a note back to explain an earlier
decision ("your notes tell us you had already ruled that out"), and never
write "you feared", "you thought", "you believed" for a move no note
covers: the engine proves what a move was worth, it proves nothing about
what was in the player's head. Cross-references are out too, even with the
timing made explicit.

The plan-pause segment is the one place this bites, because the pause ply
is chosen by `pick_pause.py` and the planning note usually sits a ply or
two earlier. That is fine as long as the note names the moves the segment
discusses; if it does not, narrate the position and leave the note out.

This is a shipped defect, not a hypothetical: a past video took a ply-85
note, *"the king can't help much because of the series of checks"*,
presented it as the reason for the ply-83 king move, and refuted it. The
note was about a position two plies later, and the refutation was aimed at
a claim the player never made.

## 3. Generate and verify with your own eyes

```sh
.venv-chess/bin/python <this skill>/scripts/make_video.py \
    chess-games/video/storyboard-NNN.json "$PWD/chess-games/video/out-NNN.mp4"
```

The out path must be ABSOLUTE: the final ffmpeg runs with cwd set to the
storyboard's directory, so a relative path resolves to a nonexistent
subfolder and ffmpeg dies with exit 254.

Then verify — subagents and storyboards both make mistakes:
- Extract 3–4 frames (`ffmpeg -ss T -i out.mp4 -frames:v 1 f.png`) at key
  moments and LOOK at them: right position? arrows pointing where the
  narration says? caption/eval matching? no clipped text?
- **Check sync against the .srt**: take 4–5 subtitle timestamps that name a
  concrete move, pull the frame at the middle of that subtitle, and confirm
  the board is showing that move. Segment boundaries are safe by
  construction; what slips is a sentence landing on the neighbouring shot
  inside a multi-shot segment. Fix by moving the sentence into the right
  shot's own `narration`.
- **Read the .srt end to end as prose**, with the level in mind. Delete
  any sentence that proves something below it, any lesson stated a second
  time, and any "you thought/feared/ruled out" that no note at that ply
  supports. This pass is cheap and it is the one the user notices.
- Check total duration against the target; check the .srt reads cleanly.
- If a bridge sequence feels rushed when previewing, raise `BRIDGE_SEC`.

## 4. Build the HTML viewer

```sh
.venv-chess/bin/python <this skill>/scripts/make_html.py \
    chess-games/games/NNN-...-annotated.pgn chess-games/video/out-NNN.html \
    --sweep <sweep.json> --title "White vs Black — Game NNN"
```

Screenshot it headless (e.g. chromium via playwright) and check: annotations flow as a document, variations are
blue and clickable, the gauge tracks the sweep.

## 5. Deliver the package

Send the user three files together: `out-NNN.mp4`, `out-NNN.srt`,
`out-NNN.html` — video for watching, srt for reuse, HTML for digging into
the engine lines the video only touches. Summarize in chat: duration, the
2–3 beats the video highlights, and what the HTML adds. Commit the
storyboard and any tool changes (never the mp4/srt/html/voices — they are
gitignored artifacts) when in a real repo session.
