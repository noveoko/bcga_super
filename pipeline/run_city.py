"""Alias for pipeline/run_city_fps.py (playable Unreal city; third-person default)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_city_fps import main


if __name__ == "__main__":
    main()
