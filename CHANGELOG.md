# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- `purrd stop-voice` command to interrupt any currently playing voice sample.
- **Shared daemon**: `purrd daemon` lets users without direct audio access (e.g.
  isolated `coder`, Docker containers) send commands to a single daemon running
  under a user with a real audio session (e.g. your desktop user). The CLI automatically
  uses the daemon when `PURRD_DAEMON_SOCK` points to a valid socket, otherwise
  falls back to local mode.
- **Auto-variation**: `purrd --auto-variation start` (or `purrd --auto-variation
  <command>`) rotates through random favorites every time the track ends instead
  of looping the same one forever. Perfect for long prompts.
- **Studio AI generation**: the music explorer tab gains a prompt field, a count
  spin (default 20) and a "Generate via AI" button that ask an external
  generation server (opt-in: `PURRD_AI_URL`, disabled when unset) to render
  instrumental tracks for the selected style into the ambience bank, polling the
  job until it finishes. purrd stays model-free at runtime: no model runs inside
  purrd, the external server does the rendering.

### Removed

- Bundled third-party voice packs: purrd no longer ships any. Import the CESP
  packs you are allowed to use with `purrd import-pack <dir>`.

### Fixed

- **No more orphan daemon**: when `purrd start` replaced a daemon that was still
  draining its audio pipe, the dying daemon erased the PID file of its
  replacement, which then played for hours with nothing able to stop it. A daemon
  now only removes its own PID-file entry, `stop()` waits for the process group to
  be really gone before escalating to SIGKILL, and `start()` never forks over a
  daemon that refuses to die.
- **Auto-variation no longer drops out**: the next track is rendered in the
  background starting ~3 minutes before the current track ends, and a short
  crossfade locks the tempo across the boundary instead of leaving a silent gap.
- Studio "Stop" button now stops both background music and voice playback, allowing
  silent work without leaving orphaned audio.
- End-of-prompt hook sequence is now documented and reliable: music stops first,
  then the `done` voice marker plays to signal that Claude has finished.

## [0.4.0] — 2026-06-19

### Added

- **Studio**: progress bar during preview loop PCM generation.
- **Styles**: `funky`, `techno`, `latin`, `triphop`, `hardrock` and `house`.
- **Reggae style**: classic guitar skank chops on offbeats.
- **Instruments**: `pad`, `strings` and `synth_lead` synth voices, used across several styles.
- **Transitions**: section transitions (`rise`, `fill`, `drop`, `halt`) between style sections.
- **Pack discovery**: `PURRD_TEMPLATE_PACKS` environment variable for CESP template discovery.

### Fixed

- Voice samples no longer include the WAV RIFF header in the streamed PCM.
- Explicit `--bpm` and `--seconds` no longer get silently overridden by a favorite.
- Config save now serializes all top-level sections, not just `[voice]`.
- Pack storage moved to XDG (`~/.local/share/purrd/packs`) with a one-time migration from `~/.purrd/packs`.
- Pad and strings volume was too low to be audible.

## [0.2.4] — 2026-06-18
### Added
- Optional voice-on-events layer (`src/purrd/voice.py`, `purrd say <event>`).
- CESP sound-pack support: import packs with `purrd import-pack <dir>`, play random
  event-mapped lines over the music, and manage packs from `purrd-studio`.
- Voice pack audio is normalized to 44.1 kHz mono PCM16 on import.
- Claude Code hooks now trigger spoken lines alongside music start/stop.
- Optional GTK4 studio GUI (`purrd-studio`) with voice pack management and a music
  explorer that saves favorite loops as deterministic parameters in
  `~/.config/purrd/favorites.toml`.
- Favorites integration: `runner.run_with_music` picks a saved favorite when no explicit
  `--seed` is given (override with `--no-favorites`).

### Removed
- Piper TTS generation and `scripts/build-voices.sh`; voices now come from imported
  CESP packs only.

### Fixed
- `pw-cat` now uses raw mode for PCM stdin playback.
- Voice packs are discovered from `~/.purrd/packs` even when purrd is installed as a
  global tool.

## [0.1.0] — 2026-06-18
### Added
- Wait-sonification MVP: music plays during a command, silence signals the end.
- Generative lo-fi engine: pure synthesis primitives (`synth`), sequencer with a
  locked groove and pentatonic melody (`sequencer`).
- Looped audio output via a system player — PipeWire / ALSA / ffmpeg (`player`).
- Command wrapping and `start`/`stop` daemon mode (`runner`, `cli`).
- Integrations: generic shell wrapper and Claude Code hooks.
- Specification, README, installation guide, and a test suite for the core.
