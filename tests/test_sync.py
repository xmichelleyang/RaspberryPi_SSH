"""Sync tests with a mocked SSH client."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from raspberrypi_ssh.sync import sync_videos


def _make_mock_client(remote_files=None):
    client = MagicMock()
    client.list_remote_dir.return_value = remote_files or []
    client.mkdir.return_value = None
    return client


def _make_local_files(tmp_path: Path, names_sizes: list[tuple[str, int]]) -> Path:
    source = tmp_path / "videos"
    source.mkdir()
    for name, size in names_sizes:
        f = source / name
        f.write_bytes(b"x" * size)
    return source


class TestSyncVideos:
    def test_transfers_new_file(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 100)])
        client = _make_mock_client(remote_files=[])
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        client.upload_file.assert_called_once()
        assert transferred == 1
        assert failed == 0

    def test_skips_file_with_matching_name_and_size(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 100)])
        client = _make_mock_client(remote_files=[{"name": "movie.mkv", "size": 100}])
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        client.upload_file.assert_not_called()
        assert transferred == 0
        assert failed == 0

    def test_transfers_file_with_different_size(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 200)])
        client = _make_mock_client(remote_files=[{"name": "movie.mkv", "size": 100}])
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        client.upload_file.assert_called_once()
        assert transferred == 1

    def test_retries_once_on_failure(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 100)])
        client = _make_mock_client()
        client.upload_file.side_effect = [OSError("connection reset"), None]
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        assert client.upload_file.call_count == 2
        assert transferred == 1
        assert failed == 0

    def test_fails_after_two_attempts(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 100)])
        client = _make_mock_client()
        client.upload_file.side_effect = OSError("always fails")
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        assert client.upload_file.call_count == 2
        assert failed == 1
        assert transferred == 0

    def test_dry_run_does_not_upload(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 100)])
        client = _make_mock_client()
        sync_videos(client, source, "/remote", [".mkv"], dry_run=True)
        client.upload_file.assert_not_called()

    def test_skips_non_matching_extensions(self, tmp_path):
        source = _make_local_files(tmp_path, [("movie.mkv", 100), ("doc.pdf", 50)])
        client = _make_mock_client()
        sync_videos(client, source, "/remote", [".mkv"])
        # Only the mkv should be transferred
        assert client.upload_file.call_count == 1

    def test_empty_source_dir(self, tmp_path):
        source = tmp_path / "videos"
        source.mkdir()
        client = _make_mock_client()
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        client.upload_file.assert_not_called()
        assert transferred == 0
        assert failed == 0

    def test_multiple_files_independent_failures(self, tmp_path):
        source = _make_local_files(tmp_path, [("a.mkv", 10), ("b.mkv", 10)])
        client = _make_mock_client()
        # First file always fails, second succeeds
        client.upload_file.side_effect = [
            OSError("fail"), OSError("fail"),  # a.mkv: 2 attempts
            None,                               # b.mkv: succeeds
        ]
        transferred, failed = sync_videos(client, source, "/remote", [".mkv"])
        assert transferred == 1
        assert failed == 1
