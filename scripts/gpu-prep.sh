#!/usr/bin/env bash
# gpu-prep — prep rogueone's shared 16 GB GPU before a REAL training / bench run
# (vLLM/SGLang bench, model training). Interactive, run it on rogueone.
#
#   1. Shows the GPU and who's holding VRAM.
#   2. Prompts you to CLOSE CHROME — frees ~2-4 GiB AND removes the per-VMA-lock
#      freeze trigger (Chrome's madvise storm). Waits until it's gone. Tabs are in
#      history, so closing it is safe.
#   3. Lets you pick an Ollama VRAM profile (default vs gpt-oss:20b training).
#   4. Drains any resident Ollama models so the card is clean.
#
# NOT for the on-demand eval — that "rides" the shared GPU with drain-only (see
# weyland_pipeline/gpu.py drain_gpu). This is for dedicated, you're-at-the-box runs.
set -euo pipefail

OLLAMA="http://127.0.0.1:11434"
DROPIN="/etc/systemd/system/ollama.service.d/gpu-guardrails.conf"
DEFAULT_OVERHEAD=6442450944   # 6 GiB — desktop + rag-embed baseline (Chrome OPEN). Big models CPU-offload.
TRAIN_OVERHEAD=2684354560     # 2.5 GiB — Chrome CLOSED; leaves ~13.5 GiB so gpt-oss:20b (13 GB) fits on-GPU.

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "== gpu-prep (rogueone) =="
echo "GPU: $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader)"
echo "Holding VRAM:"
nvidia-smi | sed -n '/Processes/,/^$/p' | grep -E 'Xorg|chrome|gnome-shell|python|ollama' || echo "  (none listed)"

# --- 1) Close Chrome ---------------------------------------------------------
if pgrep -x chrome >/dev/null 2>&1; then
  say ">> Chrome is running. Close it now — frees VRAM AND removes the freeze trigger (tabs are in history)."
  read -rp "   Press ENTER once closed, or type 'skip' to leave it: " ans
  if [ "${ans:-}" != "skip" ]; then
    while pgrep -x chrome >/dev/null 2>&1; do echo "   ...waiting for Chrome to close"; sleep 3; done
    echo "   Chrome closed."
  else
    echo "   Leaving Chrome open — big-model profiles may not fit and the freeze risk stays."
  fi
fi

# --- 2) Ollama VRAM profile --------------------------------------------------
say "Ollama VRAM profile:"
echo "  1) default        — reserve 6 GiB (Chrome-open desktop baseline). Safe; big models CPU-offload."
echo "  2) gpt-oss:20b     — reserve 2.5 GiB (Chrome CLOSED) so the 13 GB model fits on-GPU."
echo "                       Marginal: if rag-embed (~1.4 GiB) is also up it may still partly offload —"
echo "                       stop it too, or burst-rent (EMA-190) for real gpt-oss headroom."
read -rp "Profile [1/2] (default 1): " prof
case "${prof:-1}" in
  2) NEW=$TRAIN_OVERHEAD; LABEL="gpt-oss:20b training (2.5 GiB)" ;;
  *) NEW=$DEFAULT_OVERHEAD; LABEL="default (6 GiB)" ;;
esac

CUR=$(grep -oE 'OLLAMA_GPU_OVERHEAD=[0-9]+' "$DROPIN" | cut -d= -f2 || echo "")
if [ "$CUR" != "$NEW" ]; then
  say "Setting OLLAMA_GPU_OVERHEAD -> $LABEL (was ${CUR:-unset}); needs sudo + ollama restart."
  sudo sed -i "s/OLLAMA_GPU_OVERHEAD=[0-9]*/OLLAMA_GPU_OVERHEAD=$NEW/" "$DROPIN"
  sudo systemctl daemon-reload
  sudo systemctl restart ollama
  echo "   ollama restarted with $LABEL."
else
  echo "   Overhead already $LABEL — no change."
fi

# --- 3) Drain resident models ------------------------------------------------
say "Draining resident Ollama models..."
for m in $(curl -s "$OLLAMA/api/ps" | python3 -c 'import sys,json; print(" ".join(x["model"] for x in json.load(sys.stdin).get("models",[])))' 2>/dev/null || true); do
  echo "   unloading $m"; curl -s "$OLLAMA/api/generate" -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null || true
done
sleep 2
echo "GPU now: $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader)"

say "== gpu-prep done — GPU ready. =="
if [ "${prof:-1}" = "2" ]; then
  echo "!! You set a TRAINING profile. Restore desktop headroom after your run:"
  echo "   ./scripts/gpu-prep.sh   (pick profile 1)   — or reboot."
fi
