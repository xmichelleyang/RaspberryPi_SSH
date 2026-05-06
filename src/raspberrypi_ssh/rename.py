"""Intelligent video filename renaming logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Release junk to strip
_JUNK_PATTERNS = [
    r"\[.*?\]",                          # anything in square brackets e.g. [YTS.MX]
    r"\(.*?\)",                          # anything in parens   e.g. (1080p)
    r"\b(1080p|720p|480p|2160p|4k)\b",  # resolution
    r"\b(bluray|blu-ray|bdrip|brrip|webrip|web-dl|web|hdtv|dvdrip|dvdscr)\b",
    r"\b(x264|x265|h264|h265|hevc|xvid|divx|avc)\b",  # codec
    r"\b(aac|ac3|dts|mp3|flac|truehd|atmos)\b",        # audio codec
    r"\b(extended|theatrical|remastered|proper|repack|internal)\b",
    r"-[a-z0-9]{2,10}$",                # scene group suffix like -GROUP
]
_JUNK_RE = re.compile("|".join(_JUNK_PATTERNS), re.IGNORECASE)

# Season/episode patterns
_SE_PATTERNS = [
    re.compile(r"s(\d{1,2})e(\d{1,2}(?:-e\d{1,2})?)", re.IGNORECASE),   # S01E03
    re.compile(r"(\d{1,2})x(\d{1,2})", re.IGNORECASE),                    # 1x03
    re.compile(r"season\s*(\d{1,2})\s*episode\s*(\d{1,2})", re.IGNORECASE),  # Season 1 Episode 3
]

# Gibberish / camera filename patterns
_GIBBERISH_RE = re.compile(
    r"^(vid_?\d{8}|img_?\d{4}|[a-f0-9]{8,}|dsc\d+|mov\d+|clip\d+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RenameProposal:
    original: str
    renamed: str
    needs_review: bool = False


@dataclass
class _ParsedFile:
    path: Path
    stem: str             # filename without extension
    ext: str              # .mkv etc.
    show_key: str = ""    # normalised show name (for grouping)
    season: int = 0
    episode: str = ""     # may be "03" or "03-E04" for multi-ep
    episode_title: str = ""
    is_series: bool = False
    needs_review: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clean_stem(stem: str) -> str:
    """Replace separators, strip junk, title-case."""
    # Replace dots/underscores used as word separators
    text = re.sub(r"(?<=[a-zA-Z0-9])\.(?=[a-zA-Z0-9])", " ", stem)
    text = text.replace("_", " ")
    # Strip junk
    text = _JUNK_RE.sub(" ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title_case(text: str) -> str:
    """Title-case but preserve ALL-CAPS acronyms (≥2 chars)."""
    words = text.split()
    result = []
    for word in words:
        if word.isupper() and len(word) >= 2:
            result.append(word)
        else:
            result.append(word.capitalize())
    return " ".join(result)


def _extract_series_info(text: str) -> tuple[str, int, str, str]:
    """
    Try to extract (show_title, season, episode_str, episode_title) from *text*.

    Returns ("", 0, "", "") if no series pattern found.
    """
    for pat in _SE_PATTERNS:
        m = pat.search(text)
        if m:
            before = text[: m.start()].strip()
            after = text[m.end() :].strip()
            season = int(m.group(1))
            raw_ep = m.group(2)
            # Normalise multi-episode like "E03-E04" → "03-E04"
            ep_str = re.sub(r"e", "", raw_ep, flags=re.IGNORECASE)
            # episode_str should be zero-padded
            parts = re.split(r"[-]", raw_ep, flags=re.IGNORECASE)
            ep_str = "-E".join(f"{int(re.sub(r'[eE]', '', p)):02d}" for p in parts)
            return before, season, ep_str, after
    return "", 0, "", ""


def _is_gibberish(name: str) -> bool:
    """Return True if the name looks like a camera/hash filename."""
    if _GIBBERISH_RE.match(name):
        return True
    alpha_words = [w for w in name.split() if w.isalpha() and len(w) > 1]
    return len(alpha_words) < 3


def _parse_file(path: Path) -> _ParsedFile:
    ext = path.suffix.lower()
    raw_stem = path.stem
    cleaned = _clean_stem(raw_stem)
    show_title, season, episode_str, episode_title = _extract_series_info(cleaned)

    if season:
        pf = _ParsedFile(
            path=path,
            stem=raw_stem,
            ext=ext,
            show_key=_title_case(show_title).lower(),
            season=season,
            episode=episode_str,
            episode_title=_title_case(episode_title),
            is_series=True,
        )
    else:
        pf = _ParsedFile(
            path=path,
            stem=raw_stem,
            ext=ext,
        )

    # Gibberish check (only for non-series)
    if not pf.is_series and _is_gibberish(cleaned):
        pf.needs_review = True

    return pf


def _build_filename(pf: _ParsedFile, show_name_override: str | None = None) -> str:
    """Construct the final filename string."""
    ext = pf.ext

    if pf.is_series:
        show = show_name_override or _title_case(pf.show_key)
        ep_part = f"S{pf.season:02d}E{pf.episode}"
        if pf.episode_title:
            base = f"{show} - {ep_part} - {pf.episode_title}"
        else:
            base = f"{show} - {ep_part}"
        return base + ext

    # Plain movie / unknown
    cleaned = _clean_stem(pf.stem)
    if pf.needs_review:
        return f"[needs-title] {_title_case(cleaned)}{ext}"
    return _title_case(cleaned) + ext


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def propose_renames(paths: list[Path]) -> list[RenameProposal]:
    """
    Given a list of video file *paths*, return a list of :class:`RenameProposal`.

    Series files are grouped and their show name is normalised consistently.
    """
    parsed = [_parse_file(p) for p in paths]

    # Group series files by show_key
    series_groups: dict[str, list[_ParsedFile]] = {}
    for pf in parsed:
        if pf.is_series:
            series_groups.setdefault(pf.show_key, []).append(pf)

    # For groups ≥2, pick the most common / longest clean show name
    show_name_map: dict[str, str] = {}
    for key, group in series_groups.items():
        # Use the longest title_cased show name from the group
        names = [_title_case(pf.show_key) for pf in group]
        show_name_map[key] = max(names, key=len)

    proposals = []
    for pf in parsed:
        override = show_name_map.get(pf.show_key) if pf.is_series else None
        new_name = _build_filename(pf, override)
        proposals.append(
            RenameProposal(
                original=pf.path.name,
                renamed=new_name,
                needs_review=pf.needs_review,
            )
        )
    return proposals


def apply_renames(paths: list[Path], proposals: list[RenameProposal]) -> list[tuple[Path, Path]]:
    """
    Rename files on disk.  Returns list of (old_path, new_path) pairs.
    """
    results = []
    for path, proposal in zip(paths, proposals):
        if path.name == proposal.renamed:
            continue  # nothing to do
        new_path = path.parent / proposal.renamed
        path.rename(new_path)
        results.append((path, new_path))
    return results
