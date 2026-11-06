# CLAUDE.md - Ziptie Tags

Project instructions for Claude Code (committed). Personal/machine notes go in `CLAUDE.local.md` (gitignored).

## Purpose
Windows tkinter app that writes 3MF files of zip-tie cable tags (black body, orange flush text) for Bambu Lab
printers (native Bambu Studio projects) or any other printer (plain 3MF).

## Architecture (`ziptag/`)
- `constants.py` fixed dimensions and limits (single source for thickness, slot, layer plan)
- `fonts.py` bundled-font discovery + glyph outlines (fontTools) ; `geometry.py` tag dimensions, text fitting
  (`fit_text`, per-tag), `place_text`, `build_tag` (manifold3d booleans: body = block - slot - text recess,
  inlay = extruded text)
- `layout.py` shelf packing onto plates with keep-out areas ; `printers.py` printer/material/nozzle models
- `bambu_3mf.py` Bambu Studio project writer (settings from `templates/*.json.gz`, layer ranges, plates) ;
  `stl.py` binary STL writer (body+text fused) ; `plain_3mf.py` vendor-neutral writer (must contain nothing Bambu-specific; a test enforces this)
- `project.py` orchestration (`plan_plates`, `build_job`) ; `app.py`, `ui_grid.py`, `ui_preview.py`, `help_text.py` UI
- `tools/` developer-only scripts (`make_fonts.py`, `make_templates.py`, `slice_check.py`); not shipped
- Version: single source `ziptag/_version.py`; shown in the window title and About.

## Commands (PowerShell)
```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .          # lint (must pass)
python -m pytest -q             # tests (must pass)
python ziptie_tags.py           # run
python ziptie_tags.py --selftest out.3mf
powershell -ExecutionPolicy Bypass -File build.ps1    # exe in dist\
```

## Style
PEP 8 via ruff (line length 120), type hints, docstring on every public module/class/function, small
functions, no magic numbers (put them in `constants.py`), UI strings in one place, no personal paths.

## Hard-won knowledge (do not rediscover)
- A 3MF is "Bambu-native" only with `Application=BambuStudio-<ver>` and a complete JSON
  `Metadata/project_settings.config`. Hand-built settings fail to slice if array shapes are wrong; the
  templates are built by trimming a Studio-saved reference to 2 filaments and overlaying system profiles.
- Per-object layer ranges (`layer_config_ranges.xml`, 1-based object index) give the 0.08 mm top zone.
- X1/P1 have an unusable 18x28 mm front-left corner; H2 tags must stay in x 30-320 (both nozzles) and below y 305.
  Violating this gives "Object conflicts were detected" when slicing.
- Plate N origin in a multi-plate project follows Bambu Studio's grid (`plate_origin`).
- Studio CLI validation (`tools/slice_check.py`): close Bambu Studio first; failing runs show an out-of-memory popup.
- Windows: use `pwsh -NoProfile -File` for scripts; screenshots of the Tk window need `PrintWindow` (no desktop grab).

## Release process (CI/CD)
Versions are MAJOR.MINOR (e.g. 1.01), tags `v1.01`. For each release: bump `ziptag/_version.py`, add a `CHANGELOG.md` entry, run lint + tests
(+ Studio slice checks for generator changes), build the exe, commit with a descriptive message, tag `vX.YY`,
publish a GitHub release with `ZiptieTags.exe`. **Always ask the user before `git push` or publishing.**
Do not commit generated `.3mf`, build output or anything personal (see `.gitignore`).
