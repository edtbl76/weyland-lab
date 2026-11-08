"""The lab's command roster, extracted from docs/runbooks/*.md (B187 follow-on; `lab-commands`, `lab-ask`).

The runbooks are the only source of the lab's commands (AGENTS.md: one canonical command per task, in a runbook). The
roster is regenerated from them on every call and never stored, so it cannot drift; a command missing from the roster
is a runbook gap, fixed in the runbook.

Runbooks write a command three ways, and all three are read:
  1. a fenced block, optionally under a host label on its own line (`[rogueone]` then a fence);
  2. `[host] command` lines inside an unlabelled fence;
  3. inline code in prose, e.g. a bullet saying "manual (`woodpecker-cli pipeline create ...`)".
Fences in non-shell languages (yaml, json, mermaid, ...) and bare fences with no command-looking line (pasted output)
are skipped. Stdlib only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SHELL_LANGS = {"", "bash", "sh", "shell", "console", "zsh"}
# Patterns are anchored and unambiguous (no `\s*…\s*$` pairs), so none can backtrack polynomially. Callers strip
# the line first.
HOST_LABEL = re.compile(r"\[([a-z0-9][a-z0-9-]*)\]")              # fullmatch on a stripped line
HOST_PREFIX = re.compile(r"\[([a-z0-9][a-z0-9-]*)\] +(\S.*)")      # fullmatch on a stripped line
FENCE_LANG = re.compile(r"[A-Za-z0-9_+-]*")
INLINE = re.compile(r"`([^`\n]+)`")

# First words that mark a shell line as a command. Inline code is held to a narrower list: prose mentions `cat`,
# `ls` and `set` as words far more often than as instructions.
FENCE_WORDS = {
    "bash", "sh", "sudo", "kubectl", "woodpecker-cli", "curl", "python3", "python", "docker", "argocd", "helm", "ssh",
    "rsync", "tofu", "terraform", "psql", "mc", "git", "gh", "uv", "pip", "npm", "npx", "bats", "dagster", "systemctl",
    "journalctl", "crictl", "k3s", "ctr", "jq", "claude", "restic", "make", "cd", "export", "set", "source", ".",
    "cat", "ls", "grep", "find", "mkdir", "cp", "mv", "tar", "wget", "nvidia-smi", "ollama", "openssl", "kubeseal",
    "trivy", "promtool", "amtool", "lakectl", "trino", "redpanda", "rpk", "flink", "mvn", "go", "cargo", "dotnet",
    "for", "until", "while", "env", "watch", "tail", "head", "awk", "sed", "basic-memory", "codex", "opencode",
}
INLINE_WORDS = {
    "bash", "sudo", "kubectl", "woodpecker-cli", "curl", "python3", "docker", "argocd", "helm", "ssh", "rsync", "tofu",
    "psql", "mc", "gh", "uv", "bats", "dagster", "systemctl", "journalctl", "crictl", "k3s", "ctr", "claude", "restic",
    "nvidia-smi", "ollama", "kubeseal", "trivy", "promtool", "amtool", "lakectl", "rpk", "basic-memory",
}


@dataclass(frozen=True)
class Entry:
    title: str      # the runbook's H1
    section: str    # heading chain below the H1, "Trigger a run > Logs"
    source: str     # docs/runbooks/x.md#anchor
    host: str       # rogueone / mother / "" when the runbook does not say
    command: str    # one line, or a whole multi-line block


def _anchor(heading: str) -> str:
    """GitHub-style heading anchor: lowercase, drop punctuation, spaces to hyphens."""
    text = re.sub(r"[`*_]", "", heading.lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.strip().replace(" ", "-")


def _first_word(line: str) -> str:
    line = line.strip()
    if line.startswith("$ "):
        line = line[2:]
    return line.split(maxsplit=1)[0] if line else ""


def _looks_like_command(line: str, words: set[str]) -> bool:
    first = _first_word(line)
    return first in words or first.startswith(("scripts/", "./", "/home/", "~/")) or first.endswith(".sh")


def _fence_lang(line: str) -> str | None:
    """The language of a fence line (`` ```bash `` -> "bash", `` ``` `` -> ""), or None when it is not a fence."""
    s = line.strip()
    if not s.startswith("```"):
        return None
    lang = s[3:].strip()
    return lang.lower() if FENCE_LANG.fullmatch(lang) else None


def _heading(line: str) -> tuple[int, str] | None:
    """(level, text) for an ATX heading, trailing #s removed; None otherwise."""
    hashes = len(line) - len(line.lstrip("#"))
    if not 1 <= hashes <= 6 or not line[hashes:hashes + 1].isspace():
        return None
    return hashes, line[hashes:].strip().rstrip("#").strip()


def _fence_entries(lines: list[str], label_host: str) -> list[tuple[str, str]]:
    """Split a shell fence into (host, command) pairs. `[host] cmd` lines stand alone; the rest form one block."""
    out, block = [], []
    for raw in lines:
        m = HOST_PREFIX.fullmatch(raw.strip())
        if m:
            out.append((m.group(1), m.group(2).strip()))
        elif raw.strip():
            block.append(raw.rstrip())
    if block and any(_looks_like_command(b, FENCE_WORDS) for b in block):
        indent = min(len(b) - len(b.lstrip()) for b in block)
        out.insert(0, (label_host, "\n".join(b[indent:] for b in block)))
    return out


class _Runbook:
    """One pass over a runbook: tracks the heading chain and collects entries."""

    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.title = rel_path.rsplit("/", 1)[-1]
        self.chain: list[tuple[int, str]] = []
        self.anchor = ""
        self.entries: list[Entry] = []
        self.seen: set[tuple[str, str, str]] = set()

    def add(self, host: str, command: str) -> None:
        section = " > ".join(h for _, h in self.chain)
        key = (section, host, command)
        if command and key not in self.seen:
            self.seen.add(key)
            source = f"{self.rel_path}#{self.anchor}" if self.anchor else self.rel_path
            self.entries.append(Entry(self.title, section, source, host, command))

    def heading(self, level: int, name: str) -> None:
        if level == 1:
            self.title, self.chain = name, []
        else:
            self.chain = [(lvl, h) for lvl, h in self.chain if lvl < level] + [(level, name)]
        self.anchor = _anchor(name)

    def fence(self, lang: str, body: list[str], previous_line: str) -> None:
        if lang not in SHELL_LANGS:
            return
        label = HOST_LABEL.fullmatch(previous_line.strip())
        for host, command in _fence_entries(body, label.group(1) if label else ""):
            self.add(host, command)

    def prose(self, line: str) -> None:
        for span in INLINE.findall(line):
            span = span.strip()
            if len(span.split()) >= 2 and _looks_like_command(span, INLINE_WORDS):
                self.add("", span)


def _read_fence(lines: list[str], start: int) -> tuple[list[str], int]:
    """The body of the fence opened at lines[start], and the index just past its closing line."""
    end = start + 1
    while end < len(lines) and _fence_lang(lines[end]) is None:
        end += 1
    return lines[start + 1:end], end + 1


def extract(text: str, rel_path: str) -> list[Entry]:
    """Every command in one runbook, in document order, deduplicated per section."""
    rb = _Runbook(rel_path)
    lines = text.splitlines()
    i, previous = 0, ""
    while i < len(lines):
        line = lines[i]
        lang = _fence_lang(line)
        if lang is not None:
            body, i = _read_fence(lines, i)
            rb.fence(lang, body, previous)
            previous = ""
            continue
        heading = _heading(line)
        if heading:
            rb.heading(*heading)
        else:
            rb.prose(line)
        if line.strip():
            previous = line
        i += 1
    return rb.entries


def render(entries: list[Entry]) -> str:
    """The roster as text: one `## title > section (source)` header per section, then `[host] command` lines."""
    out, header = [], None
    for e in entries:
        h = f"## {e.title}{' > ' + e.section if e.section else ''} ({e.source})"
        if h != header:
            if out:
                out.append("")
            out.append(h)
            header = h
        host = e.host or "any"
        first, *rest = e.command.splitlines()
        out.append(f"[{host}] {first}")
        out.extend(f"    {r}" for r in rest)
    return "\n".join(out) + "\n"


def grep(entries: list[Entry], words: list[str]) -> list[Entry]:
    """Entries whose title, section or command contains every word, case-insensitively."""
    wanted = [w.lower() for w in words]
    return [e for e in entries if all(w in f"{e.title} {e.section} {e.command}".lower() for w in wanted)]


def prompt(question: str, index: str) -> str:
    """The single stdin payload for `claude -p`: rules, the question, then the roster."""
    return (
        "You answer questions about operating a homelab, using ONLY the command index below. The index is generated "
        "from the lab's runbooks; each entry has a header `## runbook > section (docs/runbooks/file.md#anchor)` and "
        "lines `[host] command`, where host is the machine to run it on (`any` = the runbook does not say).\n\n"
        "Answer with: the command(s) to run, the host, and the runbook source path. Keep it short. Copy commands "
        "exactly; do not invent flags or fill placeholders like <N>. If several entries fit, list the best two or "
        "three. If nothing in the index does the job, say plainly that it is not in the index (that is a runbook "
        "gap) and do not answer from general knowledge.\n\n"
        f"Question: {question}\n\n"
        "Command index:\n\n"
        f"{index}"
    )
