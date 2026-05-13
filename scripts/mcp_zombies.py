#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Cross-platform zombie odoo-mcp process cleanup.

Zombie = parent process (Claude Code) already dead. Safe to kill.
In-use = parent alive. DO NOT kill, another Claude session uses it.

Usage:
  uv run scripts/mcp_zombies.py            # list only
  uv run scripts/mcp_zombies.py --kill     # kill zombies
  uv run scripts/mcp_zombies.py --kill --quiet
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import signal
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VENV_DIR = (SCRIPT_DIR / ".." / "server" / ".venv").resolve()


def _list_procs_windows() -> list[dict]:
    cmd = [
        "wmic", "process", "get",
        "ProcessId,ParentProcessId,Name,CommandLine,ExecutablePath",
        "/format:csv",
    ]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=8
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(out.strip()))
    for r in reader:
        try:
            pid = int((r.get("ProcessId") or "0").strip() or 0)
            ppid = int((r.get("ParentProcessId") or "0").strip() or 0)
        except ValueError:
            continue
        if pid == 0:
            continue
        rows.append({
            "pid": pid,
            "ppid": ppid,
            "name": (r.get("Name") or "").strip(),
            "cmdline": (r.get("CommandLine") or "").strip(),
            "exe": (r.get("ExecutablePath") or "").strip(),
        })
    return rows


def _list_procs_posix() -> list[dict]:
    cmd = ["ps", "-ax", "-o", "pid=,ppid=,comm=,args="]
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=8
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    rows: list[dict] = []
    for line in out.splitlines():
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        pid_s, ppid_s, comm, args = parts
        try:
            rows.append({
                "pid": int(pid_s),
                "ppid": int(ppid_s),
                "name": comm,
                "cmdline": args,
                "exe": "",
            })
        except ValueError:
            continue
    return rows


def list_procs() -> list[dict]:
    if sys.platform.startswith("win"):
        return _list_procs_windows()
    return _list_procs_posix()


def is_mcp(proc: dict, venv_str: str) -> bool:
    name = proc["name"].lower()
    cmd = proc["cmdline"].lower()
    exe = proc["exe"].lower()
    venv = venv_str.lower()

    if name in ("odoo-mcp", "odoo-mcp.exe"):
        return True
    if "odoo_mcp_server" in cmd or "odoo-mcp" in cmd:
        return True
    if name in ("python", "python.exe", "python3") and venv and venv in exe:
        return True
    if name in ("uv", "uv.exe") and venv and venv in cmd:
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Clean zombie odoo-mcp processes")
    ap.add_argument("--kill", action="store_true", help="Kill zombies (parent dead)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    venv_str = str(VENV_DIR) if VENV_DIR.exists() else ""

    procs = list_procs()
    if not procs:
        if not args.quiet:
            print("Could not enumerate processes (ps/wmic unavailable).", file=sys.stderr)
        return 0

    by_pid = {p["pid"]: p for p in procs}
    mcp = [p for p in procs if is_mcp(p, venv_str)]
    if not mcp:
        if not args.quiet:
            print("No odoo-mcp processes found.")
        return 0

    rows = []
    for p in mcp:
        parent_alive = p["ppid"] in by_pid
        status = "IN-USE" if parent_alive else "ZOMBIE"
        rows.append((status, p["pid"], p["name"], p["ppid"]))

    if not args.quiet:
        print(f"{'Status':<8} {'PID':>6} {'PPID':>6}  Name")
        for s, pid, name, ppid in rows:
            print(f"{s:<8} {pid:>6} {ppid:>6}  {name}")

    if args.kill:
        killed = 0
        for s, pid, name, _ppid in rows:
            if s != "ZOMBIE":
                continue
            try:
                os.kill(pid, signal.SIGTERM)
                killed += 1
                if not args.quiet:
                    print(f"killed PID={pid} ({name})")
            except (OSError, ProcessLookupError) as e:
                if not args.quiet:
                    print(f"failed to kill PID={pid}: {e}", file=sys.stderr)
        if not args.quiet and killed == 0 and any(s == "ZOMBIE" for s, *_ in rows) is False:
            print("No zombies to kill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
