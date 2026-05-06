# raspberrypi_ssh

A command-line tool that syncs videos from a local folder (`videos_to_send/`) to a Raspberry Pi over SSH, with intelligent renaming to clean up messy filenames before transfer.

## Features

- 🎬 Smart video renaming (strips junk tags, detects TV series, normalises to `Show Name - S01E03 - Episode Title.mp4`)
- 📡 SSH/SCP transfer via `paramiko` with per-file progress bars
- ⏭️ Skip files already on the Pi (matched by name + size)
- 🔄 Retry on failure, non-zero exit if any file fails
- 🤖 GitHub Copilot CLI skill for conversational sync

## Quickstart

### 1. Install

```bash
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
# edit config.yaml with your Pi's hostname, user, paths
```

### 3. First push

```bash
# Preview renames (dry-run by default)
rpi-sync rename

# Apply renames
rpi-sync rename --apply

# Transfer files to the Pi
rpi-sync push

# Or do both in one step
rpi-sync push --rename
```

## Example output

```
$ rpi-sync rename
Proposed renames (dry-run):
┌──────────────────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────┐
│ Original                                                       │ Renamed                                                       │
├──────────────────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────┤
│ The.Dark.Knight.2008.1080p.BluRay.x264-GROUP.mkv              │ The Dark Knight.mkv                                           │
│ breaking.bad.s01e01.pilot.HDTV.x264.mkv                       │ Breaking Bad - S01E01 - Pilot.mkv                             │
│ breaking.bad.s01e02.720p.mkv                                  │ Breaking Bad - S01E02.mkv                                     │
│ VID_20240301_142233.mp4                                       │ [needs-title] VID 20240301 142233.mp4                         │
└──────────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────┘
Run with --apply to rename on disk.

$ rpi-sync push
Connecting to raspberrypi.local:22 as pi...
[1/3] The Dark Knight.mkv          ████████████████████ 100% 4.2 GB
[2/3] Breaking Bad - S01E01.mkv   ████████████████████ 100% 350 MB
[3/3] Breaking Bad - S01E02.mkv   ████████████████████ 100% 320 MB
✓ 3 files transferred successfully.
```

## Subcommands

| Command | Description |
|---|---|
| `rpi-sync rename [--apply]` | Preview or apply intelligent renaming |
| `rpi-sync push [--dry-run] [--rename]` | Transfer files to the Pi |
| `rpi-sync setup-ssh` | Interactive SSH key setup helper |
| `rpi-sync ls` | List files on the Pi's target directory |

See [docs/usage.md](docs/usage.md) for full reference.

## SSH Setup

See [docs/ssh-setup.md](docs/ssh-setup.md) for step-by-step instructions.

## License

MIT
