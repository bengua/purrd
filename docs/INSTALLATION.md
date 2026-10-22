# Installation & setup

How to set up `purrd`: installation, audio output, Claude Code integration, the
generic wrapper, tuning and troubleshooting. Written for Arch-based distributions, adaptable
elsewhere.

---

## 1. Prerequisites

- **Python >= 3.10**
- **numpy** (installed automatically)
- **a command-line audio player**, one of:
  - PipeWire — `pw-cat` (package `pipewire-audio`) <- recommended on modern desktops (KDE, GNOME)
  - ALSA — `aplay` (package `alsa-utils`)
  - ffmpeg — `ffplay`

`purrd` auto-detects which one is present (in that order). For multi-user setups,
see the **Shared daemon** section below.

```bash
# Arch-based — at least one of the three:
sudo pacman -S --needed pipewire-audio    # pw-cat
sudo pacman -S --needed alsa-utils        # aplay
sudo pacman -S --needed ffmpeg            # ffplay
```

## 2. Installation

### With uv (recommended)
```bash
cd purrd
uv sync                 # environment + dependencies + the `purrd` binary
uv run purrd demo       # listening test
```

### With pip
```bash
cd purrd
python -m venv .venv && source .venv/bin/activate
pip install -e .
purrd demo
```

Check playback: you should hear the lo-fi loop. `Ctrl-C` to stop.

## 3. First use

```bash
purrd sleep 10          # plays for 10 s then goes quiet: that is the principle
purrd make -j8          # a real build
purrd --seed 7 cargo test
```

The **silence** at the end is the signal. Launch, then look away.

## 4. Generic wrapper (`withsound`)

To avoid typing `purrd` every time, add a function to your `~/.bashrc` (or
`~/.zshrc`). The `nice -n 19` ensures the music yields the CPU as soon as the task
needs it — zero cost on your build.

```bash
withsound() { nice -n 19 purrd "$@"; }
```

Then: `withsound make -j8`. (See also `integrations/withsound.sh`.)

## 5. Claude Code integration (the core of the setup)

Goal: the music starts **when the agent works** and stops **when it hands control
back** (end of reply, or waiting for approval). When voice packs are configured,
the end of the prompt is also announced: the music stops first, then a short
`done` sample plays as an audible "all clear" signal.

For this `purrd` exposes a daemon mode: `purrd start` (launches a detached,
non-blocking, idempotent background track) and `purrd stop` (stops it).

### Step 1 — install the hook scripts
```bash
mkdir -p ~/.purrd/hooks
cp integrations/claude-hooks/purrd-on.sh  ~/.purrd/hooks/
cp integrations/claude-hooks/purrd-off.sh ~/.purrd/hooks/
chmod +x ~/.purrd/hooks/*.sh
```
> `purrd` must be on the scripts' `PATH`. With `uv`, either run `uv tool install .`
> (global binary) or put the full path to `purrd` in `purrd-on.sh`.

### Step 2 — declare the hooks
Merge this into `~/.claude/settings.json` (template in
`integrations/claude-hooks/settings.json`):

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-on.sh", "async": true } ] }
    ],
    "Stop": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-off.sh done" } ] }
    ],
    "SessionStop": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-off.sh done" } ] }
    ],
    "Notification": [
      { "hooks": [ { "type": "command", "command": "~/.purrd/hooks/purrd-off.sh permission" } ] }
    ]
  }
}
```

What each hook does:
- **`UserPromptSubmit`** — you send a message -> the agent starts working -> music
  starts. `async: true` so it never slows Claude down.
- **`Stop`** — the agent finishes its reply -> music stops, then `done` voice marker.
- **`SessionStop`** — the session ends -> same cleanup as `Stop`.
- **`Notification`** — the agent waits for input or permission -> music stops, then
  `permission` voice marker (it needs you).

### Step 3 — verify
In Claude Code, run `/hooks` to confirm the hooks appear, then give it a task: the
music should start, then stop when the agent hands control back.

## 6. Shared daemon (multi-user / Docker)

Some setups have one user that owns the audio session (e.g. your desktop user on a Wayland
desktop) while another user (e.g. an isolated `coder` account, or a Docker
container) runs Claude Code. `purrd` can run as a **Unix-socket daemon** under the
audio-capable user; every other account sends commands to it.

### When to use it

- The Claude Code process runs as a user that cannot reach PipeWire (no
  `XDG_RUNTIME_DIR` with a live audio socket).
- You want to run purrd inside a container while keeping the host audio output.

### Step 1 — choose a shared socket location

Pick a directory that both the audio-capable user and the client user can write
to. Good choices are a group-writable directory under `/tmp`, a directory under
`/run` with the right permissions, or a shared path under `PURRD_CONFIG_DIR`.

Example for a manual start as the audio-capable user:

```bash
export PURRD_DAEMON_SOCK=/tmp/purrd-shared/run/purrd.sock
export PURRD_CONFIG_DIR=/tmp/purrd-shared
mkdir -p /tmp/purrd-shared/run
chmod 2770 /tmp/purrd-shared/run
purrd daemon
```

The socket directory must be writable by the group that shares it. The socket is
created with mode `0660`.

For a persistent setup, use the provided systemd user service:

```bash
./scripts/install-systemd.sh
```

This installs `~/.config/systemd/user/purrd-daemon.service`, enables it, and
starts it. The daemon will restart automatically on failure and start with the
user session.

Check the status with:

```bash
systemctl --user status purrd-daemon
ls -l "$PURRD_DAEMON_SOCK"
```

To stop or restart manually:

```bash
systemctl --user stop purrd-daemon
systemctl --user restart purrd-daemon
```

### Step 2 — point clients to the daemon

Set `PURRD_DAEMON_SOCK` for every purrd invocation. The CLI automatically uses the
daemon when the socket exists and is writable; otherwise it falls back to local
mode.

Example start hook for the isolated user:

```bash
#!/usr/bin/env bash
export PURRD_DAEMON_SOCK=/tmp/purrd-shared/run/purrd.sock
export PURRD_CONFIG_DIR=/tmp/purrd-shared
purrd say start
nice -n 19 purrd --auto-variation start
```

> `--auto-variation` rotates through random favorites every time the track ends.
> Drop it if you prefer a single locked groove. It only activates when no explicit
> `--seed` is given.

And the matching stop hook:

```bash
#!/usr/bin/env bash
export PURRD_DAEMON_SOCK=/tmp/purrd-shared/run/purrd.sock
export PURRD_CONFIG_DIR=/tmp/purrd-shared
event=${1:-done}
purrd stop
purrd stop-voice
purrd say "$event"
```

### Step 3 — test

From the isolated account, with the daemon running:

```bash
export PURRD_DAEMON_SOCK=/tmp/purrd-shared/run/purrd.sock
purrd say start
purrd start
purrd stop
```

Sound must come from the audio-capable user's session. If the daemon is not
running, the client falls back to local mode and will fail to produce audio on an
account without a sound server.

## 7. Voice layer (optional)

The voice layer speaks short lines over the music on Claude Code events.  It is
off by default until you import a [CESP](https://openpeon.com/) sound pack.

### Step 1 — get a CESP pack

purrd ships no voice pack. Get a CESP pack (a directory holding an
`openpeon.json` manifest and its sounds) whose licence lets you use it — or make
your own by recording a few lines — and place it anywhere, e.g.
`~/Downloads/my-pack`.

### Step 2 — import it

```bash
purrd import-pack ~/Downloads/my-pack
```

The pack is copied to `~/.purrd/packs/`, normalized to 44.1 kHz mono PCM16, and
set as the active pack.

### Step 3 — update the hooks for spoken events

The Claude Code hooks can announce events in addition to starting/stopping music.
See `integrations/claude-hooks/settings.json` for an example that adds `purrd say
start` on `UserPromptSubmit`, `purrd say done` on `Stop`, and `purrd say
permission` on `Notification`.

## 8. Studio (optional GUI)

Install the GTK4 curator to edit voices and manage loop favorites visually.

The global **Stop** button stops both the background music and any currently
playing voice sample, so you can immediately return to silence when you need to
focus without audio.

### System dependencies (Arch-based)

```bash
sudo pacman -S --needed python-gobject gtk4 gobject-introspection-runtime
```

### Python dependencies

```bash
uv sync --extra studio
```

### Run

```bash
purrd-studio
```

The studio writes favorites to `~/.config/purrd/favorites.toml` (or
`$XDG_CONFIG_HOME/purrd/favorites.toml`). Each favorite stores only `seed`,
`bpm`, and `seconds` — the actual audio is regenerated on demand. When you run
`purrd <command>` without `--seed`, it picks a favorite at random if any exist.
Use `--no-favorites` to ignore saved favorites.

## 9. Tuning

| Option | Effect |
|--------|--------|
| `--seed N` | changes the melody (the foundation stays locked) |
| `--bpm N` | tempo (default 86) |
| `--seconds N` | length of the looped track (default 32) |
| `--volume 0..1` | global volume |

Example: `purrd --seed 12 --bpm 78 --volume 0.6 make`.

## 10. Troubleshooting

- **No sound** -> check a player is installed: `command -v pw-cat aplay ffplay`.
  Test it alone: `purrd demo`.
- **Crackling / choppy sound** -> increase the chunk size in `player.py`
  (`chunk_frames`), or check that PipeWire/ALSA is not saturated.
- **PipeWire vs ALSA** -> if `aplay` misbehaves under PipeWire, install
  `pipewire-audio`: `purrd` will prefer `pw-cat`.
- **Sound won't stop (hooks)** -> run `purrd stop` by hand; check the PID in
  `$XDG_RUNTIME_DIR/purrd.pid`; make sure `purrd-off.sh` is declared on both `Stop`
  and `Notification`.
- **No sound in a multi-user setup** -> verify the daemon is running under the
  audio-capable user (`pgrep -af "purrd daemon"`), that the socket exists
  (`ls -l $PURRD_DAEMON_SOCK`), and that the client can write to it. The client
  silently falls back to local mode if the socket is missing; local mode needs a
  live sound server in the caller's session.
- **CPU** -> always wrap via `nice -n 19` (the `withsound` function does this).
- **Bluetooth headset** -> BT latency may delay the start by a few hundred ms; no
  impact on use (this is a backdrop, not a beat to follow).

## 11. Uninstall
```bash
# remove the hooks from ~/.claude/settings.json, then:
rm -rf ~/.purrd
uv tool uninstall purrd   # if installed globally
```
