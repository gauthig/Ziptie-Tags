"""Developer tool: slice a generated 3MF with the Bambu Studio CLI and report what came out.

Close Bambu Studio first: a failing CLI run can pop an "out of memory" dialog.
Usage: python tools/slice_check.py <file.3mf> [--timeout 240]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

STUDIO = Path(r"C:\Program Files\Bambu Studio\bambu-studio.exe")


def studio_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq bambu-studio.exe"], capture_output=True, text=True)
    return "bambu-studio.exe" in out.stdout.lower()


def slice_file(path: Path, timeout: int = 240) -> dict:
    """Slice every plate; return result code, per-plate layer heights and filament usage."""
    out_dir = Path(tempfile.mkdtemp(prefix="zt_slice_"))
    proc = subprocess.Popen([str(STUDIO), "--slice", "0", "--outputdir", str(out_dir),
                             "--export-3mf", "sliced.3mf", str(path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"error": "timeout"}
    result_file = out_dir / "result.json"
    report: dict = {"exit": proc.returncode, "dir": str(out_dir)}
    if result_file.exists():
        report["result"] = json.loads(result_file.read_text())["error_string"]
    sliced = out_dir / "sliced.3mf"
    if sliced.exists():
        with zipfile.ZipFile(sliced) as z:
            plates = sorted(n for n in z.namelist() if re.fullmatch(r"Metadata/plate_\d+\.gcode", n))
            report["plates"] = {}
            info = z.read("Metadata/slice_info.config").decode("utf-8", "replace")
            usage = re.findall(r'<filament id="(\d+)"[^>]*type="(\w+)"[^>]*used_g="([\d.]+)"', info)
            for name in plates:
                gcode = z.read(name).decode("utf-8", "replace")
                zs = sorted({float(v) for v in re.findall(r"^; Z_HEIGHT: ([\d.]+)", gcode, re.M)})
                report["plates"][name] = {"layers": len(zs), "top_z": zs[-1] if zs else None,
                                          "top_layers": zs[-9:]}
            report["filament_grams_per_plate"] = usage
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", type=Path)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--keep", action="store_true", help="keep the output folder")
    args = parser.parse_args()
    if studio_running():
        print("Bambu Studio is running - close it first.")
        return 2
    report = slice_file(args.file, args.timeout)
    print(json.dumps(report, indent=2))
    if not args.keep and "dir" in report:
        shutil.rmtree(report["dir"], ignore_errors=True)
    return 0 if report.get("result") == "Success." else 1


if __name__ == "__main__":
    sys.exit(main())
