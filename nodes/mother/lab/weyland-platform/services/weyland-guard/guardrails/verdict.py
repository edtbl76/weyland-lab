from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    PASS = "pass"
    FLAG = "flag"
    BLOCK = "block"


class Hook(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    ACT = "act"


class Mode(str, Enum):
    OFF = "off"
    SHADOW = "shadow"
    FLAG = "flag"
    BLOCK = "block"


@dataclass
class Verdict:
    validator: str
    decision: Decision
    score: float | None
    reason: str
    latency_ms: int
