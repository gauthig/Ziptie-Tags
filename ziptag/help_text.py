"""User-facing instruction text shown in Help > Instructions."""

INSTRUCTIONS = """\
ZIPTIE TAGS - INSTRUCTIONS

WHAT IT MAKES
Zip-tie cable tags: a black tag body with the text inlaid flush in orange. The
zip-tie slot (6 mm x 2 mm) suits ties up to 5 mm wide and coax up to LMR400.
The tag is 3.44 mm thick: 0.20 mm layers, with the top 0.64 mm (the text) at
0.08 mm layers for smooth lettering.

NOZZLE
The tags are designed and sliced for a 0.4 mm nozzle (default). Other nozzle
diameters are not supported by this version.

STEPS
1. Pick your printer. Bambu Lab printers produce a ready-to-slice Bambu Studio
   project. "Other printer" produces a plain 3MF (no Bambu settings) - enter
   your bed size; choose materials and temperatures in your own slicer.
2. Pick the material (PLA, PETG, ABS) and, on H2D/H2C, Normal or High Flow nozzle.
3. Choose the font and the tag size (50% - 150% of the standard tag). The
   length, width and thickness are shown in mm, cm and inches. Thickness and the
   zip-tie slot never change.
4. Set the number of tags (1 - 40) and fill in the table, one tag per row.
   - Click a cell to edit it. Enter = next row, Tab = next cell.
   - You can copy cells from Excel and paste them (Ctrl+V). Columns: Tag text,
     Text size %, Align. Extra rows are added automatically up to 40.
   - Text size % blank = Auto (the text shrinks to fit). A number sets the size
     yourself (100 = standard size). Align blank = the default alignment.
5. Watch the Status column. A warning means the text spills over the tag edge;
   shorten it, lower its size or enlarge the tag. Spilling text is clipped.
6. Generate 3MF (Bambu Studio project or plain 3MF) or Generate STL (geometry only, for CAD or any
   slicer; body and text are fused into one solid). Both open the standard Save As dialog.

PLATES
Tags are arranged automatically. If they do not fit on one plate, extra plates
are added (Bambu projects) or placed side by side (plain 3MF). Space is kept free
for the prime tower and for printer dead zones.

FILAMENTS (Bambu projects)
Filament 1 = tag body (black), filament 2 = text (orange). Assign your spools in
Bambu Studio. ABS needs an enclosed printer (X1, P1S, H2D, H2C); on A1/P1P it
may warp. The project uses the Textured PEI plate.

TIPS
- Tags print at the same layer plan regardless of size; very small text (cap
  height under 3 mm) may not print cleanly.
- Always review the project in your slicer before printing.
"""
