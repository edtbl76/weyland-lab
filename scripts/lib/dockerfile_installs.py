"""Count the Python packages a Dockerfile installs outside a requirements file (2026-10-16).

A `pip install <pkg>` line is invisible to every source scanner (they read requirements files, never Dockerfiles), and
an unpinned one drifts on any rebuild. `scripts/check-dockerfile-installs.sh` holds each Dockerfile to a ceiling in
scripts/ci/dockerfile-installs.baseline that may only fall. Pure, stdlib: the wrapper does the I/O and exit codes.

What counts: each package token of `pip install` / `pip3 install` / `uv pip install` in any stage, pinned or not, once
comments are dropped and `\\` continuations joined. What doesn't: `-r`/`--requirement`/`-e`/`-c` installs (a file the
scanners read), option values (`--index-url URL`, `--target DIR`), local paths and wheels.
"""
import re
import shlex

_INSTALL = re.compile(r"\b(?:pip3?|uv\s+pip)\s+install\b(.*)")
_FROM_FILE = {"-r", "--requirement", "-e", "--editable", "-c", "--constraint"}
_TAKES_VALUE = {"--index-url", "-i", "--extra-index-url", "--target", "-t", "--prefix", "--root", "--find-links",
                "-f", "--trusted-host", "--cache-dir", "--python", "--platform", "--python-version", "--implementation",
                "--abi", "--only-binary", "--no-binary", "--progress-bar"}


_REDIRECT = re.compile(r"^\d*(?:>>?|<|>&)")             # a shell redirect token (k8s manifests, B227)
_REDIRECT_BARE = re.compile(r"^\d*(?:>>?|<)$")           # ... with its target in the NEXT token
_MESSAGE = re.compile(r"\b(?:echo|printf)\b")            # `pip install` inside a message is not an install


def _logical_lines(text):
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(lines).replace("\\\n", " ").splitlines()


def _is_package(tok):
    return not (tok.startswith((".", "/", "$", "~")) or tok.endswith((".whl", ".tar.gz", ".zip")) or "://" in tok)


def _segment_packages(args):
    try:
        toks = shlex.split(args)
    except ValueError:
        toks = args.split()
    if any(t in _FROM_FILE or t.startswith(("--requirement=", "--constraint=")) for t in toks):
        return []
    out, skip, i = [], False, 0
    while i < len(toks):
        t = toks[i]
        if _REDIRECT.match(t):                           # `>/dev/null`, `2>&1`; a bare `>` / `2>` also eats its target
            skip = _REDIRECT_BARE.match(t) is not None
        elif skip:
            skip = False
        elif t.startswith("-"):
            skip = t in _TAKES_VALUE
        elif " @ " in t:                                  # a quoted PEP 508 direct reference: one package
            out.append(t)
        elif i + 2 < len(toks) and toks[i + 1] == "@":   # the same, unquoted: name @ url
            out.append(f"{t} @ {toks[i + 2]}")
            i += 2
        elif _is_package(t):
            out.append(t)
        i += 1
    return out


def packages(text):
    """Every package token installed directly by this Dockerfile, in order."""
    found = []
    for line in _logical_lines(text):
        for seg in re.split(r"&&|\|\|?|;", line):
            m = _INSTALL.search(seg)
            if m and not _MESSAGE.search(seg[:m.start()]):
                found += _segment_packages(m.group(1))
    return found


def compare(counts, baseline):
    """(failures: a count above its ceiling or an unlisted Dockerfile, lowerable: a count below its ceiling)."""
    bad, lower = [], []
    for path in sorted(set(counts) | set(baseline)):
        n, ceiling = counts.get(path, 0), baseline.get(path, 0)
        if n > ceiling:
            note = " (not in the baseline)" if path not in baseline else ""
            bad.append(f"{path}: {n} direct pip install(s), baseline {ceiling}{note}")
        elif n < ceiling:
            lower.append(f"{path}: {n} < baseline {ceiling}")
    return bad, lower


def read_baseline(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                p, n = line.rstrip("\n").split("\t")
                out[p] = int(n)
    return out


def write_baseline(path, counts):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# scripts/check-dockerfile-installs.sh — per-file ceiling (Dockerfiles and, since B227, k8s manifests) on\n"
                "# packages installed outside a requirements file. It may only FALL: move installs into a pinned\n"
                "# requirements file (for a manifest: bake them into an image built from one), then lower it\n"
                "# (scripts/check-dockerfile-installs.sh --write-baseline). <path>\\t<count>; zero rows are omitted.\n")
        for p in sorted(counts):
            if counts[p]:
                f.write(f"{p}\t{counts[p]}\n")
