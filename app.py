import json, re, subprocess, uuid, asyncio
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import edge_tts

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
CHANNELS = json.loads((ROOT / "channels.json").read_text())
app = FastAPI(title="FAISAL AUTO STUDIO")
app.mount("/assets", StaticFiles(directory=str(ROOT / "static")), name="assets")

def run(args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=900)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-1500:])
    return p.stdout

def duration(path):
    return float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)]).strip())

def scenes(script):
    chunks = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+",script) if x.strip()]
    grouped = []
    current = []
    for sentence in chunks:
        current.append(sentence)
        if len(" ".join(current).split()) >= 32:
            grouped.append(" ".join(current)); current=[]
    if current: grouped.append(" ".join(current))
    return grouped

@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "static" / "index.html").read_text()

@app.get("/api/channels")
def channels():
    return CHANNELS

@app.post("/api/render")
async def render(script: str = Form(...), channel: str = Form("business"), clips: list[UploadFile] = File(...)):
    if len(script.strip()) < 35 or len(script) > 12000:
        raise HTTPException(400,"Script must be 35–12000 characters.")
    profile = next((x for x in CHANNELS if x["id"] == channel),None)
    if not profile: raise HTTPException(400,"Unknown channel.")
    if not clips or len(clips)>20: raise HTTPException(400,"Upload 1–20 clips.")
    job = OUT / uuid.uuid4().hex
    job.mkdir()
    inputs=[]
    for i, clip in enumerate(clips):
        suffix = Path(clip.filename or "").suffix.lower()
        if suffix not in {".mp4",".mov",".webm",".mkv"}:
            raise HTTPException(400,"Video clips only: MP4, MOV, WebM, MKV.")
        p = job / f"input_{i}{suffix}"
        size=0
        with p.open("wb") as f:
            while data := await clip.read(1024*1024):
                size += len(data)
                if size>150*1024*1024: raise HTTPException(413,"Each clip max 150 MB.")
                f.write(data)
        inputs.append(p)
    chunks = scenes(script.strip())
    if len(chunks)>80: raise HTTPException(400,"Too many scenes; shorten script.")
    segments=[]; plan=[]
    try:
        for i, part in enumerate(chunks):
            audio = job / f"voice_{i:03}.mp3"
            await edge_tts.Communicate(part,profile["voice"],rate="-5%").save(str(audio))
            seconds=max(1.0,duration(audio)+0.25)
            src=inputs[i % len(inputs)]
            seg=job / f"segment_{i:03}.mp4"
            # loop footage to cover narration; real video motion, no static slides
            run(["ffmpeg","-y","-stream_loop","-1","-i",str(src),"-i",str(audio),
                 "-t",str(seconds),"-filter_complex",
                 "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p[v]",
                 "-map","[v]","-map","1:a:0","-c:v","libx264","-preset","veryfast",
                 "-crf","23","-c:a","aac","-b:a","160k","-ar","44100",
                 "-shortest","-movflags","+faststart",str(seg)])
            segments.append(seg)
            plan.append({"scene":i+1,"text":part,"footage":src.name,"seconds":round(seconds,2)})
        listing=job/"concat.txt"
        listing.write_text("".join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in segments))
        video=job/"final.mp4"
        run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(listing),
             "-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-b:a","160k",
             "-movflags","+faststart",str(video)])
        (job/"scene_plan.json").write_text(json.dumps({"channel":profile,"scenes":plan},indent=2))
        return {"id":job.name,"video":f"/api/download/{job.name}","plan":f"/api/plan/{job.name}",
                "scenes":len(plan),"duration_seconds":round(duration(video),1)}
    except (RuntimeError,subprocess.TimeoutExpired,Exception) as exc:
        raise HTTPException(500,f"Render failed: {str(exc)[:400]}")

@app.get("/api/download/{job_id}")
def download(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}",job_id): raise HTTPException(404)
    p=OUT/job_id/"final.mp4"
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p,media_type="video/mp4",filename="faisal-auto-studio.mp4")

@app.get("/api/plan/{job_id}")
def plan(job_id: str):
    if not re.fullmatch(r"[0-9a-f]{32}",job_id): raise HTTPException(404)
    p=OUT/job_id/"scene_plan.json"
    if not p.exists(): raise HTTPException(404)
    return FileResponse(p,media_type="application/json",filename="scene_plan.json")
