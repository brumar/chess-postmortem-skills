#!/bin/sh
# Fetch a Stockfish binary if none is available. Prints the binary path.
# Respects $STOCKFISH if already set and executable.
set -e
if [ -n "$STOCKFISH" ] && [ -x "$STOCKFISH" ]; then echo "$STOCKFISH"; exit 0; fi
if command -v stockfish >/dev/null 2>&1; then command -v stockfish; exit 0; fi
DIR="${1:-/tmp/stockfish-dl}"
BIN="$DIR/stockfish/stockfish-ubuntu-x86-64-avx2"
if [ -x "$BIN" ]; then echo "$BIN"; exit 0; fi
mkdir -p "$DIR" && cd "$DIR"
curl -sSL -o sf.tar https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-ubuntu-x86-64-avx2.tar
tar xf sf.tar && chmod +x "$BIN"
echo "$BIN"
