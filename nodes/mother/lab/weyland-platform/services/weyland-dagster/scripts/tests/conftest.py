"""Put the weyland-dagster/scripts dir on sys.path so the script modules import by bare name (as they run)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
