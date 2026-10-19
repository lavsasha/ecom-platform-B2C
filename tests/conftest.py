from __future__ import annotations

import sys
from pathlib import Path

# Repo root on path for `tests.support` imports when pytest loads nested conftests.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
LIBS = ROOT / "libs"
if str(LIBS) not in sys.path:
    sys.path.insert(0, str(LIBS))
