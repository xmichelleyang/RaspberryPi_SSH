---
name: rpi-sync
description: >
  Use this skill when the user wants to send, sync, transfer, or push video
  files to their Raspberry Pi, or when they ask to rename, clean up, or
  organize their video files. Trigger phrases include: "send videos to my pi",
  "sync videos to raspberry pi", "push movies to the pi", "rename my videos",
  "transfer films to raspberry pi", "clean up video filenames".
---

# rpi-sync Skill

This skill helps you sync video files from your laptop to a Raspberry Pi using
the `rpi-sync` CLI tool. It handles intelligent renaming and reliable
SSH-based file transfer.

## Prerequisites

- `rpi-sync` installed (`pip install -e .` from the repo root).
- `config.yaml` configured with your Pi's hostname, user, and target directory.
- Passwordless SSH access to the Pi (see `docs/ssh-setup.md`).

## Workflow

Follow these steps in order:

### Step 1 — Inspect and propose renames

```bash
rpi-sync rename
```

This shows a dry-run table of proposed renames without touching any files.
Share the table with the user and ask if they approve.

### Step 2 — Review the proposals with the user

Show the output to the user. Look for:
- Files marked `[needs-title]` — these couldn't be auto-named and need a human title.
- Any show names that look wrong (e.g., partial matches, wrong capitalisation).

If the user is unhappy with a proposed rename, suggest adding a manual override
in `config.yaml` (feature roadmap) or renaming the source file manually before
re-running.

### Step 3 — Apply renames (on user approval)

```bash
rpi-sync rename --apply
```

The tool will prompt for confirmation before touching any files on disk.

### Step 4 — Transfer to the Pi

```bash
rpi-sync push
```

This connects over SSH, compares local files to what's already on the Pi
(by name + size), and uploads only what's missing. A progress bar is shown
per file. Failures are retried once.

### Step 5 — Confirm files are on the Pi

```bash
rpi-sync ls
```

Report the list of files back to the user so they know everything landed
correctly.

## Reasoning about imperfect renames

When the dry-run output isn't ideal:

1. **Wrong show name grouping** — files from different shows may share a short
   prefix. Tell the user to rename source files to include the full show name
   before running again.

2. **`[needs-title]` entries** — camera-generated names (e.g., `VID_20240301_142233.mp4`)
   can't be auto-titled. Ask the user what the file is and rename it manually:
   ```bash
   mv videos_to_send/VID_20240301_142233.mp4 "videos_to_send/My Holiday 2024.mp4"
   ```
   Then re-run `rpi-sync rename`.

3. **Partial episode titles** — if the episode title looks truncated, the
   original filename may not include a full title. That's fine — the
   `S01E03` marker is still correct.

4. **All files skipped on push** — if `rpi-sync push` reports 0 transferred,
   the files already exist on the Pi with matching sizes. Use `rpi-sync ls`
   to verify.

## Troubleshooting

- **Connection error** — run `rpi-sync setup-ssh` to set up key authentication.
- **No video files found** — make sure files are in `videos_to_send/` and have
  a supported extension (`.mp4`, `.mkv`, `.mov`, `.avi`, `.webm`).
- **Wrong target directory** — check `pi.target_dir` in `config.yaml`.
