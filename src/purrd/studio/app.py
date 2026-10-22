"""GTK4 studio application entry point for purrd."""

from __future__ import annotations

import os
import subprocess

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from purrd.studio.music_tab import MusicTab  # noqa: E402
from purrd.studio.voices_tab import VoicesTab  # noqa: E402


def _purrd_bin() -> str:
    """Return the purrd binary to control from the studio."""
    return os.environ.get("PURRD", "purrd")


def _is_purrd_running() -> bool:
    """Return True if the purrd daemon reports it is active."""
    try:
        result = subprocess.run(
            [_purrd_bin(), "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0 and "running" in result.stdout.lower()
    except FileNotFoundError:
        return False


class StudioWindow(Gtk.ApplicationWindow):
    """Main studio window with Voices and Music explorer tabs."""

    def __init__(self, app: Gtk.Application) -> None:
        super().__init__(application=app, title="purrd studio")
        self.set_default_size(800, 600)

        # Follow the system dark/light preference.
        settings = Gtk.Settings.get_default()
        if settings is not None:
            self._apply_theme(settings)
            settings.connect("notify::gtk-theme-name", self._on_theme_changed)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_vexpand(True)
        vbox.set_hexpand(True)
        self.set_child(vbox)

        # --- global control bar ---
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(8)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        self.start_btn = Gtk.Button(label="▶ Start purrd")
        self.start_btn.connect("clicked", self._on_start)
        toolbar.append(self.start_btn)

        self.stop_btn = Gtk.Button(label="⏹ Stop purrd")
        self.stop_btn.connect("clicked", self._on_stop)
        toolbar.append(self.stop_btn)

        self.status_label = Gtk.Label(label="Idle")
        self.status_label.set_hexpand(True)
        self.status_label.set_xalign(0)
        toolbar.append(self.status_label)

        vbox.append(toolbar)

        notebook = Gtk.Notebook()
        notebook.set_margin_top(12)
        notebook.set_margin_bottom(12)
        notebook.set_margin_start(12)
        notebook.set_margin_end(12)
        notebook.set_vexpand(True)
        notebook.set_hexpand(True)

        self.voices_tab = VoicesTab()
        self.music_tab = MusicTab()

        notebook.append_page(self.voices_tab, Gtk.Label(label="Voices"))
        notebook.append_page(self.music_tab, Gtk.Label(label="Music explorer"))

        vbox.append(notebook)

        # Poll the daemon state so the buttons stay accurate even when purrd is
        # controlled from outside the studio (CLI, hooks, etc.).
        self._poll_id: int | None = None
        self._update_button_state()
        self._schedule_poll()

    def _apply_theme(self, settings: Gtk.Settings) -> None:
        """Enable dark theme when the current GTK theme name suggests it."""
        theme = settings.get_property("gtk-theme-name") or ""
        prefer_dark = "dark" in theme.lower()
        settings.set_property("gtk-application-prefer-dark-theme", prefer_dark)

    def _on_theme_changed(self, settings: Gtk.Settings, _pspec: object) -> None:
        self._apply_theme(settings)

    def _update_button_state(self) -> None:
        running = _is_purrd_running()
        self.start_btn.set_sensitive(not running)
        self.stop_btn.set_sensitive(running)
        self.status_label.set_text("Running" if running else "Idle")

    def _schedule_poll(self) -> None:
        """Re-arm the periodic state refresh."""
        if self._poll_id is not None:
            GLib.source_remove(self._poll_id)
        self._poll_id = GLib.timeout_add_seconds(1, self._on_poll)

    def _on_poll(self) -> bool:
        """Refresh button state every second; returns True to keep polling."""
        self._update_button_state()
        return True

    def _on_start(self, _btn: Gtk.Button) -> None:
        """Start the purrd background daemon."""
        subprocess.run([_purrd_bin(), "start"], check=False)
        # Refresh immediately, then keep the periodic refresh alive.
        self._update_button_state()
        self._schedule_poll()

    def _on_stop(self, _btn: Gtk.Button) -> None:
        """Stop the purrd background daemon and any playing voice sample."""
        subprocess.run([_purrd_bin(), "stop"], check=False)
        subprocess.run([_purrd_bin(), "stop-voice"], check=False)
        self._update_button_state()
        self._schedule_poll()

    def do_close_request(self) -> bool:  # noqa: N802
        """Clean up the polling timer when the window closes."""
        if self._poll_id is not None:
            GLib.source_remove(self._poll_id)
            self._poll_id = None
        return False


class StudioApp(Gtk.Application):
    """GTK4 application wrapper."""

    def __init__(self) -> None:
        super().__init__(
            application_id="cloud.freedzhost.purrd.studio",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

    def do_activate(self) -> None:  # noqa: N802
        window = StudioWindow(self)
        window.present()


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``purrd-studio``."""
    app = StudioApp()
    return app.run(argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
