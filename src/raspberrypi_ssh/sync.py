"""Diff local vs remote, transfer missing files."""

from __future__ import annotations

import logging
from pathlib import Path

from tqdm import tqdm

from .ssh_client import RpiSSHClient

logger = logging.getLogger(__name__)


def _get_local_files(source_dir: Path, extensions: list[str]) -> list[Path]:
    files = []
    for ext in extensions:
        files.extend(source_dir.glob(f"*{ext}"))
    return sorted(files)


def sync_videos(
    client: RpiSSHClient,
    source_dir: Path,
    remote_dir: str,
    extensions: list[str],
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Sync videos from *source_dir* to *remote_dir* on the Pi.

    Returns (transferred, failed) counts.
    """
    client.mkdir(remote_dir)
    remote_files = {f["name"]: f["size"] for f in client.list_remote_dir(remote_dir)}
    local_files = _get_local_files(source_dir, extensions)

    if not local_files:
        logger.info("No video files found in %s", source_dir)
        return 0, 0

    to_transfer = []
    for lf in local_files:
        local_size = lf.stat().st_size
        if lf.name in remote_files and remote_files[lf.name] == local_size:
            logger.info("Skipping %s (already on Pi)", lf.name)
        else:
            to_transfer.append(lf)

    if dry_run:
        print(f"Would transfer {len(to_transfer)} file(s):")
        for f in to_transfer:
            print(f"  {f.name}  ({f.stat().st_size:,} bytes)")
        return 0, 0

    transferred = 0
    failed = 0

    for idx, lf in enumerate(to_transfer, 1):
        label = f"[{idx}/{len(to_transfer)}] {lf.name}"
        with tqdm(
            total=lf.stat().st_size,
            unit="B",
            unit_scale=True,
            desc=label,
            leave=True,
        ) as bar:
            last_sent = 0

            def _progress(filename: str, size: int, sent: int) -> None:
                nonlocal last_sent
                bar.update(sent - last_sent)
                last_sent = sent

            success = False
            for attempt in range(1, 3):  # try twice
                try:
                    client.upload_file(lf, remote_dir, _progress)
                    success = True
                    break
                except Exception as exc:
                    logger.warning("Attempt %d failed for %s: %s", attempt, lf.name, exc)
                    bar.clear()

            if success:
                transferred += 1
            else:
                logger.error("Failed to transfer %s after 2 attempts", lf.name)
                failed += 1

    return transferred, failed
