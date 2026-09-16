"""Put the scripts dir on sys.path so the utility modules import directly (they're stdlib-only)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the scripts/ dir
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
