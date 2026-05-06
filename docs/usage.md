# Usage Reference

## Installation

```bash
# From repo root
pip install -e ".[dev]"
```

## Configuration

Copy the example config and edit:

```bash
cp config.example.yaml config.yaml
```

Config is searched in this order:
1. Path given with `--config`
2. `./config.yaml` (repo root)
3. `~/.raspberrypi_ssh/config.yaml`

### Full config reference

```yaml
pi:
  host: raspberrypi.local   # Pi hostname or IP
  user: pi                  # SSH username
  port: 22                  # SSH port
  ssh_key: ~/.ssh/id_ed25519  # Path to private key
  target_dir: /home/pi/Videos # Where to put videos on the Pi

local:
  source_dir: ./videos_to_send  # Local folder with videos to sync

rename:
  enabled: true
  video_extensions: [.mp4, .mkv, .mov, .avi, .webm]
```

---

## Subcommands

### `rpi-sync rename`

Preview or apply intelligent filename cleanup.

```bash
# Dry-run (default) — shows a table of proposed renames
rpi-sync rename

# Apply renames on disk (prompts for confirmation)
rpi-sync rename --apply
```

**Renaming rules:**
1. Replaces dots/underscores used as spaces.
2. Strips release tags (`[YTS.MX]`), resolution (`1080p`), codec (`x264`), audio, etc.
3. Title-cases remaining words.
4. Detects TV series (`S01E03`, `1x03`, `Season 1 Episode 3`) and normalises to
   `Show Name - S01E03 - Episode Title.ext`.
5. Marks unreadable/camera filenames with `[needs-title]` for manual review.

---

### `rpi-sync push`

Transfer all videos in `videos_to_send/` to the Pi, skipping files already present.

```bash
# Transfer everything
rpi-sync push

# Preview without uploading
rpi-sync push --dry-run

# Rename first, then transfer
rpi-sync push --rename
```

Files are matched by **name + size**. If a file exists on the Pi with the same
name and byte count, it is skipped. On upload failure the tool retries once,
then moves on and reports the failure at the end.

Exit code is non-zero if any file failed.

---

### `rpi-sync setup-ssh`

Interactive helper to set up passwordless SSH to your Pi.

```bash
rpi-sync setup-ssh
```

1. Generates `~/.ssh/id_ed25519` if it doesn't exist.
2. Runs `ssh-copy-id` to install the public key on the Pi.

---

### `rpi-sync ls`

List files in the Pi's target directory.

```bash
rpi-sync ls
```

Output example:
```
Files on raspberrypi.local:/home/pi/Videos
  The Dark Knight.mkv                                      4,096.0 MB
  Breaking Bad - S01E01 - Pilot.mkv                          350.0 MB
```

---

### `--config`

Pass a custom config path to any subcommand:

```bash
rpi-sync --config /path/to/my_config.yaml push
```
