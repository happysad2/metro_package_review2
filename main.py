"""
Metro Package Review 1.0
========================
Sydney Metro package review tool — validates asset registers, IFC models,
and NWC models against Sydney Metro BIM requirements.

Launch:  python main.py
"""

import sys
from pathlib import Path

# Ensure the app root is on sys.path so modules can be imported
if getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(sys._MEIPASS).resolve()))
else:
    sys.path.insert(0, str(Path(__file__).parent.resolve()))

from ui import launch

if __name__ == "__main__":
    launch()
