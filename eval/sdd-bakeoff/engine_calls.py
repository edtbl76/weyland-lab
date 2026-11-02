"""List Bash calls in a trial log whose command matches a pattern, each with the first chars of its tool result
(stdout/stderr or error). Used to see whether a framework's own engine actually ran.
usage: engine_calls.py <run.jsonl> <regex> [max]"""
import json
import re
import sys

pat = re.compile(sys.argv[2])
limit = int(sys.argv[3]) if len(sys.argv) > 3 else 12
calls, results = {}, {}
for line in open(sys.argv[1]):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    msg = e.get("message") if isinstance(e, dict) else None
    content = msg.get("content") if isinstance(msg, dict) else None
    for c in content if isinstance(content, list) else []:
        if not isinstance(c, dict):
            continue
        if c.get("type") == "tool_use" and c.get("name") == "Bash" and pat.search(str((c.get("input") or {}).get("command", ""))):
            calls[c["id"]] = c["input"]["command"]
        if c.get("type") == "tool_result" and c.get("tool_use_id") in calls:
            body = c.get("content")
            if isinstance(body, list):
                body = " ".join(str(x.get("text", "")) for x in body if isinstance(x, dict))
            results[c["tool_use_id"]] = (bool(c.get("is_error")), str(body)[:220].replace("\n", " | "))
print(f"{len(calls)} matching call(s)")
for i, (cid, cmd) in enumerate(calls.items()):
    if i >= limit:
        break
    err, body = results.get(cid, (None, "(no result)"))
    print(f"- {'ERROR ' if err else ''}{cmd[:120]}\n    -> {body}")
