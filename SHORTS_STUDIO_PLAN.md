# Shorts Studio — Android offline production branch

This branch is reserved for a separate Android Shorts APK. The existing ClipForge application on `main` must remain unchanged.

## Product contract (v1)
- Input: user-selected local 1080p+ video, typically 10–30 minutes.
- Analyze the entire video; identify complete visual scenes and rank engaging funny moments.
- Generate unique 9:16 Shorts (15–60 seconds) with a configurable target count; never repeat source time ranges or manufacture filler to hit 24.
- Prefer subject/face-aware reframing; safe centered crop fallback. Preserve audio sync and original ambient sound.
- Render at 1080x1920, preserve source FPS up to 60, H.264/AAC MP4, configurable bitrate and export directory.
- Sponsor preset: optional logo overlay with size, position, opacity and start/end settings; optional locally supplied, licensed music with volume ducking. No music/logo by default.
- Export a batch manifest with clip IDs, source time ranges, output names, render status and sponsor preset used.
- Android offline-first; no paid APIs; batch queue and foreground notification during export; tolerate app going to background.
- Avoid duplicate clips, truncated first/last seconds, black bars, and audio drift.

## Isolation and acceptance
- Develop a separate app identity and APK artifact on this branch; do not replace or modify the original ClipForge install.
- Validate real source videos for output duration, uniqueness, A/V sync, cropping, and export success.
- Build with GitHub Actions after identifying the existing repository's actual Android build layout.
- Do not advertise a finished APK until an Android build succeeds and an installable artifact is available.

## Current status
Specification and branch initialized. Implementation, build, and device validation are pending.
