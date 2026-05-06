"""Paramiko-based SSH/SCP wrapper."""

from __future__ import annotations

import logging
import os
import stat
from pathlib import Path, PurePosixPath
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
        client.load_system_host_keys()
        # RejectPolicy: refuse connections to hosts not in known_hosts.
        # Run `rpi-sync setup-ssh` to add your Pi's host key first.
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
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
        except paramiko.SSHException as exc:
            if "not found in known_hosts" in str(exc) or "Unknown server" in str(exc):
                raise SSHConnectionError(
                    f"Host key for {self.host} not found in known_hosts. "
                    "Run `rpi-sync setup-ssh` to add it."
                ) from exc
            raise SSHConnectionError(f"Cannot connect to {self.host}:{self.port} — {exc}") from exc
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
        """Return list of {name, size} dicts for regular files in *remote_dir*."""
        sftp = self._ssh().open_sftp()
        try:
            try:
                attrs = sftp.listdir_attr(remote_dir)
            except FileNotFoundError:
                return []
            return [
                {"name": a.filename, "size": a.st_size}
                for a in attrs
                if stat.S_ISREG(a.st_mode or 0)
            ]
        finally:
            sftp.close()

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
        """Create *remote_dir* and all parent directories on the Pi."""
        sftp = self._ssh().open_sftp()
        try:
            parts = PurePosixPath(remote_dir).parts
            current = PurePosixPath(parts[0])
            for part in parts[1:]:
                current = current / part
                try:
                    sftp.mkdir(str(current))
                except OSError:
                    pass  # directory already exists
        finally:
            sftp.close()
