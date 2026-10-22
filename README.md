# purrd

**Sonification de l'attente : vos tâches longues chantent quand elles finissent.**
Pendant qu'une commande tourne, une boucle lo-fi joue. Quand elle se termine, le
silence revient — et vous dit que vous pouvez reprendre la main.

[![Licence : MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/OWNERTEST/purrd/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNERTEST/purrd/actions/workflows/ci.yml)

```text
   /\_/\      $ purrd make -j8
  ( o.o )     ♪ ♫  lo-fi pendant le build  ♫ ♪
   > ^ <      ...                 (silence)  -> c'est fini
```

> Du son = ça travaille. Le silence = c'est terminé.

## Présentation

Vous lancez un build, une suite de tests ou un agent de code, vous détournez les
yeux de l'écran, vous allez chercher un café. Vos oreilles surveillent à votre
place : pas besoin de fixer un terminal. Le retour au silence est le signal — un
état qu'on ne peut pas rater, contrairement à un bip.

La musique est **générée localement** (synthèse pure en numpy, aucun fichier audio
ni modèle requis) et **déterministe** : une même graine donne toujours le même
morceau.

## Fonctionnalités

- **Enveloppe n'importe quelle commande** : `purrd <commande>` joue tant qu'elle tourne.
- **Mode daemon** (`purrd start` / `purrd stop`), utilisé par les hooks Claude Code.
- **Cinq styles musicaux** : `classic`, `chill`, `drive`, `noir`, `minimal`, chacun
  avec ses rythmes, basses, gamme et arrangement.
- **Favoris et auto-variation** : gardez les boucles qui vous plaisent, faites-les
  tourner sur les longues sessions.
- **Banque d'ambiances** (optionnelle) : jouez vos propres fichiers audio à la place
  ou en alternance avec le synthé.
- **Couche voix** (optionnelle) : de courtes répliques par-dessus la musique sur les
  événements `start`, `done`, `permission`, `error`, à partir de packs sonores
  [CESP](https://openpeon.com/) que vous importez.
- **Studio GTK4** (extra optionnel) : explorer les boucles, gérer les favoris et les
  packs de voix.
- **Dégradation douce** : pas de banque, pas de pack, pas de `ffmpeg` ? purrd joue
  quand même, sans rien casser.

## Installation depuis zéro

### Prérequis

- Linux, Python **3.10+**.
- Un lecteur audio système : **PipeWire** (`pw-cat`), **ALSA** (`aplay`) ou
  **ffmpeg** (`ffplay`). purrd prend automatiquement celui qui est présent.
- Optionnel : [`uv`](https://docs.astral.sh/uv/), `ffmpeg` (banque d'ambiances),
  GTK4 + PyGObject (studio).

### Installer

```bash
git clone https://github.com/OWNERTEST/purrd
cd purrd
uv sync                      # ou : python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

### Premier lancement

```bash
uv run purrd demo            # écoutez la boucle (Ctrl-C pour arrêter)
uv run purrd sleep 20        # musique pendant 20 s, puis silence
```

Le pas-à-pas complet (systemd, Docker, hooks Claude Code, couche voix) est dans
[`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## Utilisation

```bash
purrd <commande...>              # enveloppe n'importe quelle commande
purrd --seed 3 ./run.sh          # une autre ambiance (la graine change la mélodie)
purrd --style chill demo         # écouter un style précis
purrd start | purrd stop         # mode daemon
purrd --auto-variation start     # fait tourner les favoris sur les longues sessions
purrd bank                       # état de la banque d'ambiances
purrd bank ratio 0.5             # moitié banque, moitié synthé
purrd import-pack <dossier>      # importe un pack de voix CESP
purrd say done                   # réplique parlée par-dessus la musique
purrd stop-voice                 # coupe une réplique en cours
```

Les options (`--bpm`, `--seconds`, `--seed`, `--volume`, `--style`/`--mood`) se
placent **avant** la commande.

**Voix.** purrd n'embarque aucun pack sonore : importez un pack CESP dont la licence
vous autorise l'usage, ou enregistrez le vôtre. Sans pack, `purrd say` ne fait
simplement rien.

**Claude Code.** La musique démarre quand l'agent travaille et s'arrête quand il
rend la main : configuration prête dans
[`integrations/claude-hooks/`](integrations/claude-hooks/).

**Studio.** `uv sync --extra studio && uv run purrd-studio`. Le CLI reste dépendant
de numpy seul.

## Configuration

| Variable | Rôle | Défaut |
|----------|------|--------|
| `PURRD_CONFIG_DIR` | dossier de configuration (`config.toml`, `favorites.toml`) | `$XDG_CONFIG_HOME/purrd` |
| `PURRD_BANK_DIR` | banque d'ambiances (`.mp3`, `.wav`, `.flac`, `.ogg`, `.opus`, `.m4a`) | `$XDG_DATA_HOME/purrd/bank` |
| `PURRD_PACKS_DIR` | packs de voix importés | `$XDG_DATA_HOME/purrd/packs` |
| `PURRD_TEMPLATE_PACKS` | dossier de packs CESP proposés à l'import | non défini |
| `PURRD_DAEMON_SOCK` | socket Unix du daemon optionnel | `$XDG_RUNTIME_DIR/purrd/purrd.sock` |
| `PURRD_AI_URL` | serveur de génération musicale externe pour le bouton « Generate via AI » du studio | **non défini = désactivé** |

purrd ne lance jamais de modèle lui-même : avec `PURRD_AI_URL`, le studio se
contente de soumettre une requête à un serveur compatible (API décrite dans
`src/purrd/studio/ai_bank.py`) et de suivre le job.

## Développement

```bash
./verify.sh                  # ruff + pytest, comme la CI (aucune carte son nécessaire)
```

Les choix de conception sont expliqués dans [`docs/DESIGN.md`](docs/DESIGN.md), le
flux de contribution dans [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Pourquoi ce projet

Parce qu'un ordinateur qui fredonne pendant qu'il bosse, c'est plus sympa qu'une
barre de progression — et qu'un silence s'entend de l'autre bout de la pièce.
C'est aussi un petit cas d'école : synthèse audio en Python pur, code cœur sans
effet de bord, testé sans carte son.
Et tout tourne en local : pas de cloud, pas de modèle, pas de télémétrie.

## Licence

[MIT](LICENSE).

## English

**Wait sonification: your long tasks sing until they finish.** While a command
runs, a lo-fi loop plays; when it ends, silence returns — your cue to get back to
work. The music is synthesised locally in pure numpy (no audio files, no model)
and is deterministic per seed.

- Wrap any command (`purrd <command>`) or use the daemon (`purrd start` / `stop`),
  e.g. from the Claude Code hooks in `integrations/claude-hooks/`.
- Five styles (`classic`, `chill`, `drive`, `noir`, `minimal`), favorites,
  auto-variation, an optional ambience bank of your own audio files.
- Optional voice layer from [CESP](https://openpeon.com/) packs you import —
  purrd ships none — and an optional GTK4 studio.

```bash
git clone https://github.com/OWNERTEST/purrd
cd purrd
uv sync            # or: pip install -e .
uv run purrd demo
```

Needs Linux, Python 3.10+ and PipeWire, ALSA or ffmpeg. Configuration is by
environment variables (table above); `PURRD_AI_URL` (off by default) points the
studio at an external music generation server. Full guide:
[`docs/INSTALLATION.md`](docs/INSTALLATION.md). Licence: MIT.

---

Un projet [FreedzHost](https://freedzhost.cloud) — souveraineté numérique, IA locale, homelab.
A [FreedzHost](https://freedzhost.cloud) project.
