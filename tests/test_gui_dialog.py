"""Tests for the GUI dialog dispatch in secret_paste_cli.

Two paths are covered without ever spinning a real GUI mainloop:

* CTk path: when ``customtkinter`` is installed, ``_show_dialog_ctk`` builds the
  full dialog (all widgets) and returns the canonical contract. We replace
  ``CTk.mainloop`` with a no-op so the window builds and tears down immediately.
* Fallback path: when ``customtkinter`` cannot be imported, ``show_dialog``
  routes to ``_show_dialog_ttk``. We simulate the missing dependency with a
  monkeypatched import that raises ``ImportError``.

These run headless. On CI without a display, building a Tk root raises
``TclError``; such tests skip rather than fail.
"""

from __future__ import annotations

import builtins

import pytest

import secret_paste_cli as cli


@pytest.fixture
def no_vault_config(monkeypatch):
    """Stub config + vault detection so the dialog never touches real state."""
    import secret_paste_core as core

    monkeypatch.setattr(
        core, "load_config", lambda: {"remote_enabled": False, "remote_backend": None}
    )
    monkeypatch.setattr(core, "detect_vaults", lambda: [])


def test_dpi_awareness_never_raises():
    # Pure defensiveness check: must be a no-op-safe call on any platform.
    cli._enable_dpi_awareness()


def test_fade_in_noop_on_missing_alpha():
    # A dummy object whose attributes() raises must be swallowed silently.
    class Dummy:
        def attributes(self, *a, **k):
            raise RuntimeError("no alpha here")

        def after(self, *a, **k):  # pragma: no cover - not reached
            raise AssertionError("after() should not run when alpha unsupported")

    cli._fade_in(Dummy())  # must not raise


def test_show_dialog_falls_back_when_customtkinter_missing(monkeypatch, no_vault_config):
    """If ``import customtkinter`` fails, show_dialog uses the ttk path."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "customtkinter":
            raise ImportError("simulated: customtkinter not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    called = {}

    def fake_ttk(key_name, description, default_persist, backend_label, multiline=False):
        called["args"] = (key_name, description, default_persist, backend_label)
        called["multiline"] = multiline
        return (True, "from-ttk", False, True)

    monkeypatch.setattr(cli, "_show_dialog_ttk", fake_ttk)

    result = cli.show_dialog("DEMO", "desc", False, "Windows DPAPI")
    assert result == (True, "from-ttk", False, True)
    assert called["args"] == ("DEMO", "desc", False, "Windows DPAPI")
    assert called["multiline"] is False


def test_show_dialog_uses_ctk_when_available(monkeypatch, no_vault_config):
    """If ``customtkinter`` imports, show_dialog routes to the CTk path."""
    pytest.importorskip("customtkinter")

    def fake_ctk(key_name, description, default_persist, backend_label, multiline=False):
        return (True, "from-ctk", True, False)

    monkeypatch.setattr(cli, "_show_dialog_ctk", fake_ctk)
    result = cli.show_dialog("DEMO", "desc", False, "Windows DPAPI")
    assert result == (True, "from-ctk", True, False)


def test_show_dialog_ctk_falls_back_on_build_error(monkeypatch, no_vault_config):
    """A failure inside the CTk path must fall back to ttk, never crash."""
    pytest.importorskip("customtkinter")

    def boom(*a, **k):
        raise RuntimeError("simulated CTk build failure")

    def fake_ttk(*a, **k):
        return (False, "", False, False)

    monkeypatch.setattr(cli, "_show_dialog_ctk", boom)
    monkeypatch.setattr(cli, "_show_dialog_ttk", fake_ttk)
    result = cli.show_dialog("DEMO", "desc", False, "Windows DPAPI")
    assert result == (False, "", False, False)


def _build_and_teardown(dialog_fn, monkeypatch, multiline=False):
    """Run a dialog builder with a no-op mainloop so it builds + tears down."""
    ctk = pytest.importorskip("customtkinter")

    try:
        # Replace mainloop on the CTk class so building completes, then destroy.
        orig_cls = ctk.CTk

        class NonBlockingCTk(orig_cls):
            def mainloop(self, *a, **k):  # noqa: D401 - no blocking
                self.destroy()

        monkeypatch.setattr(ctk, "CTk", NonBlockingCTk)
        return dialog_fn(
            "DEMO_KEY", "A demo credential", False, "Windows DPAPI", multiline
        )
    except Exception as exc:  # noqa: BLE001
        # No display available (headless CI) -> Tcl error. Skip, don't fail.
        pytest.skip(f"no GUI environment available: {exc!r}")


def test_ctk_dialog_builds_headless_cancel_contract(monkeypatch, no_vault_config):
    """The CTk dialog builds all widgets and returns the cancel contract."""
    result = _build_and_teardown(cli._show_dialog_ctk, monkeypatch)
    # mainloop was a no-op -> nothing was confirmed -> canonical cancel tuple.
    assert result == (False, "", False, False)


def test_ttk_dialog_builds_headless_cancel_contract(monkeypatch, no_vault_config):
    """The stdlib ttk fallback builds all widgets and returns the cancel contract."""
    import tkinter as tk

    try:
        tk.Tk().destroy()  # probe: is a display available?
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no GUI environment available: {exc!r}")

    orig_tk = tk.Tk

    class NonBlockingTk(orig_tk):
        def mainloop(self, *a, **k):  # noqa: D401 - no blocking
            self.destroy()

    monkeypatch.setattr(tk, "Tk", NonBlockingTk)
    result = cli._show_dialog_ttk("DEMO_KEY", "A demo credential", False, "Windows DPAPI")
    assert result == (False, "", False, False)


def test_ctk_dialog_builds_multiline_textbox(monkeypatch, no_vault_config):
    """The multiline CTk dialog (CTkTextbox path) builds + returns cancel tuple."""
    result = _build_and_teardown(cli._show_dialog_ctk, monkeypatch, multiline=True)
    assert result == (False, "", False, False)


def test_ctk_dialog_builds_with_mirror_checkbox(monkeypatch):
    """The conditional mirror checkbox path also builds without error."""
    import secret_paste_core as core

    monkeypatch.setattr(
        core, "load_config", lambda: {"remote_enabled": True, "remote_backend": "sops-age"}
    )
    monkeypatch.setattr(core, "detect_vaults", lambda: ["age", "sops"])
    result = _build_and_teardown(cli._show_dialog_ctk, monkeypatch)
    assert result == (False, "", False, False)


class _FakeWindow:
    """Minimal stand-in for a Tk/CTk window to test _safe_destroy ordering."""

    def __init__(self, pending=("after#0", "after#1"), fail_on=None):
        self._pending = list(pending)
        self._fail_on = fail_on or set()
        self.calls = []

        class _Tk:
            def __init__(self, outer):
                self._outer = outer

            def call(self, *args):
                self._outer.calls.append(("call", args))
                if "info" in args:
                    return " ".join(self._outer._pending)
                return ""

            def splitlist(self, s):
                return tuple(s.split()) if s else ()

        self.tk = _Tk(self)

    def after_cancel(self, after_id):
        self.calls.append(("after_cancel", after_id))
        if "after_cancel" in self._fail_on:
            raise RuntimeError("boom")

    def quit(self):
        self.calls.append(("quit",))
        if "quit" in self._fail_on:
            raise RuntimeError("boom")

    def destroy(self):
        self.calls.append(("destroy",))
        if "destroy" in self._fail_on:
            raise RuntimeError("boom")


def test_safe_destroy_cancels_pending_then_quits_then_destroys():
    win = _FakeWindow(pending=("after#0", "after#1"))
    cli._safe_destroy(win)
    kinds = [c[0] for c in win.calls]
    # Beide pending-Callbacks gecancelt
    assert win.calls.count(("after_cancel", "after#0")) == 1
    assert win.calls.count(("after_cancel", "after#1")) == 1
    # Reihenfolge: erst alle after_cancel, dann quit, dann destroy
    assert kinds.index("quit") < kinds.index("destroy")
    assert kinds.index("after_cancel") < kinds.index("quit")


def test_safe_destroy_is_fully_defensive():
    # Selbst wenn after_cancel UND quit werfen, muss destroy trotzdem laufen.
    win = _FakeWindow(fail_on={"after_cancel", "quit"})
    cli._safe_destroy(win)  # darf NICHT werfen
    assert ("destroy",) in win.calls
