# Chess post-mortem skills for Claude Code

Claude Code skills that turn one of your chess games into a post-mortem
you can actually read: plain-language explanations of your mistakes,
checked against Stockfish, and a narrated video of the whole game.

## The video

https://github.com/user-attachments/assets/ebd443e1-aeac-41d3-a868-64d521223a9b

*6:49, English narration, subtitles.*

This is a real game of mine: a 15+10 rapid on lichess
([5KmlrdyT](https://lichess.org/5KmlrdyT)), White, Open Sicilian against a
Najdorf, around 1700. During the game I recorded myself thinking aloud, in
French, with a plain voice recorder running next to the board. After the
game I gave Claude two things: the lichess link and the mp3.

Claude transcribed the audio locally with whisper.cpp, then used the clock
times in the PGN to match each sentence to the move I was deciding at that
moment. So when the video says "at move eight you asked yourself whether
the bishop belongs on c4 or e2", that is my own question, answered with
the engine. Everything the video shows (the transcript, the Stockfish
sweep, the annotated PGN, the storyboard) is in `examples/game-010/`.

## Why this exists

A Stockfish analysis gives you numbers and lines. It is not fun to read,
and often it does not tell you *why*: -1.8 after your move, and a 12-move
variation you would never find at the board.

I realized Claude can drive Stockfish itself. It asks the engine the
questions a human would ask ("why not the move I played?", "what if Black
simply takes?"), keeps asking until the answer makes sense, and writes it
down in human terms. And since it knows what I was thinking during the
game, it can refute my actual reasoning instead of a guessed one. After
the analysis I can keep asking my own questions about any position, and
it checks them with the engine before answering.

## Is it for you?

Probably yes if:

- you play slow or rapid games and want to learn from them, not just see
  where the eval bar dropped;
- you are fine running Claude Code on your machine;
- you are willing to take notes or talk during the game (optional, but
  this is what makes the result interesting).

Probably not if you want a quick check of a blitz game. Lichess or
chess.com analysis does that in seconds.

**It takes time.** A full run (sweep, investigations, annotations, video)
takes around one hour of processing. Use it on games where you took the
time to think, not on every game you play.

**Give it your thoughts.** I strongly recommend passing your written notes
or an audio recording covering the whole game. Without them you get a good
engine explanation. With them you get a review of *your* reasoning:
which fears were justified, which plans were sound, which questions you
asked yourself and what the answer was.

**Hallucinations.** The AI can still get something wrong. Every claim is
checked against Stockfish and a verifier pass re-reads the result, so in
my experience errors are rare. If something looks off, ask Claude to
check that position with the engine.

## My workflow

1. Play a game with some time to think (15+10 rapid, or correspondence).
2. Record myself thinking aloud during the game (any phone or web voice
   recorder). For correspondence games, I write notes per move instead.
3. After the game, open Claude Code and say something like:
   "analyze this game: <lichess link>, here is my think-aloud recording:
   <path to mp3>".
4. Wait about an hour. I get an annotated PGN and a standalone HTML
   analysis board.
5. Ask for the video: "make a video of this game".
6. Read, watch, then ask questions about the positions I still do not
   understand.

## The skills

| skill | what it does |
|---|---|
| `chess-analysis` | Stockfish sweep of every move, then parallel "investigator" subagents that interrogate the engine with naive questions until every mistake is explained. Output: a layered annotated PGN, a standalone HTML analysis board, and one "plan pause" per game where both sides' plans are derived from the engine. Handles the think-aloud recording: whisper.cpp transcription, alignment to moves via the PGN clocks. |
| `chess-video` | A narrated video of the whole game (board, arrows, eval gauge, piper TTS, burned-in subtitles) built from a storyboard, plus an interactive HTML viewer. |
| `chess-play` | Play a game against Claude over PGN files, with the board rendered to PNG for vision and adversarial blunder-check subagents. No engine. |

The skills are written for Claude to read, so the SKILL.md files double as
the documentation. Start with `skills/chess-analysis/SKILL.md`.

## Install

Copy (or symlink) the skill folders into `.claude/skills/` of your project,
or into `~/.claude/skills/` for all projects:

```sh
git clone https://github.com/brumar/chess-postmortem-skills
cp -r chess-postmortem-skills/skills/* ~/.claude/skills/
```

Then ask Claude something like "analyze this game: <lichess link or PGN>"
or "make a video of game 010".

## Requirements

You do not need to set these up by hand. Claude Code can most likely
install them for you: ask it to "install the dependencies for the chess
skills" and it will read the list below and the SKILL.md files.

- Python venv with `python-chess`, `cairosvg` (analysis), plus `pillow`,
  `piper-tts` for the video. The skills assume a `.venv-chess` at the repo
  root and create it if missing.
- Stockfish. `scripts/get_stockfish.sh` uses `$STOCKFISH` or the one on
  PATH, else downloads the official Linux binary.
- For video: `ffmpeg`, and a piper voice (download command in
  `chess-video/SKILL.md`).
- Optional: [whisper.cpp](https://github.com/ggml-org/whisper.cpp) for
  think-aloud transcription.

Game files live in a `chess-games/` folder at the root of the project you
run Claude in (`games/`, `boards/`, `video/`).

## Tell Claude your level

Every comment is pitched at a reader level (`audience.level` in
`annotations.json`). For your own games, tell Claude your level once and
make it stick, for example in your `CLAUDE.md`:

```
My lichess handle is <handle>. Write chess analysis for a 1800 player.
```

Without it, the skill uses the PGN's Elo for the reviewed side and asks
when that is missing or provisional.

## Example files: game 010

| file | stage |
|---|---|
| `games/010-...pgn` | input, as exported from lichess |
| `games/010-transcript-fr.md` | think-aloud transcript, whisper.cpp, clock-aligned per ply |
| `games/010-...-sweep.json` | per-ply Stockfish evals (depth 22) |
| `games/010-frag-*.json` | annotation fragments returned by each investigator / the plan pause / the brief-comment pass |
| `games/010-analysis-*.json` | engine lines each investigator discovered (`query.py --log` sidecars) |
| `games/010-assemble.py`, `010-annotations.json` | fragments merged into the build spec |
| `games/010-...-annotated.pgn` | the deliverable of stage 2 |
| `games/010-...-viewer.html` | standalone analysis board, open it in a browser |
| `video/storyboard-010.json` | storyboard for stage 3 |
| `video/out-010.mp4`, `.srt`, `.html` | the narrated video (6:49), subtitles, and annotation viewer |

To regenerate the video, download the piper voice into
`examples/game-010/video/voices/` and run `make_video.py` on the storyboard.

## License

MIT, except the vendored `chess.js` (BSD 2-Clause) and the cburnett piece
set (CC BY-SA / GFDL). See `LICENSE`.
