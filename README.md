# Chess post-mortem skills for Claude Code

Three [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills)
that turn a chess game into a post-mortem a human can learn from:

| skill | what it does |
|---|---|
| `chess-analysis` | Stockfish sweep of every move, then parallel "investigator" subagents that interrogate the engine with naive questions ("why not the move I played?", "why not the natural reply inside this line?") until every mistake is explained. Output: a layered annotated PGN, a standalone HTML analysis board, and one "plan pause" per game where both sides' plans are derived from the engine. Optional: a think-aloud recording of the player, transcribed with whisper.cpp and aligned to the moves via the PGN clocks, so annotations refute what the player actually believed. |
| `chess-video` | Stage 3. A narrated video of the whole game (board, arrows, eval gauge, piper TTS, burned-in subtitles) built from a storyboard JSON, plus an interactive HTML viewer. |
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

## Example: game 010

`examples/game-010/` is a complete run on a 15+10 rapid Najdorf
(lichess [5KmlrdyT](https://lichess.org/5KmlrdyT)), including a French
think-aloud recording aligned to the moves.

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
| `video/storyboard-010.json` | hand-authored storyboard for stage 3 |
| `video/out-010.mp4`, `.srt`, `.html` | the narrated video (6:49), subtitles, and annotation viewer |

To regenerate the video, download the piper voice into
`examples/game-010/video/voices/` and run `make_video.py` on the storyboard.

## License

MIT, except the vendored `chess.js` (BSD 2-Clause) and the cburnett piece
set (CC BY-SA / GFDL). See `LICENSE`.
