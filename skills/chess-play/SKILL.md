---
name: chess-play
description: Play a chess game against the user over PGN files with the board rendered to images that Claude reads with vision. Use this whenever the user wants to play chess, sends a chess move in any notation (e4, Cf3, Nf3, "knight takes", O-O...), asks to continue an existing game in chess-games/, or says things like "your move", "lets play", "new game". Also use it mid-conversation when a lone chess move arrives — that IS the user playing. Claude plays on its own reasoning, with adversarial blunder-check subagents but NO chess engine.
---

# Playing chess over PGN + rendered boards

You are playing a real game against the user. State lives in PGN files; you
perceive the board by rendering it to PNG and reading the image with vision.
You think with subagents, never with an engine.

## Ground rules

- **No engine.** Never run Stockfish or any engine to choose or check *your*
  moves during play, unless the user explicitly invites it. The game is
  Claude-vs-human on wits. (Post-game analysis is the `chess-analysis`
  skill's job.)
- **PGN is written in English SAN** (Nf3, Bb4, O-O). The user may type moves
  in any language or style — French (C=Cavalier/knight, F=Fou/bishop,
  D=Dame/queen, T=Tour/rook, R=Roi/king), lowercase, "Cx" for an obvious
  capture, "takes on e5" — translate silently, and if a move is genuinely
  ambiguous (two knights can reach the square), ask.
- **Keep chat minimal by default**: your move, the board image, nothing
  else. Put your analysis in the game's notes file, not the conversation.
  If this is a first game and the user seems to want commentary, mirror
  their energy — but the moment they ask for quiet, all thinking goes to
  the notes file only.

## Setup (once per repo/machine)

Game data lives in `chess-games/` at the repo root (create it if missing:
`games/`, `boards/`, `notes/` subdirs). Rendering needs python-chess +
cairosvg in a venv:

```sh
python3 -m venv .venv-chess && .venv-chess/bin/pip install python-chess cairosvg
```

(If the system pip can build wheels, a venv at the repo root named
`.venv-chess` is the convention; gitignore it.) Copy `scripts/render.py`
from this skill into `chess-games/` if it is not already there.

## The per-move loop

For every half-move, in order:

1. **Record the user's move**: append to `games/NNN-<white>-vs-<black>.pgn`
   (create with proper headers on game 1 / new game). Run
   `render.py games/<game>.pgn` — it validates legality (an illegal SAN
   fails loudly; that once caught a hallucinated Qf8), prints the move
   list, FEN and side to move, and writes `boards/<game>.png`.
2. **Look at the board.** Read the PNG. Confirm the position matches what
   you believe — squares, piece counts, the highlighted last move. If the
   image surprises you, the PGN or your mental model is wrong; fix before
   thinking.
3. **Think, then have your thinking attacked.** Choose 1–2 candidate moves
   yourself, writing your reasoning to `notes/NNN-claude-thoughts.md`.
   Then spawn blunder-check subagents (below) on your top candidate.
   This step exists because game 001 was lost to self-confirmation: the
   played move was "audited" only along the lines the player was already
   looking at.
4. **Record your reply**, re-render, look at the image again, update the
   notes file.
5. **Commit and push** (when playing inside a git repo and this is a real
   game, not a test): one commit per full move, message like
   `Game 001: 12. Bf4 Bb4`.
6. **Send the board** image to the user with a one-line caption
   ("After 12. Bf4 Bb4 — your move"). Your chat message: the move in the
   user's notation style, plus anything they asked for — no unrequested
   hints or analysis.

## Blunder-check subagents (mandatory before every one of your moves)

Spawn **two parallel subagents** with the Agent tool, both engine-free.
Give each: the current FEN, the full move list, your candidate move, and
the instructions file `references/referee.md` (tell them to read it).
Their jobs differ:

- **Referee A — refute the candidate.** Adversarial: "Black up to now
  intends `<move>`. Find the refutation. Assume it loses; prove it."
- **Referee B — independent candidates.** Gets the position but NOT your
  candidate: "propose the two best moves with lines". Divergence from your
  choice is information, not a veto.

If A finds a concrete refutation you can verify (replay the line
yourself — subagents also hallucinate), pick a different move and re-check
it. If B proposes something clearly stronger, adopt or note why not.
For genuinely forced moves (only legal recapture, forced check response)
and for well-known book moves in the first ~6 moves of mainstream openings,
one referee or none is fine — don't ritualize; save the full protocol for
positions where a blunder is actually possible.

If the Agent tool is unavailable in your context, run the referee protocol
yourself, inline and explicitly: write the Referee A refutation attempt in
the notes file *as if you were a different person*, checklist and all,
before committing to the move. The posture matters more than the process
isolation.

## Multiple games & resuming

One PGN per game, numbered (`001-...`, `002-...`). "Resume" = read the
PGN, render, look, continue the loop. The notes file is your memory
between sessions — keep a running plan section and a "standing lessons"
section (e.g. game 001's: *for every candidate move, list the lines the
moving piece OPENS, not just the squares it attacks*).

## Endgame conditions

`render.py` prints game-over states. On checkmate/stalemate/draw, update
the PGN `Result` header and the final `*`, announce the result, and offer
a `chess-analysis` post-mortem.
