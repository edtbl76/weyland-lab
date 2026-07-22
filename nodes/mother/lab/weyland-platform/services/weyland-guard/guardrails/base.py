from typing import Protocol
from .verdict import Verdict, Hook


class Validator(Protocol):
    name: str
    hooks: tuple[Hook, ...]      # which hooks this validator runs on

    def check(self, payload: dict, hook: Hook) -> Verdict: ...
