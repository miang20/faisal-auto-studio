# FAISAL AUTO STUDIO

Android-friendly **self-hosted** documentary video maker. Six independent channel profiles, script-to-scene segmentation, uploaded licensed footage, Edge TTS narration, FFmpeg motion-video editing, and downloadable 1080p MP4. This is an **MVP**, not an unlimited AI text-to-video model.

## What works
- Paste an English script and choose one of six channel profiles.
- In **Automatic mode**, search Wikimedia Commons for license-qualified video clips without an API key. In **Manual mode**, upload **one or more rights-cleared video clips** (MP4/MOV/WebM) to be used as moving footage.
- Generate English voice narration with edge-tts (requires internet).
- Automatically split script into scenes, trim/loop supplied clips to narration length, apply fades, mix audio and export MP4.
- Download video, scene plan and metadata suggestions.

## What is not implemented
- Hollywood clip licensing and autonomous source verification. Wikimedia Commons license metadata is checked, but copyright clearance is not guaranteed.
- Generative AI video shots, lip sync, AI research, autonomous uploads, thumbnails, GPU inference or retention guarantees.
- A permanent free cloud renderer. GitHub hosts code, not the rendering service.
- Video production without uploaded clips or FFmpeg.

## Run (computer / Linux / Colab runtime)
Install **Python 3.10+** and **FFmpeg** (both ffmpeg and ffprobe on PATH).

```bash
git clone https://github.com/miang20/faisal-auto-studio.git
cd faisal-auto-studio
python -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

Open http://localhost:7860 . For Android, run on a reachable server/Colab tunnel; localhost on the phone is **not** the server. Never expose this prototype directly to the public internet without authentication, upload limits and HTTPS.

## Automatic mode caveats\nCommons footage availability is topic-dependent; failed searches or downloads stop the job rather than invent visuals. The manifest lists creator, source and license. CC BY-SA and CC BY can require visible attribution and additional obligations; check each source before uploading. Search and rendering require internet, CPU, disk and FFmpeg. Background job state is in memory, so restarting the runtime loses job status.\n\n## Limits / security
Upload only footage you have permission to use. Internet is required for Edge TTS. Avoid sharing the server publicly: this MVP has no authentication. Outputs are written to local `outputs/`; local jobs are synchronous and long jobs can time out. Storage and compute are your responsibility. No API key is required for the provided functions.

## Quality
Video is built from **real moving clips**, not text-only slides. It is a documentary assembly tool, not Hollywood-quality synthetic video. Test with a 30–60 second script first.
