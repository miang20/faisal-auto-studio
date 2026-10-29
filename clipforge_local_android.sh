#!/data/data/com.termux/files/usr/bin/bash
# ClipForge Local: basic 10-minute compilation with original audio.
set -e
pkg install -y ffmpeg python
termux-setup-storage
mkdir -p "$HOME/clipforge-output"
echo "Paste full source path (e.g. /sdcard/Download/video.mp4):"
read -r SOURCE
[ -f "$SOURCE" ] || { echo "File not found"; exit 1; }
echo "Target minutes (e.g. 10):"
read -r MINS
case "$MINS" in ''|*[!0-9]*) echo "Use whole number"; exit 1;; esac
[ "$MINS" -ge 1 ] && [ "$MINS" -le 30 ] || { echo "1-30 minutes only"; exit 1; }
DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$SOURCE")
SECS=$(awk -v a="$DUR" -v b="$MINS" 'BEGIN {t=b*60; if(a<t)t=a; printf "%.1f",t}')
OUT="$HOME/clipforge-output/clipforge_$(date +%s).mp4"
echo "Rendering locally. Keep Termux open."
ffmpeg -hide_banner -loglevel error -stats -y -i "$SOURCE" -t "$SECS" -vf "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,fps=24" -c:v libx264 -preset ultrafast -crf 29 -threads 2 -c:a aac -b:a 96k -movflags +faststart "$OUT"
echo "DONE: $OUT"
echo "Copy to Downloads:"
cp "$OUT" "$HOME/storage/downloads/"
echo "Saved in Downloads."
