"""Deterministic AST mutation testing for one Python file against a test command (B86 bake-off, layer 1).

usage: mutate.py <repo_dir> <rel_path_of_target.py> <test command run from repo_dir>
For every mutation site it writes the mutant into the target, runs the test command, and restores the original.
A mutant is KILLED when the command exits non-zero (or times out). Prints one JSON line:
{"mutants": N, "killed": K, "survived": S, "score": K/N, "baseline": "pass"|"fail", "survivors": [...]}
If the tests FAIL on the unmutated code the score is meaningless: baseline=fail and no mutants run.

Operators (every site, in source order): comparison swaps (== != < <= > >= in, not in, is, is not), and <-> or,
`not x` -> `x`, True <-> False, int constants c -> c+1 (and 0 -> 1), `return <expr>` -> `return None`,
and deleting a whole `if` body's statement list to `pass` (the branch never acts)."""
import ast
import copy
import json
import os
import subprocess
import sys

repo, rel, cmd = sys.argv[1], sys.argv[2], sys.argv[3]
path = os.path.join(repo, rel)
original = open(path).read()

# A .bats target holds its Python inside a heredoc: the line containing <<'PY' opens it, a line that is exactly PY
# closes it. Mutate that block and re-embed it; everything outside the block is left byte-for-byte.
if rel.endswith(".bats"):
    lines = original.splitlines(keepends=True)
    start = next(i for i, l in enumerate(lines) if "<<'PY'" in l) + 1
    end = next(i for i in range(start, len(lines)) if lines[i].rstrip("\n") == "PY")
    prefix, block, suffix = "".join(lines[:start]), "".join(lines[start:end]), "".join(lines[end:])
else:
    prefix, block, suffix = "", original, ""
tree = ast.parse(block)

CMP_SWAP = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE, ast.LtE: ast.Gt,
            ast.In: ast.NotIn, ast.NotIn: ast.In, ast.Is: ast.IsNot, ast.IsNot: ast.Is}


def sites(t):
    """Yield (description, mutate_fn) where mutate_fn(tree_copy) applies the mutation to the node at the same index."""
    nodes = list(ast.walk(t))
    for i, n in enumerate(nodes):
        if isinstance(n, ast.Compare):
            for j, op in enumerate(n.ops):
                if type(op) in CMP_SWAP:
                    yield f"L{n.lineno} cmp {type(op).__name__}->{CMP_SWAP[type(op)].__name__}", (i, "cmp", j)
        elif isinstance(n, ast.BoolOp):
            yield f"L{n.lineno} {type(n.op).__name__}->{'Or' if isinstance(n.op, ast.And) else 'And'}", (i, "bool", None)
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            yield f"L{n.lineno} drop not", (i, "not", None)
        elif isinstance(n, ast.Constant) and isinstance(n.value, bool):
            yield f"L{n.lineno} {n.value}->{not n.value}", (i, "boolc", None)
        elif isinstance(n, ast.Constant) and type(n.value) is int:
            yield f"L{n.lineno} {n.value}->{n.value + 1}", (i, "int", None)
        elif isinstance(n, ast.Return) and n.value is not None:
            yield f"L{n.lineno} return->None", (i, "ret", None)
        elif isinstance(n, ast.If):
            yield f"L{n.lineno} if-body->pass", (i, "ifbody", None)


def apply(t, spec):
    i, kind, j = spec
    n = list(ast.walk(t))[i]
    if kind == "cmp":
        n.ops[j] = CMP_SWAP[type(n.ops[j])]()
    elif kind == "bool":
        n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
    elif kind == "boolc":
        n.value = not n.value
    elif kind == "int":
        n.value = n.value + 1
    elif kind == "ret":
        n.value = None
    elif kind == "ifbody":
        n.body = [ast.Pass()]
    elif kind == "not":
        # replace the UnaryOp by its operand: rewrite through the parent
        for p in ast.walk(t):
            for field, val in ast.iter_fields(p):
                if val is n:
                    setattr(p, field, n.operand)
                elif isinstance(val, list) and n in val:
                    val[val.index(n)] = n.operand
    return t


if cmd == "--list":
    # list mode: every mutant description, sorted by LINE (ast.walk is breadth-first, so its order puts top-level
    # statements such as the `if __name__ == "__main__":` guard first). Mutants inside the __main__ guard are left out:
    # disabling a script's entry point stops it running at all, which is not a logic defect a reviewer reasons about.
    guard = set()
    for n in tree.body:
        if (isinstance(n, ast.If) and isinstance(n.test, ast.Compare) and isinstance(n.test.left, ast.Name)
                and n.test.left.id == "__name__"):
            guard |= set(range(n.lineno, n.end_lineno + 1))
    items = [(int(desc.split()[0][1:]), k, desc) for k, (desc, _) in enumerate(sites(tree))]
    print(json.dumps([desc for line, _, desc in sorted(items) if line not in guard]))
    sys.exit(0)

if cmd == "--apply":
    # apply mode: write ONE named mutant (its description as listed in `survivors`) into the target and stop.
    # usage: mutate.py <repo> <rel> --apply "<desc>"   → exit 0 written · exit 3 no such mutant
    # The mutant must change ONLY the mutated node's own source text (comments, blank lines and formatting stay
    # byte-identical): a whole-file ast.unparse would strip every comment, and a reviewer must see real code.
    want = sys.argv[4]
    lines = block.splitlines(keepends=True)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln))

    def pos(lineno, col):  # (1-based line, utf-8 byte col) → char offset in block
        return offs[lineno - 1] + len(lines[lineno - 1].encode()[:col].decode(errors="ignore"))

    orig_nodes = list(ast.walk(tree))
    for desc, spec in sites(tree):
        if desc != want:
            continue
        i, kind, _ = spec
        node = orig_nodes[i]
        mutated_tree = apply(copy.deepcopy(tree), spec)
        if kind == "ifbody":
            first, last = node.body[0], node.body[-1]
            indent = lines[first.lineno - 1][: len(lines[first.lineno - 1]) - len(lines[first.lineno - 1].lstrip())]
            start, end = offs[first.lineno - 1], offs[last.end_lineno]
            new = block[:start] + indent + "pass\n" + block[end:]
        elif kind == "not":
            start, end = pos(node.lineno, node.col_offset), pos(node.end_lineno, node.end_col_offset)
            new = block[:start] + "(" + ast.get_source_segment(block, node.operand) + ")" + block[end:]
        else:
            start, end = pos(node.lineno, node.col_offset), pos(node.end_lineno, node.end_col_offset)
            # the mutated counterpart sits at the same walk index only if the tree shape is unchanged (true for these kinds)
            repl = ast.unparse(list(ast.walk(mutated_tree))[i])
            new = block[:start] + repl + block[end:]
        try:
            ast.parse(new)
        except SyntaxError as exc:
            print(json.dumps({"applied": None, "error": f"splice broke the syntax: {exc}"}))
            sys.exit(4)
        open(path, "w").write(prefix + new + suffix)
        # absolute line in the FILE (a .bats target's block starts after `prefix`, so add its line count)
        line = (node.lineno if kind != "ifbody" else node.body[0].lineno) + prefix.count("\n")
        print(json.dumps({"applied": desc, "line": line}))
        sys.exit(0)
    print(json.dumps({"applied": None, "error": f"no mutant {want!r}"}))
    sys.exit(3)


def run_tests():
    try:
        return subprocess.run(cmd, shell=True, cwd=repo, capture_output=True, timeout=120).returncode
    except subprocess.TimeoutExpired:
        return 124


base = run_tests()
if base != 0:
    print(json.dumps({"mutants": 0, "killed": 0, "survived": 0, "score": None, "baseline": "fail"}))
    sys.exit(0)
killed, survivors, total = 0, [], 0
try:
    for desc, spec in sites(tree):
        mutant = apply(copy.deepcopy(tree), spec)
        try:
            src = ast.unparse(ast.fix_missing_locations(mutant))
        except Exception:
            continue
        if src == ast.unparse(tree):
            continue
        open(path, "w").write(prefix + src + ("\n" if prefix else "") + suffix)
        total += 1
        if run_tests() != 0:
            killed += 1
        else:
            survivors.append(desc)
finally:
    open(path, "w").write(original)
print(json.dumps({"mutants": total, "killed": killed, "survived": total - killed,
                  "score": round(killed / total, 3) if total else None, "baseline": "pass", "survivors": survivors[:40]}))
