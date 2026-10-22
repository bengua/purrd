"""Music explorer tab for the purrd studio."""

from __future__ import annotations

import threading
import time
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from purrd import patterns  # noqa: E402
from purrd.studio import ai_bank  # noqa: E402
from purrd.studio.logic import (  # noqa: E402
    add_favorite,
    generate_loop_presets,
    list_favorites,
    preview_loop_params,
    remove_favorite,
)


class MusicTab(Gtk.Box):
    """Generate loops, keep/discard them, and manage saved favorites."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._volume = 1.0
        self._stop_preview = threading.Event()
        self._current_candidates: list[dict[str, Any]] = []
        self._gen_thread: threading.Thread | None = None
        self._ai_thread: threading.Thread | None = None

        # --- generation settings ---
        settings = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        settings.append(Gtk.Label(label="Generator settings"))

        self._count_spin = self._spin_row("Count", 1, 50, 10)
        self._bpm_min_spin = self._spin_row("BPM min", 40, 200, 78)
        self._bpm_max_spin = self._spin_row("BPM max", 40, 200, 92)
        self._seconds_spin = self._spin_row("Seconds", 4, 120, 32)
        self._style_drop = self._drop_down_row("Style", list(patterns.STYLE_NAMES), selected=0)
        settings.append(self._count_spin)
        settings.append(self._bpm_min_spin)
        settings.append(self._bpm_max_spin)
        settings.append(self._seconds_spin)
        settings.append(self._style_drop)

        volume_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_row.append(Gtk.Label(label="Preview volume", width_chars=14, xalign=0))
        vol_adj = Gtk.Adjustment(value=1.0, lower=0.0, upper=1.0, step_increment=0.05)
        self._volume_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=vol_adj)
        self._volume_slider.set_digits(2)
        self._volume_slider.set_hexpand(True)
        self._volume_slider.connect("value-changed", self._on_volume_changed)
        volume_row.append(self._volume_slider)
        settings.append(volume_row)

        progress_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        progress_row.append(Gtk.Label(label="Progress", width_chars=14, xalign=0))
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_hexpand(True)
        self._progress_bar.set_show_text(True)
        self._progress_bar.set_text("Ready")
        progress_row.append(self._progress_bar)
        settings.append(progress_row)

        self.append(settings)

        # --- top controls ---
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.generate_btn = Gtk.Button(label="Generate")
        self.generate_btn.connect("clicked", self._on_generate)
        controls.append(self.generate_btn)

        self.mute_btn = Gtk.Button(label="Mute")
        self.mute_btn.connect("clicked", self._on_mute)
        controls.append(self.mute_btn)

        self.append(controls)

        # --- AI bank (optional generation server, PURRD_AI_URL) ---
        ai = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ai.append(Gtk.Separator())
        ai.append(
            Gtk.Label(label="AI bank — generated instrumentals (optional server)", xalign=0)
        )
        self._ai_prompt = Gtk.Entry()
        self._ai_prompt.set_placeholder_text("optional prompt (e.g. warm analog, rainy night)")
        ai.append(self._ai_prompt)
        self._ai_count = self._spin_row("Count (per style)", 1, 200, 20)
        ai.append(self._ai_count)
        ai_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.ai_generate_btn = Gtk.Button(label="Generate via AI")
        self.ai_generate_btn.connect("clicked", self._on_ai_generate)
        ai_controls.append(self.ai_generate_btn)
        ai.append(ai_controls)
        if ai_bank.enabled():
            hint = "The style selected above sets the tags."
        else:
            hint = f"Disabled: set {ai_bank.ENV_VAR} to a generation server URL."
            self.ai_generate_btn.set_sensitive(False)
        self._ai_status = Gtk.Label(label=hint, xalign=0)
        ai.append(self._ai_status)
        self.append(ai)

        # --- candidates list ---
        self.candidates_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.append(Gtk.Label(label="Candidates"))
        self.append(self.candidates_box)

        # --- favorites list ---
        self.append(Gtk.Separator())
        self.append(Gtk.Label(label="Favourites"))
        self.favorites_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.append(self.favorites_box)
        self._refresh_favorites()

    def _spin_row(self, label: str, low: int, high: int, value: int) -> Gtk.Box:
        """Return a labeled spin button row."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(Gtk.Label(label=label, width_chars=14, xalign=0))
        adj = Gtk.Adjustment(value=value, lower=low, upper=high, step_increment=1)
        spin = Gtk.SpinButton(adjustment=adj)
        spin.set_numeric(True)
        row.append(spin)
        return row

    def _spin_value(self, row: Gtk.Box) -> int:
        """Extract the current value from a spin row."""
        for child in [row.get_first_child(), row.get_last_child()]:
            if isinstance(child, Gtk.SpinButton):
                return int(child.get_value())
        return 0

    def _drop_down_row(self, label: str, values: list[str], selected: int = 0) -> Gtk.Box:
        """Return a labeled drop-down row."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(Gtk.Label(label=label, width_chars=14, xalign=0))
        dropdown = Gtk.DropDown(model=Gtk.StringList.new(values), selected=selected)
        row.append(dropdown)
        return row

    def _drop_down_value(self, row: Gtk.Box) -> str:
        """Extract the current value from a drop-down row."""
        for child in [row.get_first_child(), row.get_last_child()]:
            if isinstance(child, Gtk.DropDown):
                model = child.get_model()
                return model.get_string(child.get_selected())
        return "classic"

    def _on_volume_changed(self, slider: Gtk.Scale) -> None:
        """Update preview volume."""
        self._volume = slider.get_value()

    def _on_mute(self, _btn: Gtk.Button) -> None:
        """Stop any currently playing preview."""
        self._stop_preview.set()

    def _on_generate(self, _btn: Gtk.Button) -> None:
        """Generate new candidates with current settings in a background thread."""
        if self._gen_thread is not None and self._gen_thread.is_alive():
            return

        count = self._spin_value(self._count_spin)
        bpm_min = self._spin_value(self._bpm_min_spin)
        bpm_max = self._spin_value(self._bpm_max_spin)
        seconds = self._spin_value(self._seconds_spin)
        style = self._drop_down_value(self._style_drop)

        if bpm_min > bpm_max:
            bpm_min, bpm_max = bpm_max, bpm_min

        style_pool: tuple[str, ...] | None = None
        if style != "classic":
            style_pool = (style,)

        self._clear_candidates()
        self.generate_btn.set_sensitive(False)
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("Generating…")

        self._gen_thread = threading.Thread(
            target=self._generate_worker,
            args=(count, bpm_min, bpm_max, seconds, style_pool),
            daemon=True,
        )
        self._gen_thread.start()

    def _generate_worker(
        self,
        count: int,
        bpm_min: int,
        bpm_max: int,
        seconds: int,
        style_pool: tuple[str, ...] | None,
    ) -> None:
        """Run generation and schedule UI updates on the GTK main thread."""
        candidates = generate_loop_presets(
            count=count,
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            seconds=seconds,
            style_pool=style_pool,
            progress=lambda done, total: GLib.idle_add(self._update_progress, done, total),
        )
        GLib.idle_add(self._finish_generation, candidates)

    def _update_progress(self, done: int, total: int) -> bool:
        """Update the progress bar fraction.

        Returns False so GLib.idle_add does not reschedule automatically.
        """
        fraction = done / total if total > 0 else 0.0
        self._progress_bar.set_fraction(fraction)
        self._progress_bar.set_text(f"Generating {done}/{total}")
        return False

    def _finish_generation(self, candidates: list[dict[str, Any]]) -> bool:
        """Populate the candidates list after generation finishes."""
        self._current_candidates = candidates
        for preset in self._current_candidates:
            row = self._build_candidate_row(preset)
            self.candidates_box.append(row)
        self._progress_bar.set_text("Done")
        self.generate_btn.set_sensitive(True)
        self._gen_thread = None
        return False

    def _on_ai_generate(self, _btn: Gtk.Button) -> None:
        """Ask the generation server to generate `count` instrumental tracks for the selected
        style into the bank, then follow the job."""
        if self._ai_thread is not None and self._ai_thread.is_alive():
            return
        style = self._drop_down_value(self._style_drop)
        count = self._spin_value(self._ai_count)
        prompt = self._ai_prompt.get_text()
        self.ai_generate_btn.set_sensitive(False)
        self._ai_set_status(f"Sending to the generation server… ({style} ×{count})")
        self._ai_thread = threading.Thread(
            target=self._ai_worker,
            args=(style, count, prompt),
            daemon=True,
        )
        self._ai_thread.start()

    def _ai_worker(self, style: str, count: int, prompt: str) -> None:
        """Submit the generation and poll the job to done, on a background thread."""
        try:
            job = ai_bank.request_generation(style, count, prompt)
        except Exception as exc:  # noqa: BLE001 — surface the reason in the UI
            GLib.idle_add(self._ai_finish, f"Sending failed: {exc}")
            return
        jid = job.get("id", "")
        while jid:
            try:
                st = ai_bank.job_status(jid)
            except Exception:  # noqa: BLE001 — network hiccup: report it
                GLib.idle_add(self._ai_finish, "Tracking interrupted — check the generation server.")
                return
            status = st.get("status", "?")
            out = st.get("output") or ""
            GLib.idle_add(self._ai_set_status, f"{style}: {status} {out}")
            if status in ("done", "error"):
                GLib.idle_add(self._ai_finish, f"{style}: {status} {out}")
                return
            time.sleep(3)
        GLib.idle_add(self._ai_finish, "Job without an id — check the generation server.")

    def _ai_set_status(self, text: str) -> bool:
        self._ai_status.set_text(text)
        return False

    def _ai_finish(self, text: str) -> bool:
        self._ai_status.set_text(text)
        self.ai_generate_btn.set_sensitive(True)
        self._ai_thread = None
        return False

    def _clear_candidates(self) -> None:
        """Remove all candidate rows."""
        while (child := self.candidates_box.get_first_child()) is not None:
            self.candidates_box.remove(child)
        self._current_candidates = []

    def _build_candidate_row(self, preset: dict[str, Any]) -> Gtk.Box:
        """Row for a candidate preset with Play, Keep, Discard buttons."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        style = preset.get("style", "classic")
        label = Gtk.Label(
            label=(
                f"seed={preset['seed']}  bpm={preset['bpm']}  "
                f"seconds={preset['seconds']}  style={style}"
            ),
            xalign=0,
        )
        row.append(label)
        row.set_hexpand(True)

        play_btn = Gtk.Button(label="Play")
        play_btn.connect("clicked", self._on_play_preset, preset)
        row.append(play_btn)

        keep_btn = Gtk.Button(label="Keep ♥")
        keep_btn.connect("clicked", self._on_keep, preset, row)
        row.append(keep_btn)

        discard_btn = Gtk.Button(label="Discard")
        discard_btn.connect("clicked", self._on_discard, row)
        row.append(discard_btn)

        return row

    def _on_play_preset(self, _btn: Gtk.Button, preset: dict[str, Any]) -> None:
        """Preview a candidate or favorite asynchronously with progress."""
        self._stop_preview.set()
        self._stop_preview = threading.Event()
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_text("Rendering…")

        thread = threading.Thread(
            target=self._preview_worker,
            args=(preset, self._stop_preview),
            daemon=True,
        )
        thread.start()

    def _preview_worker(self, preset: dict[str, Any], stop: threading.Event) -> None:
        """Render the preview PCM and schedule playback on the GTK thread."""

        def report(done: int, total: int) -> None:
            if not stop.is_set():
                GLib.idle_add(self._update_progress, done, total)

        pcm = preview_loop_params(
            preset["seed"],
            preset["bpm"],
            preset["seconds"],
            volume=self._volume,
            style=preset.get("style"),
            progress=report,
        )
        if not stop.is_set():
            GLib.idle_add(self._start_playback, pcm, stop)

    def _start_playback(self, pcm: bytes, stop: threading.Event) -> bool:
        """Start playing rendered PCM in a background thread."""
        self._progress_bar.set_text("Playing")
        thread = threading.Thread(
            target=self._play_pcm,
            args=(pcm, stop),
            daemon=True,
        )
        thread.start()
        return False

    def _play_pcm(self, pcm: bytes, stop: threading.Event) -> None:
        """Play bytes through the system player."""
        from purrd.player import play_loop

        play_loop(pcm, stop)

    def _on_keep(
        self,
        _btn: Gtk.Button,
        preset: dict[str, Any],
        row: Gtk.Box,
    ) -> None:
        """Move a candidate to favorites."""
        add_favorite(preset["seed"], preset["bpm"], preset["seconds"], style=preset.get("style"))
        self.candidates_box.remove(row)
        self._refresh_favorites()

    def _on_discard(self, _btn: Gtk.Button, row: Gtk.Box) -> None:
        """Remove a candidate row."""
        self.candidates_box.remove(row)

    def _refresh_favorites(self) -> None:
        """Redraw the favorites list."""
        while (child := self.favorites_box.get_first_child()) is not None:
            self.favorites_box.remove(child)
        for fav in list_favorites():
            row = self._build_favorite_row(fav)
            self.favorites_box.append(row)

    def _build_favorite_row(self, fav: dict[str, Any]) -> Gtk.Box:
        """Row for a saved favorite with Play and Remove buttons."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        style = fav.get("style", "classic")
        label = Gtk.Label(
            label=(
                f"seed={fav['seed']}  bpm={fav['bpm']}  seconds={fav['seconds']}  style={style}"
            ),
            xalign=0,
        )
        row.append(label)
        row.set_hexpand(True)

        play_btn = Gtk.Button(label="Play")
        play_btn.connect("clicked", self._on_play_preset, fav)
        row.append(play_btn)

        remove_btn = Gtk.Button(label="Remove")
        remove_btn.connect("clicked", self._on_remove, fav, row)
        row.append(remove_btn)

        return row

    def _on_remove(
        self,
        _btn: Gtk.Button,
        fav: dict[str, Any],
        row: Gtk.Box,
    ) -> None:
        """Remove a saved favorite."""
        remove_favorite(fav["seed"], fav["bpm"], fav["seconds"], style=fav.get("style"))
        self.favorites_box.remove(row)
