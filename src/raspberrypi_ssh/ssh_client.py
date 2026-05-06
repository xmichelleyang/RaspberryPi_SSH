"""Paramiko-based SSH/SCP wrapper."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable

import paramiko
from scp import SCPClient

logger = logging.getLogger(__name__)


class SSHConnectionError(RuntimeError):
    pass


class RpiSSHClient:
    """Thin wrapper around paramiko + scp."""

    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        ssh_key: str | None = None,
    ) -> None:
        self.host = host
        self.user = user
        self.port = port
        self.ssh_key = ssh_key or os.path.expanduser("~/.ssh/id_ed25519")
        self._client: paramiko.SSHClient | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=self.host,
                username=self.user,
                port=self.port,
                key_filename=self.ssh_key,
                look_for_keys=False,
                allow_agent=False,
            )
        except paramiko.AuthenticationException as exc:
            raise SSHConnectionError(f"Authentication failed for {self.user}@{self.host}") from exc
        except Exception as exc:
            raise SSHConnectionError(f"Cannot connect to {self.host}:{self.port} — {exc}") from exc
        self._client = client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "RpiSSHClient":
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Remote operations
    # ------------------------------------------------------------------

    def _ssh(self) -> paramiko.SSHClient:
        if self._client is None:
            raise SSHConnectionError("Not connected — call connect() first.")
        return self._client

    def run(self, command: str) -> tuple[str, str]:
        """Run *command* remotely; return (stdout, stderr)."""
        _, stdout, stderr = self._ssh().exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

    def list_remote_dir(self, remote_dir: str) -> list[dict]:
        """Return list of {name, size} dicts for files in *remote_dir*."""
        out, _ = self.run(f"ls -l {remote_dir} 2>/dev/null || true")
        entries = []
        for line in out.splitlines():
            parts = line.split()
            # -rw-r--r-- 1 pi pi 1234567 Jan 1 12:00 filename.mkv
            if len(parts) >= 9 and parts[0].startswith("-"):
                try:
                    entries.append({"name": parts[8], "size": int(parts[4])})
                except (IndexError, ValueError):
                    continue
        return entries

    def upload_file(
        self,
        local_path: Path,
        remote_dir: str,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> None:
        """Upload *local_path* into *remote_dir* on the Pi."""
        def _progress(filename: bytes, size: int, sent: int) -> None:
            if progress_callback:
                progress_callback(filename.decode(errors="replace"), size, sent)

        with SCPClient(self._ssh().get_transport(), progress=_progress) as scp:
            scp.put(str(local_path), remote_path=remote_dir)

    def mkdir(self, remote_dir: str) -> None:
        self.run(f"mkdir -p {remote_dir}")
