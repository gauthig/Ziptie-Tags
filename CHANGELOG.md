# Changelog

All notable changes are listed here. Versions are MAJOR.MINOR (e.g. 1.01).

## 1.01 - 2026-11-06
First public release.

- Tag generator: black body with flush orange text inlay, 6 x 2 mm zip-tie slot, 3.44 mm thick,
  0.20 mm layers with the top 0.64 mm at 0.08 mm.
- UI: 1-40 tags in a spreadsheet grid (paste from Excel), per-tag text size and alignment, per-tag spill-over
  warnings, live to-scale preview, size slider 50-150 % with mm/cm/inch readout, font choice (10 bundled
  open-licensed fonts), material PLA/PETG/ABS, Normal/High Flow nozzle, Generate 3MF and Generate STL buttons (standard Save As dialog).
- Generate STL button: all tags fused (body + text) into one binary STL for CAD/slicer import.
- Output: native Bambu Studio projects for A1, X1, P1S, P1P, H2C, H2D (multi-plate, prime-tower and dead-zone aware);
  plain 3MF with no Bambu content for other printers.
- Developer tooling: tests, ruff, PyInstaller build script, Studio CLI slice checker, template/font generators.
