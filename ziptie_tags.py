"""Launcher used by PyInstaller and for ``python ziptie_tags.py``."""
import sys

from ziptag.app import main

if __name__ == "__main__":
    sys.exit(main())
