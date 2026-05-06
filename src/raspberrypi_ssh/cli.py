"""Entry point: rpi-sync command."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config
from .rename import apply_renames, propose_renames
from .ssh_client import RpiSSHClient, SSHConnectionError
from .sync import sync_videos

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(cfg: dict) -> RpiSSHClient:
    pi = cfg["pi"]
    return RpiSSHClient(
        host=pi["host"],
        user=pi["user"],
        port=pi["port"],
        ssh_key=pi["ssh_key"],
    )


def _print_rename_table(proposals: list) -> None:
    orig_w = max((len(p.original) for p in proposals), default=40)
    new_w = max((len(p.renamed) for p in proposals), default=40)
    orig_w = max(orig_w, 8)
    new_w = max(new_w, 7)
    sep = f"{'─' * (orig_w + 2)}┼{'─' * (new_w + 2)}"
    header = f" {'Original':<{orig_w}} │ {'Renamed':<{new_w}} "
    print(f"┌{sep.replace('┼', '┬')}┐")
    print(f"│{header}│")
    print(f"├{sep}┤")
    for p in proposals:
        mark = " ⚠" if p.needs_review else ""
        print(f"│ {p.original:<{orig_w}} │ {p.renamed:<{new_w}}{mark} │")
    print(f"└{sep.replace('┼', '┴')}┘")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_rename(args: argparse.Namespace, cfg: dict) -> int:
    source_dir = Path(cfg["local"]["source_dir"]).expanduser()
    if not source_dir.exists():
        print(f"Source directory not found: {source_dir}", file=sys.stderr)
        return 1

    exts = cfg["rename"]["video_extensions"]
    files: list[Path] = []
    for ext in exts:
        files.extend(source_dir.glob(f"*{ext}"))
    files = sorted(files)

    if not files:
        print("No video files found.")
        return 0

    proposals = propose_renames(files)
    unchanged = [p for p in proposals if p.original == p.renamed]
    changes = [p for p in proposals if p.original != p.renamed]

    if not changes:
        print("All filenames are already clean.")
        return 0

    print(f"\nProposed renames ({'dry-run' if not args.apply else 'will apply'}):")
    _print_rename_table(changes)

    if not args.apply:
        print("\nRun with --apply to rename on disk.")
        return 0

    # Confirmation prompt when applying
    answer = input(f"\nRename {len(changes)} file(s) on disk? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        return 0

    apply_renames(files, proposals)
    print(f"✓ Renamed {len(changes)} file(s).")
    return 0


def cmd_push(args: argparse.Namespace, cfg: dict) -> int:
    source_dir = Path(cfg["local"]["source_dir"]).expanduser()
    remote_dir = cfg["pi"]["target_dir"]
    exts = cfg["rename"]["video_extensions"]

    if args.rename:
        # Run rename first (apply mode with prompt)
        class _FakeArgs:
            apply = True

        ret = cmd_rename(_FakeArgs(), cfg)
        if ret != 0:
            return ret

    pi = cfg["pi"]
    print(f"Connecting to {pi['host']}:{pi['port']} as {pi['user']}...")
    try:
        with _make_client(cfg) as client:
            transferred, failed = sync_videos(
                client, source_dir, remote_dir, exts, dry_run=args.dry_run
            )
    except SSHConnectionError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1

    if not args.dry_run:
        if failed:
            print(f"⚠ {transferred} transferred, {failed} failed.", file=sys.stderr)
            return 1
        print(f"✓ {transferred} file(s) transferred successfully.")
    return 0


def cmd_setup_ssh(args: argparse.Namespace, cfg: dict) -> int:
    import os
    import subprocess

    key_path = Path(cfg["pi"]["ssh_key"]).expanduser()
    if not key_path.exists():
        print(f"Generating ED25519 key at {key_path} ...")
        key_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-t", "ed25519", "-f", str(key_path), "-N", ""], check=True)
    else:
        print(f"Key already exists: {key_path}")

    pi = cfg["pi"]
    target = f"{pi['user']}@{pi['host']}"
    print(f"Installing public key on {target} (you may be prompted for the Pi password) ...")
    subprocess.run(["ssh-copy-id", "-i", str(key_path) + ".pub", "-p", str(pi["port"]), target])
    print("Done.  Test with: ssh -i", key_path, target)
    return 0


def cmd_ls(args: argparse.Namespace, cfg: dict) -> int:
    pi = cfg["pi"]
    print(f"Files on {pi['host']}:{pi['target_dir']}")
    try:
        with _make_client(cfg) as client:
            entries = client.list_remote_dir(pi["target_dir"])
    except SSHConnectionError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        return 1

    if not entries:
        print("  (empty)")
    for e in entries:
        size_mb = e["size"] / 1_048_576
        print(f"  {e['name']:<60} {size_mb:>8.1f} MB")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rpi-sync",
        description="Sync and rename videos to a Raspberry Pi over SSH.",
    )
    parser.add_argument("--config", type=Path, help="Path to config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    # rename
    p_rename = sub.add_parser("rename", help="Intelligently rename files in videos_to_send/")
    p_rename.add_argument(
        "--apply", action="store_true", help="Apply renames (default is dry-run)"
    )

    # push
    p_push = sub.add_parser("push", help="Transfer videos to the Pi")
    p_push.add_argument("--dry-run", action="store_true", help="Show what would be transferred")
    p_push.add_argument("--rename", action="store_true", help="Run rename pass before transfer")

    # setup-ssh
    sub.add_parser("setup-ssh", help="Interactive SSH key setup helper")

    # ls
    sub.add_parser("ls", help="List files on the Pi")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    cfg = load_config(args.config if hasattr(args, "config") else None)

    handlers = {
        "rename": cmd_rename,
        "push": cmd_push,
        "setup-ssh": cmd_setup_ssh,
        "ls": cmd_ls,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args, cfg) or 0)


if __name__ == "__main__":
    main()
