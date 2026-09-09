#!/usr/bin/env python3
"""
pull_changed.py - pull only the pages that changed on the wiki since the last
pull, without trampling local edits.

pull.py rewrites every page it lists, whether or not it changed, and whether
or not the local file carries an edit that was never pushed. This does three
things differently:

  1. It asks the wiki for every page's CURRENT revision id in one sweep
     (about ten calls per namespace) and fetches only pages whose revid
     differs from the one recorded in .state.json, plus pages it has never
     seen.
  2. Before overwriting a file, it compares the local copy with the last
     committed version (git HEAD). If they differ, the local file carries an
     edit of its own: that copy is saved under pages_backup/<same path> and
     the page is listed at the end so the two versions can be reconciled.
  3. Pages that exist in .state.json but no longer on the wiki are reported,
     not deleted.

Usage:
    python pull_changed.py            # every namespace in pull.NS_NAMES
    python pull_changed.py --ns 0     # one namespace
"""
import argparse
import subprocess
import sys
from pathlib import Path

import pull as P

BACKUP = Path("pages_backup")


def latest_revids(s, namespace):
    """{title: revid} for every page in the namespace, from the wiki."""
    out = {}
    cont = {}
    while True:
        params = {
            "action": "query", "generator": "allpages", "gapnamespace": namespace,
            "gaplimit": "max", "prop": "revisions", "rvprop": "ids", "format": "json",
        }
        params.update(cont)
        r = s.get(P.API, params=params).json()
        for page in r.get("query", {}).get("pages", {}).values():
            revs = page.get("revisions")
            if revs:
                out[page["title"]] = revs[0]["revid"]
        if "continue" in r:
            cont = r["continue"]
        else:
            return out


def head_version(path):
    """The file as last committed, or None if git has no copy."""
    try:
        r = subprocess.run(["git", "show", f"HEAD:{path.as_posix()}"], capture_output=True)
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", errors="replace")
    except OSError:
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ns", type=int, default=None)
    args = ap.parse_args()
    namespaces = [args.ns] if args.ns is not None else list(P.NS_NAMES)
    s = P.session_login()
    state = P.load_state()
    updated, new, conflicts, gone = [], [], [], []
    for ns in namespaces:
        remote = latest_revids(s, ns)
        folder = P.NS_NAMES.get(ns, f"NS_{ns}")
        known = {t for t, v in state.items() if Path(v["path"]).parts[1:2] == (folder,)}
        for title in sorted(known - set(remote)):
            gone.append(title)
        todo = [t for t, rev in remote.items() if t not in state or state[t]["revid"] != rev]
        print(f"ns {ns} ({folder}): {len(remote)} pages on the wiki, {len(todo)} changed or new")
        for title in sorted(todo):
            content, revid = P.fetch_page(s, title)
            if content is None:
                continue
            stored = state.get(title)
            if stored:
                path = Path(stored["path"])
                if path.exists():
                    local = path.read_text(encoding="utf-8")
                    head = head_version(path)
                    if local != content and (head is None or local != head):
                        bp = BACKUP / path.relative_to(P.PAGES_DIR)
                        bp.parent.mkdir(parents=True, exist_ok=True)
                        bp.write_text(local, encoding="utf-8")
                        conflicts.append((title, str(path), str(bp)))
                updated.append(title)
            else:
                new.append(title)
            P.write_page(title, ns, content, revid, state)
        P.save_state(state)
    print(f"\nupdated {len(updated)}, new {len(new)}, gone from the wiki {len(gone)}, "
          f"local edits backed up {len(conflicts)}")
    if conflicts:
        print("\nLOCAL EDITS OVERWRITTEN (your version is in pages_backup/):")
        for title, path, bp in conflicts:
            print(f"  {title}  ->  {bp}")
    if gone:
        print("\nIN .state.json BUT NO LONGER ON THE WIKI (files kept):")
        for t in gone:
            print("  " + t)


if __name__ == "__main__":
    main()
