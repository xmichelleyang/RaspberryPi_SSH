"""Unit tests for rename.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from raspberrypi_ssh.rename import (
    RenameProposal,
    _clean_stem,
    _is_gibberish,
    propose_renames,
)


# ---------------------------------------------------------------------------
# _clean_stem tests
# ---------------------------------------------------------------------------


class TestCleanStem:
    def test_dots_as_spaces(self):
        assert _clean_stem("The.Dark.Knight.2008") == "The Dark Knight 2008"

    def test_underscores_as_spaces(self):
        assert _clean_stem("my_video_file") == "my video file"

    def test_strips_resolution(self):
        result = _clean_stem("Movie.Name.1080p.BluRay")
        assert "1080p" not in result
        assert "BluRay" not in result

    def test_strips_codec(self):
        result = _clean_stem("Film.x264.HEVC")
        assert "x264" not in result
        assert "HEVC" not in result

    def test_strips_brackets(self):
        result = _clean_stem("Movie [YTS.MX]")
        assert "[YTS.MX]" not in result

    def test_strips_parens(self):
        result = _clean_stem("Movie (1080p)")
        assert "(1080p)" not in result

    def test_collapse_whitespace(self):
        result = _clean_stem("Movie   Name")
        assert "  " not in result

    def test_strips_scene_group(self):
        result = _clean_stem("The.Dark.Knight.2008.1080p.BluRay.x264-GROUP")
        assert "GROUP" not in result


# ---------------------------------------------------------------------------
# _is_gibberish tests
# ---------------------------------------------------------------------------


class TestIsGibberish:
    def test_camera_filename(self):
        assert _is_gibberish("VID_20240301_142233") is True

    def test_hash_like(self):
        assert _is_gibberish("a1b2c3d4e5f6") is True

    def test_img_prefix(self):
        assert _is_gibberish("IMG_1234") is True

    def test_normal_title(self):
        assert _is_gibberish("The Dark Knight") is False

    def test_short_title(self):
        # only 2 alpha words → gibberish
        assert _is_gibberish("Dark Knight") is True


# ---------------------------------------------------------------------------
# propose_renames tests
# ---------------------------------------------------------------------------


class TestProposeRenames:
    def _paths(self, names: list[str]) -> list[Path]:
        return [Path(f"/fake/{name}") for name in names]

    def test_plain_movie_cleaned(self):
        paths = self._paths(["The.Dark.Knight.2008.1080p.BluRay.x264-GROUP.mkv"])
        proposals = propose_renames(paths)
        assert len(proposals) == 1
        assert "1080p" not in proposals[0].renamed
        assert "x264" not in proposals[0].renamed
        assert proposals[0].renamed.endswith(".mkv")

    def test_series_single_file(self):
        paths = self._paths(["breaking.bad.s01e01.pilot.HDTV.x264.mkv"])
        proposals = propose_renames(paths)
        r = proposals[0].renamed
        assert "S01E01" in r
        assert r.endswith(".mkv")

    def test_series_two_files_consistent_naming(self):
        paths = self._paths([
            "breaking.bad.s01e01.mkv",
            "breaking.bad.s01e02.mkv",
        ])
        proposals = propose_renames(paths)
        names = [p.renamed for p in proposals]
        # Both should start with the same show name
        show_parts = [n.split(" - ")[0] for n in names]
        assert show_parts[0] == show_parts[1]

    def test_series_episode_title_included(self):
        paths = self._paths(["Breaking.Bad.S01E01.Pilot.mkv"])
        proposals = propose_renames(paths)
        assert "Pilot" in proposals[0].renamed

    def test_season_episode_alternate_format(self):
        paths = self._paths(["Show.Name.1x03.Episode.Title.mkv"])
        proposals = propose_renames(paths)
        assert "S01E03" in proposals[0].renamed

    def test_gibberish_camera_filename(self):
        paths = self._paths(["VID_20240301_142233.mp4"])
        proposals = propose_renames(paths)
        assert proposals[0].needs_review is True
        assert "[needs-title]" in proposals[0].renamed

    def test_already_clean_name(self):
        paths = self._paths(["The Dark Knight.mkv"])
        proposals = propose_renames(paths)
        # Renamed should not be worse than input
        assert proposals[0].renamed.endswith(".mkv")

    def test_mixed_case_title_cased(self):
        paths = self._paths(["the.dark.knight.mkv"])
        proposals = propose_renames(paths)
        # Should be title-cased
        r = proposals[0].renamed
        assert r[0].isupper()

    def test_extension_preserved(self):
        for ext in [".mp4", ".mkv", ".avi", ".mov"]:
            paths = self._paths([f"some.movie.1080p{ext}"])
            proposals = propose_renames(paths)
            assert proposals[0].renamed.endswith(ext)

    def test_no_unchanged_proposals_for_junk_name(self):
        original = "Movie.Name.2023.1080p.BluRay.x264-GROUP.mkv"
        paths = self._paths([original])
        proposals = propose_renames(paths)
        assert proposals[0].renamed != original
