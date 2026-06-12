"""Project launcher entrypoint.

Run this file directly from PyCharm to start the local development stack:

- FastAPI backend: http://127.0.0.1:8011/docs
- Vue frontend:   http://127.0.0.1:5173/work-orders

PyCharm: choose run configuration "PyCharm Start Full Stack", or right-click
this file and select Run 'main'.

The real startup logic lives in scripts/pycharm_start.py so command-line and
PyCharm startup share one implementation.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import pycharm_start

MYSQL_DATABASE = pycharm_start.DEFAULT_DB_NAME
RESET_DATABASE_ON_START = False
main = pycharm_start.main


if __name__ == "__main__":
    raise SystemExit(main())
