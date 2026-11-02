"""Spec-as-oracle v2, step 1: pick ONE planted INTENT defect per framework round-1 output, by rule.
v1 (select_defects.py) planted a single-site mutant; every reviewer found it from the code alone (36/36, framework
documents opened in 1 review), so it measured nothing about documents. v2 changes an intended VALUE consistently in the
code AND in the trial's own tests, so code and tests still agree and only a document that states the value can reveal it.

Rule (no hand-picking):
- candidates = int constants in the target code, value >= 3, outside the `__main__` guard, that occur EXACTLY ONCE as an
  int constant in that code (one line carries the defect), and whose value appears as a whole number in at least one
  framework document the trial authored. In source order.
- mutation = N -> N+1 at that one site, and every whole-number N in the trial's own test files -> N+1.
- accept the first candidate whose mutated copy (a) still passes the trial's OWN tests (code and tests agree) and
  (b) FAILS the hidden reference judge (a real behaviour change).
-> results/oracle2/defects.tsv: task, arm, target, value, line, tests changed, judge verdict
usage: select_intent.py [task-arm ...]   (default: the 16 framework round-1 outputs)"""
import ast
import os
import re
import shutil
import subprocess
import sys

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
O = f"{B}/results/oracle2"
DOC = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)|^aidlc/spaces/(?:[^/.][^/]*/)*[^/.][^/]*\.md$")
TARGET = {"small": "scripts/tests/alert-rules.bats", "brown": "scripts/check-private-lanes.py",
          "green": "nodes/mother/lab/weyland-platform/services/store-scaler/app.py"}
SCALER = "nodes/mother/lab/weyland-platform/services/store-scaler"
os.makedirs(O, exist_ok=True)
os.makedirs(f"{B}/trash", exist_ok=True)


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True).stdout


def target(task, arm):
    if task != "vague":
        return TARGET[task]
    m = re.search(r"^checker=(\S+)", open(f"{B}/results/quality/{task}-{arm}.txt").read(), re.M)
    return m.group(1) if m else None


def own_tests(d, task, tgt):
    """The trial's own test files, found the way quality/in_container.sh finds them."""
    if task == "small":
        return []          # the bats @tests live in the target file itself, outside the Python block
    if task == "green":
        t = f"{d}/{SCALER}/tests"
        return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(t) for f in fs if f.endswith(".py"))
    key = os.path.basename(tgt)
    out = subprocess.run(["grep", "-rl", key, f"{d}/scripts/tests", "--include=*.bats"], capture_output=True, text=True).stdout
    return sorted(os.path.relpath(p, d) for p in out.split())


def framework_docs(src, arm):
    """Framework documents the trial authored (build_review.py's rule)."""
    commits = git(src, "rev-list", "--reverse", "HEAD").split()
    since = commits[1] if (arm != "aidlc" and len(commits) > 1) else commits[0]
    authored = set(git(src, "diff", "--name-only", "--diff-filter=A", since).split())
    authored |= set(git(src, "ls-files", "--others", "--exclude-standard").split())
    authored |= set(git(src, "ls-files", "--others", "--ignored", "--exclude-standard").split())
    return sorted(p for p in authored if DOC.search(p) and os.path.isfile(f"{src}/{p}"))


def split(text, rel):
    """(prefix, code block, suffix): a .bats target's Python lives in its <<'PY' heredoc."""
    if not rel.endswith(".bats"):
        return "", text, ""
    lines = text.splitlines(keepends=True)
    s = next(i for i, ln in enumerate(lines) if "<<'PY'" in ln) + 1
    e = next(i for i in range(s, len(lines)) if lines[i].rstrip("\n") == "PY")
    return "".join(lines[:s]), "".join(lines[s:e]), "".join(lines[e:])


IPV4 = re.compile(r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.)(\d{1,3})$")
LISTSTR = re.compile(r"^[\w.-]+(,[\w.-]+){2,}$")


def in_docs(s, doc_text):
    return re.search(rf"(?<![\w.]){re.escape(s)}(?![\w.])", doc_text) is not None


def candidates(text, rel, doc_text):
    """Every intent-defect site, in source order: dicts with desc, line (in the file), start/end (char offsets in the
    file), new (replacement text), sub (test-file substitution (regex, replacement) or None)."""
    prefix, block, _ = split(text, rel)
    tree = ast.parse(block)
    blines = block.splitlines(keepends=True)
    offs = [0]
    for ln in blines:
        offs.append(offs[-1] + len(ln))

    def pos(lineno, col):   # (1-based line, utf-8 byte col) in the block → char offset in the FILE
        return len(prefix) + offs[lineno - 1] + len(blines[lineno - 1].encode()[:col].decode(errors="ignore"))

    guard = set()
    for n in tree.body:
        if (isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
                and n.test.left.id == "__name__"):
            guard |= set(range(n.lineno, n.end_lineno + 1))
    consts = [n for n in ast.walk(tree) if isinstance(n, ast.Constant) and not isinstance(n.value, bool)]
    count = {}
    for n in consts:
        count[repr(n.value)] = count.get(repr(n.value), 0) + 1
    out = []
    for n in ast.walk(tree):
        if getattr(n, "lineno", None) in guard:
            continue
        line = n.lineno + prefix.count("\n") if hasattr(n, "lineno") else 0
        if isinstance(n, ast.Constant) and type(n.value) is int and n.value >= 3 and count[repr(n.value)] == 1 \
                and in_docs(str(n.value), doc_text):
            out.append({"desc": f"int {n.value}->{n.value + 1}", "line": line, "start": pos(n.lineno, n.col_offset),
                        "end": pos(n.end_lineno, n.end_col_offset), "new": str(n.value + 1),
                        "sub": (rf"(?<![\w.]){n.value}(?![\w.])", str(n.value + 1))})
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and count[repr(n.value)] == 1:
            v, m = n.value, IPV4.match(n.value)
            if m and in_docs(v, doc_text):
                nv = f"{m.group(1)}{(int(m.group(2)) + 1) % 256}"
                out.append({"desc": f"ip {v}->{nv}", "line": line, "start": pos(n.lineno, n.col_offset),
                            "end": pos(n.end_lineno, n.end_col_offset), "new": repr(nv).replace("'", '"') if '"' in blines[n.lineno - 1][n.col_offset:n.col_offset + 1] else repr(nv),
                            "sub": (re.escape(v), nv)})
            elif LISTSTR.match(v) and sum(in_docs(x, doc_text) for x in v.split(",")) >= 2 and in_docs(v.split(",")[-1], doc_text):
                nv = ",".join(v.split(",")[:-1])
                q = blines[n.lineno - 1][len(blines[n.lineno - 1].encode()[:n.col_offset].decode(errors="ignore"))]
                out.append({"desc": f"allowlist drop {v.split(',')[-1]!r}", "line": line,
                            "start": pos(n.lineno, n.col_offset), "end": pos(n.end_lineno, n.end_col_offset),
                            "new": f"{q}{nv}{q}", "sub": None})
        elif isinstance(n, (ast.List, ast.Tuple, ast.Set)) and len(n.elts) >= 3 \
                and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts) \
                and sum(in_docs(e.value, doc_text) for e in n.elts) >= 2 and in_docs(n.elts[-1].value, doc_text):
            a, z = n.elts[-2], n.elts[-1]
            out.append({"desc": f"allowlist drop {z.value!r}", "line": z.lineno + prefix.count("\n"),
                        "start": pos(a.end_lineno, a.end_col_offset), "end": pos(z.end_lineno, z.end_col_offset),
                        "new": "", "sub": None})
    return sorted(out, key=lambda c: c["start"])


def apply(d, rel, tests, c):
    """Write the mutant into the copy d; returns how many test occurrences changed."""
    p = f"{d}/{rel}"
    text = open(p).read()
    text = text[:c["start"]] + c["new"] + text[c["end"]:]
    changed = 0
    if c["sub"]:
        rx = re.compile(c["sub"][0])
        if rel.endswith(".bats"):   # small: the bats tests sit outside the Python block of the same file
            prefix, block, suffix = split(text, rel)
            prefix, a = rx.subn(c["sub"][1], prefix)
            suffix, b = rx.subn(c["sub"][1], suffix)
            text, changed = prefix + block + suffix, a + b
        for t in tests:
            tp = f"{d}/{t}"
            new, k = rx.subn(c["sub"][1], open(tp).read())
            if k:
                open(tp, "w").write(new)
                changed += k
    open(p, "w").write(text)
    if rel.endswith(".py") or rel.endswith(".bats"):
        ast.parse(split(text, rel)[1])   # the splice must leave valid Python
    return changed


def own_tests_pass(d, task, tests):
    """Run the trial's own tests in the CI-shaped image; True only on an explicit pass."""
    if task == "green":
        cmd = ["docker", "run", "--rm", "-v", f"{d}/{SCALER}:/src:ro", "python:3.12-slim", "sh", "-c",
               "cp -r /src /w && cd /w && pip install -q --disable-pip-version-check -r requirements.txt pytest httpx "
               ">/dev/null 2>&1 && python -m pytest -q -x -p no:cacheprovider >/dev/null 2>&1 && echo OWN_PASS"]
    else:
        # fail closed: only small keeps its tests in the target itself. Found 2026-11-02: an empty list here used to
        # fall back to the SMALL task's suite, so two vague picks "kept their own tests green" while testing nothing.
        if not tests and task != "small":
            return False
        files = " ".join(tests) if tests else TARGET["small"]
        cmd = ["docker", "run", "--rm", "-v", f"{d}:/src:ro", "-v", f"{B}/toolbox/bin/promtool:/usr/local/bin/promtool:ro",
               "--entrypoint", "sh", "bats/bats:latest", "-c",
               "apk add --no-cache python3 py3-yaml jq git >/dev/null 2>&1; cp -r /src /w && cd /w && "
               f"bats {files} >/dev/null 2>&1 && echo OWN_PASS"]
    return "OWN_PASS" in subprocess.run(cmd, capture_output=True, text=True).stdout


ids = sys.argv[1:] or [f"{t}-{a}" for t in ("small", "brown", "green", "vague") for a in ("aidlc", "bmad", "openspec", "speckit")]
out = open(f"{O}/defects.tsv", "a")
for ident in ids:
    task, arm = ident.split("-", 1)
    src = f"{B}/trials/{ident}"
    tgt = target(task, arm)
    docs = framework_docs(src, arm)
    doc_text = "\n".join(open(f"{src}/{p}", errors="ignore").read() for p in docs)
    tests = own_tests(src, task, tgt) if tgt else []
    pick, why = None, "no candidate"
    if not tgt or not docs:
        why = "no target" if not tgt else "the framework wrote no documents"
    elif not own_tests_pass(src, task, tests):
        why = "own tests fail on the unmutated output (consistency cannot be checked)"
    else:
        cands = candidates(open(f"{src}/{tgt}").read(), tgt, doc_text)
        print(f"{ident}: {len(cands)} candidate(s) from {len(docs)} document(s)", flush=True)
        for n, c in enumerate(cands):
            work = f"{B}/trials/{ident}-int"
            if os.path.exists(work):
                shutil.move(work, f"{B}/trash/{ident}-int-{os.getpid()}-{n}")
            shutil.copytree(src, work, symlinks=True)
            changed = apply(work, tgt, tests, c)
            ok = own_tests_pass(work, task, tests)
            verdict = ""
            if ok:
                verdict = (subprocess.run(["bash", f"{C}/judge_trial.sh", task, arm, "-int"], capture_output=True,
                                          text=True).stdout.strip().splitlines() or [""])[-1]
            print(f"  {c['desc']} at line {c['line']}, tests changed {changed}: own tests "
                  f"{'pass' if ok else 'FAIL'}; judge {verdict[:60]}", flush=True)
            if ok and "FAIL" in verdict:
                pick = (c["desc"], c["line"], changed, verdict)
                break
        else:
            why = "no candidate kept the own tests green and failed the judge"
    if os.path.exists(f"{B}/trials/{ident}-int"):
        shutil.move(f"{B}/trials/{ident}-int", f"{B}/trash/{ident}-int-{os.getpid()}-final")
    row = [task, arm, tgt or "-", *(pick if pick else ("none", "-", "-", why))]
    out.write("\t".join(str(x) for x in row) + "\n")
    out.flush()
    print(f"== {ident}: {'PICK ' + str(pick[0]) + ' at line ' + str(pick[1]) if pick else why}", flush=True)
