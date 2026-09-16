"""Put scripts/lib on sys.path so the pure-logic library modules (api_spec_diff, …) import directly.

The project root resolves to scripts/ (this file sits in scripts/tests/); scripts/lib holds stdlib-only
helpers, so no runtime deps are needed to test them.
"""
import os
import sys

_LIB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)
