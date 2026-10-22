"""purrd command-line interface.

Examples:
    purrd make -j8                # plays during the build; silence = done
    purrd cargo test              # same for any command
    purrd --seed 3 ./deploy.sh    # a different mood (the seed changes the melody)
    purrd demo                    # preview the loop (Ctrl-C to stop)
    purrd start / purrd stop      # daemon mode, used by the Claude Code hooks

purrd options must come BEFORE the wrapped command.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading

# _env normalises XDG_RUNTIME_DIR / DBUS_SESSION_BUS_ADDRESS for PipeWire.
# The import has a side effect and must come before _paths / runner in the foreground.
from . import _env  # noqa: F401
from . import _paths, config, daemon, patterns, runner

_CONTROL = {"start", "stop", "stop-voice", "status", "demo", "say", "import-pack", "daemon", "bank"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="purrd",
        description="Background music while a long task runs; silence signals the end.",
    )
    p.add_argument("--bpm", type=int, default=None, help="tempo (default: 86)")
    p.add_argument(
        "--seconds", type=int, default=None, help="length of the looped track (default: 32)"
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="seed: changes the melody (default: use favorites, then 0)",
    )
    p.add_argument(
        "--style",
        "--mood",
        dest="style",
        choices=patterns.STYLE_NAMES,
        default=None,
        help=f"musical style / mood preset (default: {patterns.STYLE_NAMES[0]})",
    )
    p.add_argument("--volume", type=float, default=1.0, help="volume 0..1 (default: 1.0)")
    p.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing pack when importing",
    )
    p.add_argument(
        "--favorites",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use saved favorites when no explicit seed is given (default: true)",
    )
    p.add_argument(
        "--auto-variation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="rotate through random favorites on long sessions instead of looping one track (default: false)",
    )
    p.add_argument(
        "target",
        nargs="?",
        help="start | stop | demo | say | daemon, or the first word of the command to wrap",
    )
    p.add_argument("rest", nargs=argparse.REMAINDER, help="the rest of the command to wrap")
    return p


def main(argv: list[str] | None = None) -> int:
    _paths.migrate_legacy_packs()
    args = _build_parser().parse_args(argv)

    if args.target == "daemon":
        daemon.run_daemon()
        return 0

    if args.target == "stop":
        if daemon.daemon_available():
            daemon.send_command({"cmd": "stop"})
        else:
            runner.stop()
        return 0

    if args.target == "stop-voice":
        if daemon.daemon_available():
            daemon.send_command({"cmd": "stop-voice"})
        else:
            from .voice import stop_voice

            stop_voice()
        return 0

    if args.target == "status":
        if daemon.daemon_available():
            resp = daemon.send_command({"cmd": "status"})
            running = bool(resp.get("result"))
        else:
            running = runner.is_running()
        if running:
            print("purrd is running")
            return 0
        print("purrd is not running")
        return 1

    if args.target == "start":
        if daemon.daemon_available():
            daemon.send_command(
                {
                    "cmd": "start",
                    "bpm": args.bpm,
                    "seconds": args.seconds,
                    "seed": args.seed,
                    "volume": args.volume,
                    "style": args.style,
                    "use_favorites": args.favorites,
                    "auto_variation": args.auto_variation,
                }
            )
        else:
            runner.start(
                args.bpm,
                args.seconds,
                args.seed,
                args.volume,
                style=args.style,
                use_favorites=args.favorites,
                auto_variation=args.auto_variation,
            )
        return 0

    if args.target == "demo":
        from . import favorites
        from .player import play_loop, to_pcm16
        from .sequencer import build_track

        rbpm, rseconds, rseed, rstyle = favorites.resolve_params(
            args.bpm, args.seconds, args.seed, style=args.style, use_favorites=args.favorites
        )
        stop = threading.Event()
        pcm = to_pcm16(build_track(rseconds, rbpm, rseed, args.volume, style=rstyle))
        try:
            play_loop(pcm, stop)
        except KeyboardInterrupt:
            stop.set()
        return 0

    if args.target == "say":
        event = args.rest[0] if args.rest else None
        if not event:
            print("Usage: purrd say <event>", file=sys.stderr)
            return 1
        if daemon.daemon_available():
            daemon.send_command({"cmd": "say", "event": event})
        else:
            from .voice import play_event

            try:
                proc = play_event(event)
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
            if proc is not None:
                try:
                    proc.wait(timeout=10.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        return 0

    if args.target == "import-pack":
        from pathlib import Path

        from . import cesp

        # Accept "purrd import-pack [--force] <dir>" regardless of flag order.
        tokens = args.rest
        force = args.force or "--force" in tokens
        source = next((t for t in tokens if t != "--force"), None)
        if not source:
            print("Usage: purrd import-pack [--force] <source-dir>", file=sys.stderr)
            return 1
        try:
            pack = cesp.import_pack(Path(source), force=force)
            cesp.set_active_pack(pack.name)
            print(f"Imported and activated pack: {pack.display_name}")
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        return 0

    if args.target == "bank":
        from . import bank

        tokens = args.rest
        if tokens and tokens[0] == "ratio":
            raw = tokens[1] if len(tokens) > 1 else None
            if raw is None:
                print("Usage: purrd bank ratio <0.0..1.0>", file=sys.stderr)
                return 1
            try:
                value = float(raw)
            except ValueError:
                print(f"Error: {raw!r} is not a valid float", file=sys.stderr)
                return 1
            value = max(0.0, min(1.0, value))
            cfg = config.load()
            cfg.setdefault("bank", {})["ratio"] = value
            config.save(cfg)
            print(value)
            return 0
        print(_paths.bank_dir())
        print(f"tracks: {len(bank.list_bank())}")
        print(f"ratio: {bank.bank_ratio()}")
        return 0

    cmd = ([args.target] if args.target else []) + args.rest
    if not cmd:
        _build_parser().print_help()
        return 1
    return runner.run_with_music(
        cmd,
        args.bpm,
        args.seconds,
        args.seed,
        args.volume,
        style=args.style,
        use_favorites=args.favorites,
        auto_variation=args.auto_variation,
    )


if __name__ == "__main__":
    sys.exit(main())
