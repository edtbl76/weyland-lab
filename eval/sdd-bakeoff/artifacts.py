"""Per trial, what the run produced relative to its starting commit, in three classes:
  code       — files the task is about (outside any framework folder)
  docs       — edits to the repo's existing docs (docs/**, other *.md) the trial made while doing the task
  framework  — the framework's own process artifacts: spec/plan/task/review folders wherever it put them
               (openspec/, specs/ at any depth, _bmad-output/, aidlc-docs/ [gitignored], .specify/ changes)
Size: a NEW file counts its full bytes; a MODIFIED file counts only the bytes of its added lines (`git diff`), so
editing a 1.2 MB backlog by one paragraph counts one paragraph.  → results/artifacts.tsv"""
import os
import re
import subprocess

B = os.environ.get("SDD_BAKEOFF_HOME", "/home/edwardmangini/sdd-bakeoff")   # work dir (outside the repo)
C = os.path.dirname(os.path.abspath(__file__))   # harness code: eval/sdd-bakeoff in the repo
FRAMEWORK = re.compile(r"(^|/)(openspec|specs|_bmad-output|aidlc-docs)(/|$)")
# runtime bookkeeping, not authored documents: AI-DLC's session transcripts / hook markers / state, BMAD's rendered
# workflow templates, Spec Kit's own config edits
RUNTIME = re.compile(r"^(aidlc/|_bmad/|\.specify/)")
# ...except AI-DLC's AUTHORED documents, which live inside its workspace: the codekb reverse-engineering docs and the
# intent's stage artifacts (Markdown under aidlc/spaces/, outside its dot-folders)
AIDLC_AUTHORED = re.compile(r"^aidlc/spaces/(?:[^/.][^/]*/)*[^/.][^/]*\.md$")


def classify(path):
    if AIDLC_AUTHORED.search(path):
        return "framework"
    if RUNTIME.search(path):
        return "runtime"
    if FRAMEWORK.search(path):
        return "framework"
    if path.startswith("docs/") or path.endswith(".md"):
        return "docs"
    return "code"
SKIP = re.compile(r"(__pycache__|\.pyc$|\.pytest_cache)")


def git(d, *args):
    return subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, check=True).stdout


def added_bytes(d, path):
    diff = git(d, "diff", "--unified=0", "--", path)
    return sum(len(l) - 1 for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))


def measure(d):
    tot = {"code": [0, 0], "docs": [0, 0], "framework": [0, 0], "runtime": [0, 0]}
    # --ignored=matching lists ignored FILES one by one (plain --ignored collapses an ignored folder to one dir entry)
    for line in git(d, "status", "--porcelain", "--ignored=matching", "--untracked-files=all").splitlines():
        status, path = line[:2], line[3:].split(" -> ")[-1]
        full = os.path.join(d, path)
        # git may report an untracked/ignored DIRECTORY as one entry (e.g. `!! _bmad/render/bmad-build/`, whose ignore
        # rule names the folder): expand it so every file inside is counted, whichever way git collapsed it.
        if os.path.isdir(full) and status in ("??", "!!"):
            for root, _, names in os.walk(full):
                for nm in names:
                    p = os.path.join(root, nm)
                    rel = os.path.relpath(p, d)
                    if not SKIP.search(rel) and not os.path.islink(p):
                        cls = classify(rel)
                        tot[cls][0] += 1
                        tot[cls][1] += os.path.getsize(p)
            continue
        if SKIP.search(path) or not os.path.isfile(full) or os.path.islink(full):
            continue
        size = os.path.getsize(full) if status in ("??", "!!") else added_bytes(d, path)
        cls = classify(path)
        tot[cls][0] += 1
        tot[cls][1] += size
    return tot


rows = []
for task in ("small", "brown", "green", "vague"):
    for arm in ("none", "aidlc", "bmad", "openspec", "speckit"):
        if not os.path.exists(f"{B}/results/{task}-{arm}.meta"):
            continue
        t = measure(f"{B}/trials/{task}-{arm}")
        rows.append("\t".join([task, arm] + [str(v) for c in ("code", "docs", "framework", "runtime") for v in t[c]]))
with open(f"{B}/results/artifacts.tsv", "w") as f:
    f.write("task\tarm\tcode_files\tcode_bytes\tdocs_files\tdocs_added_bytes\tspec_files\tspec_bytes\truntime_files\truntime_bytes\n" + "\n".join(rows) + "\n")
print(open(f"{B}/results/artifacts.tsv").read())
