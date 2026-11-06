> **Status:** approved spec for v1.01, kept for history. As built: printers are Bambu A1, X1, P1S, P1P,
> H2C, H2D plus "Other printer" (plain 3MF, custom bed size); X2D was dropped; the standard label area is 58 mm
> (tag 72 x 16 mm at 100 %); the exe never runs the Studio CLI (dev tool only). See README.md and CHANGELOG.md.

# Ziptie Tags — Spec and Test Plan (v2 DRAFT)

Repo/code folder: `3d Print Files\Ziptie Tags` (this spec moves there once approved).

## Goal
Windows desktop app that generates a 3MF of zip-tie cable tags (body color + flush text inlay), based on the validated `antenna_cable_tags_bambu.3mf`. Version is shown in the app title/About and tracked as git tags and GitHub releases.

## Inputs (UI)
| # | Control | Behavior |
|---|---------|----------|
| 1 | Number of tags | 1–40 |
| 2 | Spreadsheet grid | One row per tag (rows = count). Columns: **Text, Size %, Align**. Paste from Excel works. Per-row status column shows OK / WARNING (text too long, shrunk to fit / does not fit at minimum size). |
| 3 | Tag size slider | 50%–150% (100% = current tag). Shows length x width in mm, cm and inches. Thickness (3.44 mm), layer plan and zip-tie hole (6 x 2 mm) never change. |
| 4 | Text size | Auto-fit by default; per-tag override (Size % column) 30–100% of the text area height. Per-tag warning if the text would spill over the tag (never silently clipped). |
| 5 | Text alignment | Center / Left / Right. Default set globally, overridable per tag in the grid. |
| 6 | Font | Drop-down of 10 embedded, open-licensed fonts (see below), with a live preview line. |
| 7 | Material | PLA / PETG / ABS. |
| 8 | Printer | Bambu: A1, X1, P1S, P1P, H2C, H2D (X2D removed). Non-Bambu printers: see open question. |
| 9 | Nozzle | Normal / High Flow (Bambu only). Instructions state nozzle defaults to 0.4 mm. |
| 10 | Save As | Standard File > Save As dialog -> `.3mf`. |

## Fonts (embedded in the app, SIL OFL / Apache licensed so they may be redistributed; license files ship in the repo)
Roboto, Open Sans, Lato, Montserrat, Oswald, Source Sans 3, Noto Sans, Roboto Condensed, Poppins, Ubuntu. Bold weight used. (Arial is dropped as a choice: it is not redistributable.) Latin charset incl. accents, digits and common symbols (- _ / . & # +).

## Output
- Bambu printers: Bambu Studio-native 3MF (Application metadata, full settings, layer ranges 0.20 mm / top 0.64 mm at 0.08 mm, two filaments black/orange), multi-plate when tags don't fit.
- Non-Bambu printers: **plain 3MF with no Bambu Studio header/footer, metadata or settings** (geometry + two named parts/colors only). Plate size used only for layout.
- Tags auto-arranged, 4 mm spacing, 5 mm margin; extra plates added when needed (plain 3MF: arranged in plate-sized groups spaced apart, since plain 3MF has no plates).

## Plate sizes
A1/X1/P1S/P1P 256x256, H2D 350x320, H2C 330x320 (from installed Studio profiles). Non-Bambu sizes per chosen list.

## Q: Does the .exe run the Studio CLI?
**No.** The CLI is only a development test tool I use to validate the generated files. The .exe never launches Bambu Studio and does not need it installed. The "out of memory" popup risk applies only to my testing; I will run those tests only with your Studio closed and tell you before each batch.

## Architecture
Python 3 + tkinter, manifold3d + numpy, own TTF outline parser (handles composite glyphs for accents). Modules: `ziptag/` package (`geometry`, `fonts`, `layout`, `bambu_3mf`, `plain_3mf`, `printers`, `app` UI), `tests/`, `build.ps1` (PyInstaller one-file exe), `fonts/` (TTF + licenses), `templates/` (Bambu base files), `VERSION`.
Repo files: `.gitignore` (venv, build/dist, test output, local settings, `CLAUDE.local.md`, `.claude/settings.local.json`, personal paths), `README.md`, `CLAUDE.md` (project instructions, committed), `CHANGELOG.md`, `LICENSE` (needs your choice), font licenses.

## Release process (CI/CD)
Semantic version in `VERSION`, shown in the app, tagged `vX.Y.Z`. After testing I summarize and prompt you before every push; I write the commit message and CHANGELOG entry for each version. Exe published as a GitHub Release asset (not committed). You approve each push and release.

## Review gates before release
A. UI review (clean, easy, labels, tab order, errors, small screens, DPI). B. Readability/style review (PEP 8, naming, docstrings, consistency, linted with ruff). C. Architecture review (module boundaries, data flow, error handling, risks). Fixes applied, then retest.

## Risks
1. Bambu base settings exist as validated only for H2D; other Bambu printers need templates validated by Studio CLI slicing. Any that fail will be reported, not shipped silently.
2. Material x printer x nozzle matrix is sampled, not exhaustively sliced; no physical print testing.
3. Plain 3MF: colors/parts import differently per slicer; verified only by structural checks.
4. Font licenses must ship with the exe/repo.

## Test plan
Unit: text fit/warnings per tag (short/long/min size), alignment (L/C/R positions), all 10 fonts render every character, size slider 50/100/150% dims in mm/cm/in, hole and thickness unchanged, 1/16/40 tags, multi-plate counts, no overlaps, tags inside plate.
Geometry: manifold meshes; inlay volume = recess volume.
File: Bambu 3MF is Bambu-native; plain 3MF contains no Bambu strings (automated grep for "Bambu"); layer ranges; filament count/colors.
Slice (Studio CLI, Studio closed): each Bambu printer x PETG; PLA/ABS and High Flow samples; 40 tags at 150% across plates; check Z layers and filament use.
GUI: grid paste, Save As cancel, error dialogs, exe launches from a clean folder, version shown.
