"""Main window of the Ziptie Tags application."""
from __future__ import annotations

import contextlib
import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ziptag import __version__
from ziptag import constants as c
from ziptag.fonts import available_fonts, load_font
from ziptag.geometry import Align, FitStatus, TagSpec, dimensions, fit_text
from ziptag.help_text import INSTRUCTIONS
from ziptag.layout import LayoutError
from ziptag.printers import BAMBU_PRINTERS, Material, Nozzle, Printer, custom_printer, printer_by_label
from ziptag.project import JobOptions, build_job, build_stl, plan_plates
from ziptag.ui_grid import RowData, SpreadsheetGrid
from ziptag.ui_preview import TagPreview

OTHER_PRINTER = "Other printer (plain 3MF)"
DEFAULT_BED = 220.0
ALIGN_LABELS = {"Left": Align.LEFT, "Center": Align.CENTER, "Right": Align.RIGHT}
MM_PER_CM, MM_PER_INCH = 10.0, 25.4


class RowError(ValueError):
    """A grid row contains a value that cannot be used."""


class App(ttk.Frame):
    """The whole UI: settings on top, tag table in the middle, preview and Generate buttons."""

    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=10)
        self.master = master
        self.fonts = available_fonts()
        self._saving = False

        self.printer_var = tk.StringVar(value=BAMBU_PRINTERS[-1].label)       # H2D
        self.material_var = tk.StringVar(value=Material.PETG.value)
        self.nozzle_var = tk.StringVar(value=Nozzle.NORMAL.value)
        self.font_var = tk.StringVar(value="Roboto" if "Roboto" in self.fonts else next(iter(self.fonts)))
        self.align_var = tk.StringVar(value="Center")
        self.size_var = tk.IntVar(value=c.SIZE_DEFAULT_PCT)
        self.count_var = tk.IntVar(value=2)
        self.bed_x_var = tk.StringVar(value=f"{DEFAULT_BED:g}")
        self.bed_y_var = tk.StringVar(value=f"{DEFAULT_BED:g}")
        self.summary_var = tk.StringVar()
        self.dims_var = tk.StringVar()

        self._build_menu()
        self._build_widgets()
        self.grid_widget.set_rows([RowData("HEX BEAM"), RowData("VERTICAL")])
        self._printer_changed()
        self.grid_widget.select(0)
        self.refresh()

    # ---- construction ----------------------------------------------------------------
    def _build_menu(self) -> None:
        menu = tk.Menu(self.master)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Instructions", command=self.show_instructions)
        help_menu.add_command(label="About", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.master.configure(menu=menu)
        self.master.bind("<Control-s>", lambda _e: self.generate("3mf"))

    def _build_widgets(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        # -- header: title on the left, generate buttons on the right
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Zip-tie cable tag generator", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w")
        self.stl_button = ttk.Button(header, text="Generate STL", command=lambda: self.generate("stl"))
        self.stl_button.grid(row=0, column=2, padx=(8, 0))
        self.mf_button = ttk.Button(header, text="Generate 3MF", command=lambda: self.generate("3mf"))
        self.mf_button.grid(row=0, column=1, padx=(8, 0))

        # -- printer / material / nozzle
        box = ttk.LabelFrame(self, text="Printer and material", padding=8)
        box.grid(row=1, column=0, sticky="ew")
        printer_labels = [p.label for p in BAMBU_PRINTERS] + [OTHER_PRINTER]
        self._combo(box, "Printer", self.printer_var, printer_labels, 0, 0, 28)
        self.material_box = self._combo(box, "Material", self.material_var, [m.value for m in Material], 0, 2, 8)
        self.nozzle_box = self._combo(box, "Nozzle type", self.nozzle_var, [n.value for n in Nozzle], 0, 4, 10)
        self.bed_frame = ttk.Frame(box)
        ttk.Label(self.bed_frame, text="Bed size (mm)  X").pack(side="left")
        ttk.Entry(self.bed_frame, textvariable=self.bed_x_var, width=6).pack(side="left", padx=4)
        ttk.Label(self.bed_frame, text="Y").pack(side="left")
        ttk.Entry(self.bed_frame, textvariable=self.bed_y_var, width=6).pack(side="left", padx=4)
        self.bed_frame.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.note_var = tk.StringVar()
        ttk.Label(box, textvariable=self.note_var, foreground="#555555").grid(
            row=2, column=0, columnspan=6, sticky="w", pady=(6, 0))
        self.printer_var.trace_add("write", lambda *_: self._printer_changed())
        for var in (self.material_var, self.nozzle_var, self.bed_x_var, self.bed_y_var):
            var.trace_add("write", lambda *_: self._update_summary())

        # -- tag appearance
        tag_box = ttk.LabelFrame(self, text="Tag design", padding=8)
        tag_box.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._combo(tag_box, "Font", self.font_var, list(self.fonts), 0, 0, 18)
        ttk.Label(tag_box, text="Default text alignment").grid(row=0, column=2, padx=(16, 4))
        align_frame = ttk.Frame(tag_box)
        align_frame.grid(row=0, column=3, sticky="w")
        for name in ALIGN_LABELS:
            ttk.Radiobutton(align_frame, text=name, value=name, variable=self.align_var,
                            command=self.refresh).pack(side="left", padx=4)
        ttk.Label(tag_box, text="Number of tags").grid(row=0, column=6, padx=(16, 4))
        ttk.Spinbox(tag_box, from_=1, to=c.MAX_TAGS, width=4, textvariable=self.count_var,
                    command=self._count_changed).grid(row=0, column=7)
        count_box = tag_box.grid_slaves(row=0, column=7)[0]
        count_box.bind("<Return>", lambda _e: self._count_changed())
        count_box.bind("<FocusOut>", lambda _e: self._count_changed())
        ttk.Label(tag_box, text="Tag size").grid(row=1, column=0, sticky="w", pady=(8, 0))
        slider = ttk.Scale(tag_box, from_=c.SIZE_MIN_PCT, to=c.SIZE_MAX_PCT, variable=self.size_var,
                           command=lambda _v: self._size_moved())
        slider.grid(row=1, column=1, columnspan=5, sticky="ew", pady=(8, 0), padx=4)
        ttk.Label(tag_box, text="50%", foreground="#777777").grid(row=2, column=1, sticky="w", padx=4)
        ttk.Label(tag_box, text="150%", foreground="#777777").grid(row=2, column=5, sticky="e", padx=4)
        self.size_label = ttk.Label(tag_box, width=6)
        self.size_label.grid(row=1, column=6, pady=(8, 0))
        ttk.Label(tag_box, textvariable=self.dims_var).grid(row=3, column=0, columnspan=8, sticky="w", pady=(4, 0))
        tag_box.columnconfigure(5, weight=1)

        # -- spreadsheet
        grid_box = ttk.LabelFrame(self, text="Tag text  (click a cell to edit - paste from Excel with Ctrl+V)",
                                  padding=8)
        grid_box.grid(row=3, column=0, sticky="nsew", pady=(8, 0))
        grid_box.columnconfigure(0, weight=1)
        grid_box.rowconfigure(0, weight=1)
        self.grid_widget = SpreadsheetGrid(grid_box, self.refresh, self._row_selected, self._grid_grew)
        self.grid_widget.grid(row=0, column=0, sticky="nsew")

        # -- preview + save
        prev_box = ttk.LabelFrame(self, text="Preview of selected tag (top view)", padding=8)
        prev_box.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        prev_box.columnconfigure(0, weight=1)
        self.preview = TagPreview(prev_box)
        self.preview.grid(row=0, column=0, sticky="ew")

        bottom = ttk.Frame(self)
        bottom.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        ttk.Label(bottom, textvariable=self.summary_var).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=120)
        self.progress.grid(row=0, column=1)
        self.progress.grid_remove()

    def _combo(self, parent, label: str, var: tk.StringVar, values: list[str], row: int, col: int,
               width: int) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0 if col == 0 else 16, 4))
        box = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
        box.grid(row=row, column=col + 1, sticky="w")
        box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
        return box

    # ---- state -----------------------------------------------------------------------
    def current_printer(self) -> Printer:
        found = printer_by_label(self.printer_var.get())
        if found:
            return found
        return custom_printer(self._number(self.bed_x_var, DEFAULT_BED), self._number(self.bed_y_var, DEFAULT_BED))

    @staticmethod
    def _number(var: tk.StringVar, default: float) -> float:
        try:
            return max(float(var.get()), 50.0)
        except ValueError:
            return default

    def _printer_changed(self) -> None:
        printer = self.current_printer()
        other = not printer.bambu
        self.material_box.configure(state="disabled" if other else "readonly")
        self.nozzle_box.configure(state="readonly" if printer.dual_nozzle else "disabled")
        if not printer.dual_nozzle:
            self.nozzle_var.set(Nozzle.NORMAL.value)
        (self.bed_frame.grid if other else self.bed_frame.grid_remove)()
        if other:
            self.note_var.set("Plain 3MF: geometry and two colours only (body, text). Set material and "
                              "temperatures in your slicer. Nozzle: 0.4 mm.")
        elif printer.dual_nozzle:
            self.note_var.set("Bambu Studio project. Nozzle diameter defaults to 0.4 mm. "
                              f"Plate {printer.bed_x:g} x {printer.bed_y:g} mm.")
        else:
            self.note_var.set("Bambu Studio project. Nozzle diameter defaults to 0.4 mm "
                              "(Normal nozzle only on this printer). "
                              f"Plate {printer.bed_x:g} x {printer.bed_y:g} mm.")
        self.refresh()

    def _size_moved(self) -> None:
        self.size_var.set(round(self.size_var.get()))
        self.refresh()

    def _count_changed(self) -> None:
        try:
            count = int(self.count_var.get())
        except (tk.TclError, ValueError):
            count = len(self.grid_widget.rows)
        count = max(1, min(c.MAX_TAGS, count))
        self.count_var.set(count)
        self.grid_widget.set_row_count(count)
        self.refresh()

    def _grid_grew(self, count: int) -> None:
        self.count_var.set(count)

    def _row_selected(self, _index: int) -> None:
        self._update_preview()

    # ---- spec building ---------------------------------------------------------------
    def _spec_for(self, row: RowData) -> TagSpec:
        text_pct = None
        if row.size:
            try:
                text_pct = float(row.size)
            except ValueError as exc:
                raise RowError("Text size % must be a number (blank = Auto)") from exc
            if not c.MANUAL_MIN_PCT <= text_pct <= c.MANUAL_MAX_PCT:
                raise RowError(f"Text size % must be {c.MANUAL_MIN_PCT:g}-{c.MANUAL_MAX_PCT:g} (blank = Auto)")
        align = ALIGN_LABELS.get(row.align) or ALIGN_LABELS[self.align_var.get()]
        return TagSpec(row.text, float(self.size_var.get()), text_pct, align)

    def build_specs(self) -> tuple[list[TagSpec | None], list[str]]:
        """Specs per row (None for unusable rows) and the error text per row."""
        specs, errors = [], []
        for row in self.grid_widget.rows:
            try:
                specs.append(self._spec_for(row))
                errors.append("")
            except RowError as exc:
                specs.append(None)
                errors.append(str(exc))
        return specs, errors

    # ---- refresh ---------------------------------------------------------------------
    def refresh(self) -> None:
        face = load_font(self.fonts[self.font_var.get()])
        pct = self.size_var.get()
        d = dimensions(pct)
        self.size_label.configure(text=f"{pct}%")
        self.dims_var.set(
            f"Length x width x thickness:   {d.length:.1f} x {d.width:.1f} x {d.thickness:.2f} mm    |    "
            f"{d.length / MM_PER_CM:.2f} x {d.width / MM_PER_CM:.2f} x {d.thickness / MM_PER_CM:.2f} cm    |    "
            f"{d.length / MM_PER_INCH:.2f} x {d.width / MM_PER_INCH:.2f} x {d.thickness / MM_PER_INCH:.2f} in")
        specs, errors = self.build_specs()
        for i, (spec, err) in enumerate(zip(specs, errors, strict=True)):
            if spec is None:
                self.grid_widget.set_status(i, err, True)
            else:
                fit = fit_text(face, spec)
                self.grid_widget.set_status(i, fit.message, fit.warning)
        self._update_preview()
        self._update_summary()

    def _update_preview(self) -> None:
        specs, _ = self.build_specs()
        index = min(self.grid_widget.selected_index(), len(specs) - 1)
        if specs and specs[index] is not None:
            self.preview.show(load_font(self.fonts[self.font_var.get()]), specs[index])

    def _update_summary(self) -> None:
        specs, errors = self.build_specs()
        usable = [s for s in specs if s is not None]
        if not usable:
            self.summary_var.set("")
            return
        try:
            plates = len(plan_plates(usable, self._job_options()))
            where = "plate" if plates == 1 else "plates"
            self.summary_var.set(f"{len(specs)} tags -> {plates} {where}"
                                 + (f"   |   {sum(1 for e in errors if e)} row(s) need fixing" if any(errors) else ""))
        except LayoutError as exc:
            self.summary_var.set(str(exc))

    def _job_options(self) -> JobOptions:
        return JobOptions(self.fonts[self.font_var.get()], self.current_printer(),
                          Material(self.material_var.get()), Nozzle(self.nozzle_var.get()))

    # ---- saving ----------------------------------------------------------------------
    def generate(self, kind: str) -> None:
        """Check the table, ask where to save (File > Save As dialog) and build a 3MF or STL."""
        if self._saving:
            return
        specs, errors = self.build_specs()
        if any(errors):
            bad = next(i for i, e in enumerate(errors) if e)
            self.grid_widget.select(bad)
            messagebox.showerror("Fix the table first", f"Row {bad + 1}: {errors[bad]}")
            return
        face = load_font(self.fonts[self.font_var.get()])
        spills = [i + 1 for i, s in enumerate(specs) if fit_text(face, s).status is FitStatus.OVERFLOW]
        if spills and not messagebox.askyesno(
                "Text spills over", f"Text on tag(s) {', '.join(map(str, spills))} spills over the tag edge "
                "and will be clipped.\n\nSave anyway?"):
            return
        label = "3MF project" if kind == "3mf" else "STL model"
        path = filedialog.asksaveasfilename(
            parent=self.master, title=f"Save {label} as", defaultextension=f".{kind}",
            initialfile=f"ziptie_tags.{kind}", filetypes=[(label, f"*.{kind}"), ("All files", "*.*")])
        if not path:
            return
        opts = self._job_options()
        self._saving = True
        self._set_buttons("disabled")
        self.progress.grid()
        self.progress.start(12)
        threading.Thread(target=self._worker, args=(specs, opts, Path(path), kind), daemon=True).start()

    def _worker(self, specs: list[TagSpec], opts: JobOptions, path: Path, kind: str) -> None:
        try:
            plates = (build_job if kind == "3mf" else build_stl)(specs, opts, path)
            result: tuple[bool, str] = (True, f"Saved {len(specs)} tag(s) on {plates} plate(s):\n{path}")
        except (LayoutError, OSError, ValueError) as exc:
            result = (False, str(exc))
        except Exception as exc:  # noqa: BLE001 - show any unexpected failure instead of dying silently
            result = (False, f"Unexpected error: {exc!r}")
        self.master.after(0, self._saved, result)

    def _saved(self, result: tuple[bool, str]) -> None:
        self._saving = False
        self.progress.stop()
        self.progress.grid_remove()
        self._set_buttons("normal")
        (messagebox.showinfo if result[0] else messagebox.showerror)(
            "Saved" if result[0] else "Could not save", result[1])

    def _set_buttons(self, state: str) -> None:
        for button in (self.mf_button, self.stl_button):
            button.configure(state=state)

    # ---- help ------------------------------------------------------------------------
    def show_instructions(self) -> None:
        win = tk.Toplevel(self.master)
        win.title("Instructions")
        win.geometry("640x560")
        text = tk.Text(win, wrap="word", padx=12, pady=10, font=("Segoe UI", 10))
        text.insert("1.0", INSTRUCTIONS)
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)

    def show_about(self) -> None:
        messagebox.showinfo("About", f"Ziptie Tags  v{__version__}\n\nGenerates zip-tie cable tag 3MF files "
                            "for Bambu Lab printers and other slicers.\nFonts: SIL Open Font License.")


def _enable_dpi_awareness() -> None:
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shcore.SetProcessDpiAwareness(1)


def selftest(path: Path) -> int:
    """Build a small project without opening a window (checks bundled fonts/templates)."""
    fonts = available_fonts()
    opts = JobOptions(next(iter(fonts.values())), BAMBU_PRINTERS[-1])
    plates = build_job([TagSpec("HEX BEAM"), TagSpec("VERTICAL")], opts, path)
    print(f"selftest ok: {len(fonts)} fonts, {plates} plate, v{__version__}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "--selftest":
        return selftest(Path(args[1]))
    _enable_dpi_awareness()
    root = tk.Tk()
    root.title(f"Ziptie Tags  v{__version__}")
    root.geometry("1100x860")
    root.minsize(900, 720)
    App(root).pack(fill="both", expand=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
