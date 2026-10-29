#!/data/data/com.termux/files/usr/bin/bash
# ClipForge local compilation: shuffled source moments with their original audio.
set -euo pipefail
mkdir -p "$HOME/clipforge-output"
echo "Source video full path:"
read -r SOURCE
[ -f "$SOURCE" ] || { echo "File not found: $SOURCE"; exit 1; }
echo "Target minutes (1-30):"
read -r MINS
case "$MINS" in ''|*[!0-9]*) echo "Enter a whole number"; exit 1;; esac
[ "$MINS" -ge 1 ] && [ "$MINS" -le 30 ] || { echo "Minutes must be 1-30"; exit 1; }
echo "Clip length in seconds (recommended 12):"
read -r CLIPSEC
CLIPSEC=${CLIPSEC:-12}
case "$CLIPSEC" in ''|*[!0-9]*) echo "Enter a whole number"; exit 1;; esac
[ "$CLIPSEC" -ge 5 ] && [ "$CLIPSEC" -le 45 ] || { echo "Clip length must be 5-45"; exit 1; }
DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$SOURCE")
AUDIO=$(ffprobe -v error -select_streams a:0 -show_entries stream=index -of csv=p=0 "$SOURCE")
export DUR MINS CLIPSEC
WORK=$(mktemp -d "$HOME/clipforge-output/work_XXXXXX")
trap 'rm -rf "$WORK"' EXIT
python - "$WORK" <<'PY'
import os,sys,random,math
from pathlib import Path
work=Path(sys.argv[1]);dur=float(os.environ["DUR"]);target=min(dur,int(os.environ["MINS"])*60)
step=int(os.environ["CLIPSEC"])
positions=[i*step for i in range(math.ceil(dur/step)) if i*step < dur-0.5]
if not positions:raise SystemExit("No valid clips")
random.SystemRandom().shuffle(positions)
picked=[];remaining=target
for p in positions:
    n=min(step,dur-p,remaining)
    if n>=0.5:picked.append((p,n));remaining-=n
    if remaining<0.5:break
if remaining>0.5:print(f"Warning: output may be {remaining:.1f}s short")
(work/"plan.tsv").write_text("".join(f"{p:.3f}\t{n:.3f}\n" for p,n in picked))
print(f"Selected {len(picked)} clips across the source; target {target:.1f}s",flush=True)
PY
i=0
while IFS=$'\t' read -r START LEN; do
  i=$((i+1))
  printf 'Rendering clip %d at %ss for %ss\n' "$i" "$START" "$LEN"
  OUTCLIP=$(printf '%s/clip_%04d.mp4' "$WORK" "$i")
  if [ -n "$AUDIO" ]; then
    ffmpeg -hide_banner -loglevel error -y -ss "$START" -i "$SOURCE" -t "$LEN" -map 0:v:0 -map 0:a:0 -vf 'scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p' -c:v libx264 -preset ultrafast -crf 29 -threads 2 -c:a aac -ar 48000 -ac 2 -b:a 96k "$OUTCLIP"
  else
    ffmpeg -hide_banner -loglevel error -y -ss "$START" -i "$SOURCE" -f lavfi -t "$LEN" -i 'anullsrc=channel_layout=stereo:sample_rate=48000' -map 0:v:0 -map 1:a:0 -vf 'scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,fps=24,format=yuv420p' -c:v libx264 -preset ultrafast -crf 29 -threads 2 -c:a aac -ar 48000 -ac 2 -b:a 96k -shortest "$OUTCLIP"
  fi
  printf "file '%s'\n" "$OUTCLIP" >> "$WORK/concat.txt"
done < "$WORK/plan.tsv"
OUT="$HOME/storage/downloads/clipforge_remix_$(date +%s).mp4"
echo "Joining shuffled clips..."
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$WORK/concat.txt" -c copy -movflags +faststart "$OUT"
echo "DONE: $OUT"
