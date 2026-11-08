# shellcheck shell=bash
# Lab shortcuts for an interactive shell on rogueone (B187 follow-on). Source it from ~/.bashrc:
#
#   source /home/edwardmangini/IdeaProjects/weyland/scripts/lab-shortcuts.sh
#
#   lab-commands [WORD ...]   the lab's command roster from the runbooks, or the entries matching every WORD
#   lab-ask "QUESTION"        ask Claude which runbook command does a job; answers from the roster only
#   vault TOPIC               create (or reopen) a research scratch vault and start Claude in it
#   vault-rm TOPIC            delete a scratch vault (refuses anything that is not one)
#
# All the decisions live in tested Python (scripts/lib/lab_commands.py, scripts/lib/scratch_vault.py); these
# functions only wire them to `claude` and `rm`. Runbook: docs/runbooks/research-scratch-vault.md § Shortcuts.

WEYLAND_REPO="${WEYLAND_REPO:-/home/edwardmangini/IdeaProjects/weyland}"
CLAUDE_OBSIDIAN_HOME="${CLAUDE_OBSIDIAN_HOME:-$HOME/claude-obsidian}"
SCRATCH_VAULTS="${SCRATCH_VAULTS:-$HOME/Documents/scratch-vaults}"
LAB_ASK_MODEL="${LAB_ASK_MODEL:-sonnet}"
export CLAUDE_OBSIDIAN_HOME SCRATCH_VAULTS

lab-commands() {
  if [ "$#" -gt 0 ]; then
    python3 "$WEYLAND_REPO/scripts/lab_commands.py" --grep "$@"
  else
    python3 "$WEYLAND_REPO/scripts/lab_commands.py"
  fi
}

lab-ask() {
  if [ "$#" -eq 0 ]; then
    echo 'usage: lab-ask "what you want to do in the lab"' >&2
    return 2
  fi
  local payload
  payload="$(python3 "$WEYLAND_REPO/scripts/lab_commands.py" --prompt "$@")" || return 2
  # No tools: the answer comes from the roster on stdin, never from running anything. Run from $HOME so the
  # repo's project instructions are not loaded into a one-shot lookup.
  printf '%s\n' "$payload" | (cd "$HOME" && claude -p --model "$LAB_ASK_MODEL" --tools "" --no-session-persistence \
    "Answer the question in the input, following the rules given there.")
}

vault() {
  if [ "$#" -ne 1 ]; then
    echo "usage: vault TOPIC   (a lowercase name, e.g. vault metasearch)" >&2
    return 2
  fi
  local path
  path="$(python3 "$WEYLAND_REPO/scripts/scratch_vault.py" create "$1")" || return 2
  echo "vault: $path"
  echo "Put text sources in $path/inbox (each starting with a Source: URL line), then run /claude-obsidian:wiki-ingest."
  (cd "$path" && claude --plugin-dir "$CLAUDE_OBSIDIAN_HOME")
}

vault-rm() {
  if [ "$#" -ne 1 ]; then
    echo "usage: vault-rm TOPIC" >&2
    return 2
  fi
  local path
  path="$(python3 "$WEYLAND_REPO/scripts/scratch_vault.py" check-rm "$1")" || return 2
  rm -r -- "$path" && echo "deleted $path (also remove it from Obsidian's vault list if you opened it there)"
}
