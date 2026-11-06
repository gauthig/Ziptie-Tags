"""Smoke test of the window (needs a display; skipped when Tk is unavailable)."""
from __future__ import annotations

import tkinter as tk

import pytest

from ziptag.app import App


@pytest.fixture
def app():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    widget = App(root)
    widget.pack()
    yield widget
    root.destroy()


def test_defaults_and_status(app):
    app.update_idletasks()
    assert app.summary_var.get().startswith("2 tags -> 1 plate")
    dims = app.dims_var.get()
    assert " mm" in dims and " cm" in dims and " in" in dims


def test_tag_count_limits_and_grid_resize(app):
    app.count_var.set(99)
    app._count_changed()
    assert len(app.grid_widget.rows) == 40
    app.count_var.set(0)
    app._count_changed()
    assert len(app.grid_widget.rows) == 1


def test_per_row_validation(app):
    app.grid_widget.rows[0].size = "abc"
    _, errors = app.build_specs()
    assert errors[0] and not errors[1]


def test_nozzle_only_for_dual_nozzle_printers(app):
    app.printer_var.set("Bambu Lab A1")
    assert str(app.nozzle_box.cget("state")) == "disabled"
    app.printer_var.set("Bambu Lab H2D")
    assert str(app.nozzle_box.cget("state")) == "readonly"


def test_paste_adds_rows(app):
    app.clipboard_clear()
    app.clipboard_append("A\t80\tLeft\nB\nC\t\tRight")
    app.grid_widget.select(0)
    app.grid_widget._paste(None)
    rows = app.grid_widget.rows
    assert [r.text for r in rows[:3]] == ["A", "B", "C"]
    assert rows[0].size == "80" and rows[0].align == "Left" and rows[2].align == "Right"


def test_generate_buttons_and_no_file_menu(app):
    assert app.mf_button.cget("text") == "Generate 3MF" and app.stl_button.cget("text") == "Generate STL"
    menu = app.master.nametowidget(app.master.cget("menu"))
    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]
    assert "File" not in labels
