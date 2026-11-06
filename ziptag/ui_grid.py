"""Spreadsheet-style entry grid: one row per tag, editable in place."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk

from ziptag.constants import MAX_TAGS

ALIGN_CHOICES = ("", "Left", "Center", "Right")     # "" = use the default alignment
BLANK_LABEL = {"size": "Auto", "align": "(default)"}
COLUMNS = ("n", "text", "size", "align", "status")
HEADINGS = {"n": "#", "text": "Tag text", "size": "Text size %", "align": "Align", "status": "Status"}
WIDTHS = {"n": 40, "text": 260, "size": 90, "align": 80, "status": 420}
EDITABLE = ("text", "size", "align")


@dataclass
class RowData:
    """One tag row as typed by the user (strings, validated by the app)."""

    text: str = ""
    size: str = ""       # blank = Auto-fit
    align: str = ""      # blank = default alignment


class SpreadsheetGrid(ttk.Frame):
    """A Treeview with in-place cell editing, keyboard navigation and Excel paste."""

    def __init__(self, master, on_edit: Callable[[], None], on_select: Callable[[int], None],
                 on_count_change: Callable[[int], None]):
        super().__init__(master)
        self._on_edit, self._on_select, self._on_count_change = on_edit, on_select, on_count_change
        self._rows: list[RowData] = []
        self._editor: tk.Widget | None = None
        self._edit_pos: tuple[int, str] | None = None

        self.tree = ttk.Treeview(self, columns=COLUMNS, show="headings", selectmode="browse", height=10)
        for col in COLUMNS:
            self.tree.heading(col, text=HEADINGS[col])
            self.tree.column(col, width=WIDTHS[col], anchor="w" if col in ("text", "status") else "center",
                             stretch=col == "status")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree.tag_configure("warn", background="#fde8e8")
        self.tree.tag_configure("note", foreground="#555555")
        self.tree.bind("<ButtonRelease-1>", self._on_click)
        self.tree.bind("<<TreeviewSelect>>", self._selected)
        self.tree.bind("<Return>", lambda _e: self._begin_edit_selected("text"))
        self.tree.bind("<F2>", lambda _e: self._begin_edit_selected("text"))
        self.tree.bind("<Control-v>", self._paste)
        self.tree.bind("<Key>", self._typed)

    # ---- public API ------------------------------------------------------------------
    @property
    def rows(self) -> list[RowData]:
        return self._rows

    def set_row_count(self, count: int) -> None:
        """Grow or shrink the grid, keeping what was already typed."""
        count = max(1, min(MAX_TAGS, count))
        rows = self._rows[:count] + [RowData() for _ in range(count - len(self._rows))]
        self.set_rows(rows)

    def set_rows(self, rows: list[RowData]) -> None:
        """Replace the grid contents."""
        self._end_edit(commit=True)
        self._rows = rows[:MAX_TAGS] or [RowData()]
        self.tree.delete(*self.tree.get_children())
        for i in range(len(self._rows)):
            self.tree.insert("", "end", iid=str(i), values=self._values(i))

    def set_status(self, index: int, message: str, warn: bool) -> None:
        if str(index) in self.tree.get_children():
            self.tree.set(str(index), "status", ("⚠ " if warn else "") + message)
            tags = ("warn",) if warn else (("note",) if message not in ("OK", "") else ())
            self.tree.item(str(index), tags=tags)

    def selected_index(self) -> int:
        sel = self.tree.selection()
        return int(sel[0]) if sel else 0

    def select(self, index: int) -> None:
        self.tree.selection_set(str(index))
        self.tree.see(str(index))

    # ---- editing ---------------------------------------------------------------------
    def _values(self, i: int) -> tuple:
        row = self._rows[i]
        return (i + 1, row.text, self._shown(row, "size"), self._shown(row, "align"), "")

    @staticmethod
    def _shown(row: RowData, col: str) -> str:
        """Cell text; empty size/align cells show what blank means."""
        value = getattr(row, col)
        return value if value or col == "text" else BLANK_LABEL[col]

    def _refresh_row(self, index: int) -> None:
        for col in EDITABLE:
            self.tree.set(str(index), col, self._shown(self._rows[index], col))

    def _on_click(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        item = self.tree.identify_row(event.y)
        col = COLUMNS[int(self.tree.identify_column(event.x)[1:]) - 1]
        if item and col in EDITABLE:
            self._begin_edit(int(item), col)

    def _selected(self, _event) -> None:
        self._on_select(self.selected_index())

    def _typed(self, event) -> None:
        if event.char and event.char.isprintable() and not (event.state & 0x4) and self.tree.selection():
            self._begin_edit_selected("text", initial=event.char)

    def _begin_edit_selected(self, col: str, initial: str | None = None) -> str:
        if self.tree.selection():
            self._begin_edit(self.selected_index(), col, initial)
        return "break"

    def _begin_edit(self, index: int, col: str, initial: str | None = None) -> None:
        self._end_edit(commit=True)
        item = str(index)
        self.tree.selection_set(item)
        self.tree.see(item)
        self.update_idletasks()
        bbox = self.tree.bbox(item, col)
        if not bbox:
            return
        current = getattr(self._rows[index], col)
        if col == "align":
            choices = [BLANK_LABEL["align"], *ALIGN_CHOICES[1:]]
            editor: tk.Widget = ttk.Combobox(self.tree, values=choices, state="readonly")
            editor.set(current or BLANK_LABEL["align"])
        else:
            editor = ttk.Entry(self.tree)
            editor.insert(0, current if initial is None else initial)
        editor.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        editor.focus_set()
        if isinstance(editor, ttk.Entry):
            editor.icursor("end")
        editor.bind("<Return>", lambda _e: self._finish(down=True))
        editor.bind("<Tab>", lambda _e: self._finish(next_col=True))
        editor.bind("<Escape>", lambda _e: self._end_edit(commit=False))
        editor.bind("<FocusOut>", lambda _e: self._end_edit(commit=True))
        editor.bind("<<ComboboxSelected>>", lambda _e: self._finish())
        self._editor, self._edit_pos = editor, (index, col)

    def _finish(self, down: bool = False, next_col: bool = False) -> str:
        """Commit the open editor, then move: Enter = same column next row, Tab = next cell."""
        pos = self._edit_pos
        self._end_edit(commit=True)
        if pos:
            index, col = pos
            if next_col:
                at = EDITABLE.index(col)
                if at + 1 < len(EDITABLE):
                    self._begin_edit(index, EDITABLE[at + 1])
                elif index + 1 < len(self._rows):
                    self._begin_edit(index + 1, EDITABLE[0])
            elif down and index + 1 < len(self._rows):
                self._begin_edit(index + 1, col)
        return "break"

    def _end_edit(self, commit: bool) -> None:
        editor, pos = self._editor, self._edit_pos
        self._editor = self._edit_pos = None
        if editor is None or pos is None:
            return
        value = editor.get() if commit else None
        editor.destroy()
        if value is not None:
            index, col = pos
            value = value if col == "text" else value.strip()
            if col == "align" and value not in ALIGN_CHOICES:
                value = ""                                   # "(default)"
            if col == "size" and value.lower() in ("auto", "%"):
                value = ""
            setattr(self._rows[index], col, value.rstrip("%"))
            self._refresh_row(index)
            self._on_edit()

    # ---- clipboard -------------------------------------------------------------------
    def _paste(self, _event) -> str:
        """Paste tab/newline separated cells (e.g. copied from Excel) starting at the selection."""
        try:
            data = self.clipboard_get()
        except tk.TclError:
            return "break"
        lines = [ln for ln in data.replace("\r", "").split("\n")]
        while lines and not lines[-1].strip():
            lines.pop()
        if not lines:
            return "break"
        self._end_edit(commit=True)
        start = self.selected_index() if self.tree.selection() else 0
        needed = min(MAX_TAGS, start + len(lines))
        if needed > len(self._rows):
            self.set_row_count(needed)
            self._on_count_change(needed)
        for offset, line in enumerate(lines):
            if start + offset >= len(self._rows):
                break
            cells = line.split("\t")
            row = self._rows[start + offset]
            row.text = cells[0]
            if len(cells) > 1:
                size = cells[1].strip().rstrip("%")
                row.size = "" if size.lower() == "auto" else size
            if len(cells) > 2:
                row.align = cells[2].strip().capitalize() if cells[2].strip().capitalize() in ALIGN_CHOICES else ""
            self._refresh_row(start + offset)
        self._on_edit()
        return "break"
