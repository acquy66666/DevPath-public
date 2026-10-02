"""Command-line scripts, run as `python -m scripts.<name>`.

`-m` imports this package before the script itself, which makes it the one
place to say something about every script: SQL echo is switched off here.

The dev stack runs with DEBUG=true, and `app/core/db.py` turns that into an
engine that logs every statement -- useful in the API server's log, useless in
a script's output. On a blank database `scripts.seed_sales` printed 9,495 lines
and `scripts.seed_study` 34,169, nearly all of them SQL, with the one line that
says what happened somewhere in the middle (docs/report/assets/phase-6/
fresh-machine.txt). The API process never imports this package, so its echo is
untouched.
"""

from app.core.db import engine

# `echo` is a live property: setting it re-configures the engine's logger, so
# this holds even though the engine was created on the import above.
engine.echo = False
