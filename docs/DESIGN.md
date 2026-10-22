# purrd — Specification & design study

> **purrd** sonifies waiting. While a long task runs, ambient music plays; when
> the task finishes, **silence returns** and tells you that you can get back to
> it. You launch your build (or Claude Code), look away from the screen, do
> something else — your ears keep watch for you.

Project reference document. Version 0.1 (MVP). Status: design approved, ready to build.

---

## 1. Executive summary

`purrd` is a small command-line tool (Python) that plays ambient music **while** a
long command runs and stops it **at the end**. The information is not carried by a
one-off notification (a "beep") but by the **continuity of the sound and its
interruption**: presence = work in progress, silence = work done.

Audience: developers and operators who launch long tasks (builds, tests, coding
agents like Claude Code, deployments) and want to **free their visual attention**
without missing the moment the task ends.

Hard constraints: **simple** (readable in fifteen minutes), **frugal** (negligible
CPU cost), **sovereign** (100% local, offline, no cloud dependency), **auditable**
(clear, tested code, no magic).

---

## 2. Context & problem

Modern hardware has gone silent. In the era of spinning hard drives, you could
*hear* the computer working; the scratching stopped and you knew it was done. The
SSD removed that involuntary sensory feedback. As a result, faced with a long task,
we **stare at the screen** or compulsively check a terminal, which fragments
attention and is tiring.

Existing tools mostly address the **end** of a task: a beep, a desktop
notification, a sound played after the command. That signal is **fleeting**: with
headphones on, having left the room, or absorbed in something else, you miss it,
and it does not come back.

**The gap addressed:** a *continuous, ambient* activity signal whose **absence**
(silence) is what informs — a persistent state you cannot miss, requiring no active
attention during the task.

---

## 3. Vision & concept

`purrd` deliberately reintroduces the activity indicator that silent hardware took
away from us, but a pleasant one: background music.

- **Sound present** = "working, look away from the screen".
- **Sound stops** = "done, come back".
- **Silence is the signal.** This is the inverse of an end-of-task beep.

Guiding analogy (the workshop): the machine tool humming while it cuts. The
operator does something else; when the hum stops, they look up. `purrd` is that
hum, made listenable.

Cognitive benefit: we **delegate monitoring to hearing** (an under-used peripheral
channel) to keep the eyes and active attention available for something else.

Comfort angle: because the end-of-task signal moves to hearing, there is less reason
to keep watching the screen while you wait — easier on the eyes, and one less thing
pulling your gaze back to the monitor.

---

## 4. Objectives and non-objectives

### Objectives (what purrd does)
- Play background music during an arbitrary command and stop it at its end.
- Integrate with coding agents (Claude Code) via their hooks: sound while the agent
  works, silence when it hands control back.
- Produce a **pleasant, unobtrusive** sound over time (instrumental lo-fi hip-hop).
- Stay frugal, local and readable.

### Non-objectives (what purrd is not)
- **Not** a digital audio workstation (DAW), not an editable sequencer.
- **Not** an end-of-task beeper (that is exactly what we are replacing).
- **Not** a music library player.
- **Not** a network service or a remote daemon.
- **No** voice, lyrics or rap — instrumental only.

---

## 5. Use cases

1. **Builds / tests:** `purrd make -j8`, `purrd cargo test`, `purrd pytest`. The
   music plays, the user reads their email; silence calls them back.
2. **Coding agent:** Claude Code launched on a 20-minute task; music starts when the
   agent works, stops when it waits for input or is done.
3. **Arbitrary long command:** `purrd ./deploy.sh`, transfers, conversions.
4. **Listening / tuning:** `purrd demo` to hear the loop and pick a mood.

---

## 6. Functional requirements

| Ref   | Requirement |
|-------|-------------|
| FR-1  | Wrap a command: play during its execution, stop at termination, propagate its exit code. |
| FR-2  | Daemon mode `start` / `stop` driven by external hooks; `start` is idempotent and non-blocking. |
| FR-3  | Generate a loopable lo-fi track, deterministic for a given seed. |
| FR-4  | Allow the mood to vary via parameters (`--seed`, `--bpm`, `--volume`, `--seconds`). |
| FR-5  | Auto-detect the available audio player (PipeWire, ALSA, ffmpeg). |
| FR-6  | `demo` mode to preview the loop. |

## 7. Non-functional requirements

| Ref    | Requirement |
|--------|-------------|
| NFR-1  | **Frugality:** negligible CPU cost (single generation + playback regulated by back-pressure; `nice` priority on the integration side). |
| NFR-2  | **Sovereignty:** 100% offline, no network request, no telemetry, no cloud dependency. |
| NFR-3  | **Auditability:** pure core separated from side effects; whole repo readable in ~15 min; tests that document. |
| NFR-4  | **Portability:** Linux (developed on an Arch-based distribution); depends only on Python >= 3.10 + numpy + a system audio player. |
| NFR-5  | **Responsiveness:** sound must stop within ~0.1 s after the task ends. |
| NFR-6  | **Minimal, justified dependencies:** a single runtime dependency (numpy). |

---

## 8. Architecture

Strict **pure / side-effect** separation. The sound is *computed* by pure functions
(testable, deterministic); it is only *emitted* in an isolated layer.

```
                 user command / Claude Code hook
                              │
                       ┌──────▼──────┐
                       │   cli.py    │  argument parsing; auto-routes to
                       │             │  the shared daemon when available
                       └──────┬──────┘
                              │
            ┌─────────────────┼─────────────────┐
            │ local mode      │   daemon mode   │
            │                 │                 │
     ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
     │  runner.py  │   │  daemon.py  │   │  runner.py  │
     │             │   │  (client/  │   │  (server)   │
     │ run_with_   │   │   server)   │   │             │
     │ music(cmd)  │   │             │   │ start/stop  │
     │ start/stop  │   └──────┬──────┘   └──────┬──────┘
     └──────┬──────┘          │                 │
            │                  │                 │
            │         ┌────────┘                 │
            │         │                          │
   generates│         │                   emits   │
┌───────────▼──┐ ┌────▼──────────┐ ┌────────────▼─┐
│ sequencer.py │ │  sequencer.py │ │   player.py    │  <- only side effect
│   (PURE)     │ │    (PURE)     │ │  (PCM -> system│   (aplay / pw-cat / ffplay)
└──────┬───────┘ └───────┬───────┘ │   player, loop)│
       │                 │         └────────────────┘
┌──────▼──────┐
│   synth.py   │  PURE primitives: kick, snare, hat,
│   (PURE)     │  pluck_bass, soft_lead
└──────────────┘
```

### Role of each module
- **`synth.py`** — the instruments, pure functions returning float signals. Noise
  (snare, hat) receives a random generator as a parameter to stay deterministic and
  testable.
- **`patterns.py`** — pure banks of drum patterns, bass riffs, scales/modes, and
  named *styles* that combine them. Deterministic selection from a seeded RNG.
- **`sequencer.py`** — assembles a loopable lo-fi track. Default style ``"classic"``
  keeps the original **locked** groove (fixed drums + bass line) byte for byte;
  other styles draw from ``patterns.py`` so every seed can sound different.
- **`player.py`** — converts to 16-bit PCM and plays on a loop via a system player,
  in small chunks so it can stop almost instantly.
- **`runner.py`** — orchestration: music during a command, or `start/stop` daemon.
- **`daemon.py`** — optional Unix-socket daemon. Lets users without audio access
  (isolated accounts, Docker) send commands to a single daemon running under a
  user with a real PipeWire session. The CLI auto-detects the daemon and falls
  back to local mode when it is absent.
- **`cli.py`** — command-line interface.
- **`integrations/`** — generic shell wrapper + ready-to-use Claude Code hooks.

---

## 9. Technical choices (and their rationale)

- **Python + numpy.** numpy makes synthesis trivial and fast; a single, justified
  runtime dependency. Generating a 32 s track is near-instant.
- **Pentatonic scale.** On this scale you essentially cannot play a wrong note: a
  random draw already sounds consonant. That is what makes generation *simple AND
  pleasant*.
- **Locked groove + variable melody (classic style).** The foundation (drums + bass line) loops
  identically -> stability, anchoring. Only the melody varies -> no monotony.
- **Style presets for variety.** Other styles (`chill`, `drive`, `noir`, `minimal`) select from shared pattern/riff/scale banks so that two seeds can produce genuinely different grooves while staying deterministic and reproducible.
- **Lo-fi hip-hop.** A genre designed to run in the background without grabbing
  attention ("lofi beats to study to"): the best register for a waiting backdrop.
- **Loop rather than real-time stream.** We generate one track and repeat it:
  simpler, deterministic, and CPU cost stays near zero (playback regulates writes
  via back-pressure).
- **16-bit / 44.1 kHz.** CD quality, standard, sufficient. The "vinyl" grain is
  added as an *effect* on top, without degrading the actual resolution.
- **`pw-cat` / `aplay` / `ffplay`.** We rely on whatever player is already present
  (PipeWire first) instead of bundling an audio stack.
- **Shared Unix-socket daemon.** Some accounts (e.g. an isolated `coder` user or a
  Docker container) cannot reach the desktop PipeWire socket. A single daemon
  running under the audio-capable user exposes a local Unix socket in a shared
  directory; the CLI transparently routes `start`, `stop`, `say`, `stop-voice`
  and `status` through it. The socket is group-writable and the fallback stays
  local, keeping single-user setups unchanged.
- **No bytebeat.** Striking in a ten-second demo, but harsh and tiring as a
  prolonged backdrop: the wrong engine for this use. Ruled out knowingly.

---

## 10. Usage modes

- **Wrapper:** `purrd <command...>` — plays during, stops at the end (FR-1).
- **Claude Code hooks:** `purrd start` on `UserPromptSubmit`, `purrd stop` on `Stop`
  and `Notification` (FR-2). Details in `docs/INSTALLATION.md`.

---

## 11. Risks & limitations

- **Timbre fatigue.** A constant timbre can wear over long sessions. Mitigation:
  melody varies by seed; later, pattern and per-phase mood variation (roadmap).
- **Audio heterogeneity.** Depending on the setup (ALSA vs PipeWire vs BT headset),
  output may need adjustment. Mitigation: auto-detection + troubleshooting guide.
- **Taste.** Not everyone likes background music while working. This is an assumed
  niche use; volume and stopping are trivial.
- **"Homemade" quality.** The output is deliberately simple, not a pro production.

---

## 12. Roadmap

- **v0.1 (MVP)** — wrapper + hooks + locked lo-fi engine + demo. *(scope of this document)*
- **v0.2** ✅ — vary the drum patterns and bass line from bar to bar; a bank of mood presets. Implemented as named ``--style`` presets (`classic`, `chill`, `drive`, `noir`, `minimal`) backed by pattern/riff/scale banks.
- **v0.3** — moods that evolve with the phase / duration of the task; more style packs and per-style parameters exposed in the studio.
- **v0.4** — explorer: generate variations, let you listen and save your favourites.

---

## 13. Success criteria

1. You launch a long task, **look away from the screen** without anxiety, and the
   **return to silence** reminds you effectively.
2. CPU cost stays **negligible** during a heavy build (the music gets out of the way).
3. The repo is **readable and understandable in fifteen minutes** by someone else.
4. Installation and first listen fit in **fewer than five commands**.

---

## 14. License & governance

Proposed license: **MIT** (permissive, consistent with a sovereign, open
approach). Possible alternative: MIT/Apache-2.0 for broader adoption. *(Author's
choice; this document does not settle the legal aspect.)*

The repo is designed to be **auditable from the first commit**: clear structure,
documentation of the *why*, tests that document usage, minimal dependencies, no
hidden magic.
