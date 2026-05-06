# SSH Key Setup for Raspberry Pi

This guide walks you through enabling SSH on your Raspberry Pi, generating an
ED25519 key pair on your laptop, and configuring passwordless login.

---

## 1. Enable SSH on the Pi

**Option A — headless (SD card):**
Before first boot, create an empty file named `ssh` in the `/boot` partition of
the SD card. The Pi will enable the SSH server on first boot.

**Option B — via the Pi desktop:**
Open *Raspberry Pi Configuration* → *Interfaces* → enable **SSH**.

**Option C — from the terminal on the Pi:**
```bash
sudo systemctl enable --now ssh
```

---

## 2. Find the Pi's IP address or hostname

Raspberry Pi OS advertises itself via mDNS as `raspberrypi.local` by default.
Test reachability from your laptop:

```bash
ping raspberrypi.local
```

If that doesn't work, find the IP from your router's DHCP table, or run on the Pi:

```bash
hostname -I
```

---

## 3. Generate an ED25519 key pair (laptop)

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_rpi -C "laptop -> rpi"
```

Accept the default passphrase or set one for extra security.

---

## 4. Copy the public key to the Pi

```bash
ssh-copy-id -i ~/.ssh/id_ed25519_rpi.pub pi@raspberrypi.local
```

You'll be prompted for the Pi's password (default: `raspberry`).
After this, you should not need a password again.

---

## 5. Verify passwordless login

```bash
ssh -i ~/.ssh/id_ed25519_rpi pi@raspberrypi.local
```

You should land in the Pi shell immediately.

---

## 6. Create a `~/.ssh/config` alias (optional but recommended)

```
Host rpi
    HostName raspberrypi.local
    User pi
    IdentityFile ~/.ssh/id_ed25519_rpi
    Port 22
```

Now you can just type `ssh rpi`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `raspberrypi.local` not found | Install Bonjour (Windows) or `avahi-daemon` (Linux) |
| Permission denied (publickey) | Check `~/.ssh/authorized_keys` on the Pi has your public key |
| SSH times out | Confirm `sudo systemctl status ssh` shows *active* on the Pi |
| Wrong username | Default user on Raspberry Pi OS is `pi` |
| Firewall blocking | Run `sudo ufw allow ssh` on the Pi (if ufw is enabled) |

---

## Using `rpi-sync setup-ssh`

The `setup-ssh` subcommand automates steps 3–4:

```bash
rpi-sync setup-ssh
```

It will:
1. Generate `~/.ssh/id_ed25519` if it doesn't exist.
2. Run `ssh-copy-id` to install the public key on the Pi (prompts once for the password).
