#!/bin/bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  terminal_mic_capture.sh OUTPUT.wav [SECONDS] [BACKEND]

Arguments:
  OUTPUT.wav   Destination WAV file
  SECONDS      Capture duration in seconds (default: 5)
  BACKEND      rec | ffmpeg (default: rec)

This launches the capture inside Terminal.app, which lets macOS attribute
microphone access to Terminal instead of the current non-bundled shell.

Examples:
  ./terminal_mic_capture.sh sample.wav
  ./terminal_mic_capture.sh sample.wav 3 rec
  ./terminal_mic_capture.sh sample.wav 3 ffmpeg
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || $# -lt 1 ]]; then
  usage
  exit $([[ $# -lt 1 ]] && echo 1 || echo 0)
fi

output_path="$1"
duration="${2:-5}"
backend="${3:-rec}"

if [[ "$output_path" != /* ]]; then
  output_path="$PWD/$output_path"
fi

mkdir -p "$(dirname "$output_path")"

base="${output_path%.*}"
log_file="${base}.log"
done_file="${base}.done"

rm -f "$done_file"

case "$backend" in
  rec)
    backend_cmd="/opt/homebrew/bin/rec -q -c 1 -r 24000 $(printf '%q' "$output_path") trim 0 $(printf '%q' "$duration")"
    ;;
  ffmpeg)
    backend_cmd="/opt/homebrew/bin/ffmpeg -hide_banner -f avfoundation -i ':0' -t $(printf '%q' "$duration") -ac 1 -ar 16000 $(printf '%q' "$output_path") -y"
    ;;
  *)
    echo "Unsupported backend: $backend" >&2
    exit 2
    ;;
esac

terminal_cmd="cd $(printf '%q' "$PWD"); $backend_cmd > $(printf '%q' "$log_file") 2>&1; echo \$? > $(printf '%q' "$done_file")"
osascript_string=$(python3 - <<PY
import json
print(json.dumps("""$terminal_cmd"""))
PY
)

echo "Launching $backend capture in Terminal.app for $duration second(s)..."
echo "Output: $output_path"
echo "Log:    $log_file"
echo "Done:   $done_file"
echo
echo "If Terminal prompts for microphone access, choose Allow."

osascript \
  -e 'tell application "Terminal" to activate' \
  -e "tell application \"Terminal\" to do script $osascript_string" >/dev/null

max_wait=$((duration + 15))
for ((i = 0; i < max_wait; i++)); do
  if [[ -f "$done_file" ]]; then
    break
  fi
  sleep 1
done

if [[ ! -f "$done_file" ]]; then
  echo "Timed out waiting for Terminal capture to finish." >&2
  exit 3
fi

status="$(cat "$done_file")"
if [[ "$status" != "0" ]]; then
  echo "Terminal capture failed with status $status" >&2
  [[ -f "$log_file" ]] && sed -n '1,120p' "$log_file" >&2
  exit "$status"
fi

python3 - <<PY
import audioop
import os
import sys
import wave

path = """$output_path"""
if not os.path.exists(path):
    print("Capture finished but output file is missing.", file=sys.stderr)
    sys.exit(4)

with wave.open(path, "rb") as wav_file:
    frames = wav_file.readframes(wav_file.getnframes())
    rms = audioop.rms(frames, wav_file.getsampwidth()) if frames else 0
    print(f"channels={wav_file.getnchannels()} rate={wav_file.getframerate()} frames={wav_file.getnframes()} rms={rms}")
PY
