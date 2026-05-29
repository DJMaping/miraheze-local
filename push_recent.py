"""
push_recent.py — Push only files modified since the last time you ran this.

Tracks the last successful run in .last_push.json. Walks every tracked file in
.state.json, picks the ones whose mtime is newer than that timestamp, and
delegates the actual upload to push.py. On success, updates the timestamp so
the next run only sees newer changes.

Run via: double-click push_recent.bat (or `python push_recent.py`).
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(".state.json")
LAST_PUSH_FILE = Path(".last_push.json")


def load_last_push() -> float:
    if not LAST_PUSH_FILE.exists():
        return 0.0
    data = json.loads(LAST_PUSH_FILE.read_text(encoding="utf-8"))
    return float(data.get("timestamp", 0.0))


def save_last_push(ts: float) -> None:
    data = {
        "timestamp": ts,
        "iso": datetime.fromtimestamp(ts).isoformat(timespec="seconds"),
    }
    LAST_PUSH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def fmt(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    if not STATE_FILE.exists():
        print("ERROR: .state.json not found. Run pull.py first.")
        return 1

    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    last_push = load_last_push()
    if last_push:
        print(f"Last push: {fmt(last_push)}")
    else:
        print("Last push: never — will push every locally-modified file.")

    candidates = []
    for title, info in state.items():
        fp = Path(info["path"])
        if not fp.exists():
            continue
        mtime = fp.stat().st_mtime
        if mtime > last_push:
            candidates.append((fp, title, mtime))

    if not candidates:
        print("\nNo files modified since last push. Nothing to do.")
        return 0

    candidates.sort(key=lambda x: x[2])
    print(f"\n{len(candidates)} file(s) modified since last push:")
    for fp, title, mtime in candidates:
        print(f"  {fmt(mtime)}  {title}")

    # Stamp the start time BEFORE pushing so that any file edited mid-push
    # still gets picked up on the next run.
    start_ts = time.time()

    files_arg = [str(fp) for fp, _, _ in candidates]
    cmd = [sys.executable, "push.py", *files_arg]
    print(f"\n--- Running push.py ---")
    result = subprocess.run(cmd)

    if result.returncode == 0:
        save_last_push(start_ts)
        print(f"\nDone. Last push timestamp updated to {fmt(start_ts)}.")
    else:
        print(f"\npush.py exited with code {result.returncode}. Timestamp NOT updated.")

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
