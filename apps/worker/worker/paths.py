from __future__ import annotations

import sys
from pathlib import Path

# Ensure apps/api, apps/worker, and root are on sys.path
API_ROOT = Path(__file__).resolve().parents[2] / "api"
WORKER_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]

for p in [str(API_ROOT), str(WORKER_ROOT), str(REPO_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)
