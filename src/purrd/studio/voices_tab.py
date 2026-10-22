"""Voices tab for the purrd studio — CESP pack manager."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from typing import Any

import gi

from purrd.studio import logic
from purrd.voice import _play_wav

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402


class VoicesTab(Gtk.Box):
    """Manage CESP voice packs: import, select active pack, preview events."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._stop_preview = threading.Event()
        self._current_player: subprocess.Popen | None = None

        # --- active pack ---
        active_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        active_box.append(Gtk.Label(label="Active voice pack"))

        self.active_label = Gtk.Label(label="No active pack", xalign=0)
        active_box.append(self.active_label)

        self.pack_dropdown = Gtk.DropDown()
        active_box.append(self.pack_dropdown)

        self.set_active_btn = Gtk.Button(label="Set as active")
        self.set_active_btn.connect("clicked", self._on_set_active)
        active_box.append(self.set_active_btn)

        self.append(active_box)

        # --- installed packs list ---
        packs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        packs_box.append(Gtk.Label(label="Installed packs"))
        self.installed_list = Gtk.ListBox()
        packs_box.append(self.installed_list)
        self.append(packs_box)

        # --- import from templates ---
        templates_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        templates_box.append(Gtk.Label(label="Templates"))

        self.template_dropdown = Gtk.DropDown()
        templates_box.append(self.template_dropdown)

        self.import_template_btn = Gtk.Button(label="Import template")
        self.import_template_btn.connect("clicked", self._on_import_template)
        templates_box.append(self.import_template_btn)

        self.append(templates_box)

        # --- import from custom directory ---
        custom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        custom_box.append(Gtk.Label(label="Import custom pack"))

        custom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.custom_path = Gtk.Entry()
        self.custom_path.set_placeholder_text("/path/to/pack")
        self.custom_path.set_hexpand(True)
        custom_row.append(self.custom_path)

        self.browse_btn = Gtk.Button(label="Browse…")
        self.browse_btn.connect("clicked", self._on_browse)
        custom_row.append(self.browse_btn)
        custom_box.append(custom_row)

        self.import_custom_btn = Gtk.Button(label="Import custom pack")
        self.import_custom_btn.connect("clicked", self._on_import_custom)
        custom_box.append(self.import_custom_btn)

        self.append(custom_box)

        # --- preview ---
        preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        preview_box.append(Gtk.Label(label="Preview"))

        self.event_dropdown = Gtk.DropDown()
        self.event_dropdown.set_model(Gtk.StringList.new(list(logic.VOICE_EVENTS)))
        preview_box.append(self.event_dropdown)

        self.preview_btn = Gtk.Button(label="Play selected event")
        self.preview_btn.connect("clicked", self._on_preview)
        preview_box.append(self.preview_btn)

        self.mute_btn = Gtk.Button(label="Mute")
        self.mute_btn.connect("clicked", self._on_mute)
        preview_box.append(self.mute_btn)

        self.append(preview_box)

        # --- feedback ---
        self.feedback = Gtk.Label(label="", xalign=0)
        self.append(self.feedback)

        self._refresh_packs()

    def _refresh_packs(self) -> None:
        """Reload installed packs, templates, and active selection."""
        self.installed_packs = logic.list_installed_packs()
        templates = logic.list_template_packs()

        installed_names = [p.display_name for p in self.installed_packs]
        self.pack_dropdown.set_model(Gtk.StringList.new(installed_names))

        self.installed_list.remove_all()
        for pack in self.installed_packs:
            label = f"{pack.display_name} ({pack.name})"
            self.installed_list.append(Gtk.Label(label=label))

        template_names = [p.display_name for p in templates]
        self.template_dropdown.set_model(Gtk.StringList.new(template_names))
        self._templates = templates

        active = logic.get_active_pack()
        if active is not None:
            self.active_label.set_text(f"Active: {active.display_name}")
            try:
                idx = installed_names.index(active.display_name)
                self.pack_dropdown.set_selected(idx)
            except ValueError:
                pass
        else:
            self.active_label.set_text("No active pack")

    def _set_feedback(self, message: str) -> None:
        """Update the feedback label."""
        self.feedback.set_text(message)

    def _on_set_active(self, _btn: Gtk.Button) -> None:
        """Set the selected installed pack as active."""
        idx = self.pack_dropdown.get_selected()
        if idx >= len(self.installed_packs):
            self._set_feedback("No pack selected.")
            return
        pack = self.installed_packs[idx]
        logic.set_active_pack(pack.name)
        self.active_label.set_text(f"Active: {pack.display_name}")
        self._set_feedback(f"Activated {pack.display_name}.")

    def _on_import_template(self, _btn: Gtk.Button) -> None:
        """Import the selected template pack."""
        idx = self.template_dropdown.get_selected()
        if idx >= len(self._templates):
            self._set_feedback("No template selected.")
            return
        pack = self._templates[idx]
        try:
            imported = logic.import_pack(pack.pack_dir)
            logic.set_active_pack(imported.name)
            self._refresh_packs()
            self._set_feedback(f"Imported and activated {imported.display_name}.")
        except Exception as exc:  # noqa: BLE001
            self._set_feedback(f"Import failed: {exc}")

    def _on_browse(self, _btn: Gtk.Button) -> None:
        """Open a folder chooser for a custom CESP pack."""
        dialog = Gtk.FileDialog(title="Select CESP pack directory")
        window = self.get_root()
        dialog.select_folder(window, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: Any) -> None:
        """Fill the custom path entry with the chosen directory."""
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        if folder is not None:
            self.custom_path.set_text(folder.get_path())

    def _on_import_custom(self, _btn: Gtk.Button) -> None:
        """Import a pack from the custom path entry."""
        text = self.custom_path.get_text().strip()
        if not text:
            self._set_feedback("Enter a pack directory.")
            return
        path = Path(text)
        if not path.exists():
            self._set_feedback(f"Directory not found: {path}")
            return
        try:
            imported = logic.import_pack(path)
            logic.set_active_pack(imported.name)
            self._refresh_packs()
            self._set_feedback(f"Imported and activated {imported.display_name}.")
        except Exception as exc:  # noqa: BLE001
            self._set_feedback(f"Import failed: {exc}")

    def _on_preview(self, _btn: Gtk.Button) -> None:
        """Play a preview of the selected event from the active pack."""
        event_idx = self.event_dropdown.get_selected()
        event = logic.VOICE_EVENTS[event_idx]
        path = logic.preview_sound_for_event(event)
        if path is None:
            self._set_feedback(f"No sound for {event} in active pack.")
            return
        self._stop_preview.set()
        self._stop_preview = threading.Event()
        thread = threading.Thread(
            target=self._play_sound,
            args=(path, self._stop_preview),
            daemon=True,
        )
        thread.start()
        self._set_feedback(f"Playing {event}.")

    def _play_sound(self, path: Path, stop: threading.Event) -> None:
        """Stream a WAV sample to the system player."""
        self._current_player = _play_wav(path)
        while self._current_player.poll() is None:
            if stop.is_set():
                self._current_player.terminate()
                break
            stop.wait(0.1)
        self._current_player = None

    def _on_mute(self, _btn: Gtk.Button) -> None:
        """Stop any currently playing preview."""
        self._stop_preview.set()
        if self._current_player is not None:
            self._current_player.terminate()
            self._current_player = None
        self._set_feedback("Playback stopped.")
