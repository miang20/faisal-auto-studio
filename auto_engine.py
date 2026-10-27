"""Autonomous keyless documentary assembler using Commons licensed footage.
No promise of generative video or source accuracy. Job status is polled from the UI.
"""
import asyncio, json, re, subprocess, threading, uuid, time
from pathlib import Path
import edge_tts
from footage import search_videos, download_video

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"outputs"
OUT.mkdir(exist_ok=True)
JOBS={}
LOCK=threading.Lock()

def command(args, timeout=1200):
    result=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-900:])
    return result.stdout.strip()

def probe(path):
    return float(command(["ffprobe","-v","error","-show_entries","format=duration",
                          "-of","default=noprint_wrappers=1:nokey=1",str(path)]))

def split_script(script):
    sentences=[x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+",script) if x.strip()]
    result=[]; part=[]
    for s in sentences:
        part.append(s)
        if len(" ".join(part).split())>=35:
            result.append(" ".join(part));part=[]
    if part:result.append(" ".join(part))
    return result

def keywords(text, channel):
    stop={"what","when","where","this","that","with","from","there","their","would","could",
          "should","about","after","before","which","these","those","have","were","will",
          "into","your","because","every","while","then","they","them","just","only","over"}
    words=[w.lower() for w in re.findall(r"[A-Za-z]{4,}",text) if w.lower() not in stop]
    fallback={"business":"city skyline","geography":"mountain landscape","science":"space earth",
              "history":"historical architecture","movies":"cinema projector",
              "engineering":"industrial machines"}
    return " ".join(words[:3]) if words else fallback.get(channel,"landscape")

def set_status(jid, **fields):
    with LOCK:
        JOBS[jid].update(fields)

async def produce(jid, script, profile):
    job=OUT/jid
    job.mkdir(parents=True,exist_ok=True)
    parts=split_script(script)
    if len(parts)>45:raise ValueError("Maximum 45 scenes per job")
    scene_files=[]; credits=[]; plans=[]
    cache={}
    for i,part in enumerate(parts):
        set_status(jid,stage=f"Scene {i+1}/{len(parts)}: narration and licensed footage",
                   progress=round(5+80*i/len(parts)))
        voice=job/f"voice_{i:03}.mp3"
        await edge_tts.Communicate(part,profile["voice"],rate="-5%").save(str(voice))
        seconds=probe(voice)+0.35
        query=keywords(part,profile["id"])
        candidates=search_videos(query,limit=8)
        if not candidates:
            # General fallback is labeled; never claim exact scene match.
            candidates=search_videos("nature landscape",limit=8)
        if not candidates:
            raise RuntimeError("No license-qualified Commons video available. Try a different topic or upload footage in Manual mode.")
        clip=None; chosen=None
        for candidate in candidates:
            url=candidate["url"]
            if url in cache:
                clip=cache[url];chosen=candidate;break
            dest=job/f"source_{len(cache):03}.media"
            try:
                download_video(candidate,dest)
                command(["ffprobe","-v","error","-select_streams","v:0",
                         "-show_entries","stream=codec_name","-of","csv=p=0",str(dest)],timeout=25)
                clip=dest;chosen=candidate;cache[url]=dest;break
            except Exception:
                dest.unlink(missing_ok=True)
                continue
        if clip is None:raise RuntimeError("Commons footage download failed for scene "+str(i+1))
        segment=job/f"scene_{i:03}.mp4"
        fadeout=max(0,seconds-0.3)
        filters=("scale=1280:720:force_original_aspect_ratio=increase,"
                 "crop=1280:720,fps=30,format=yuv420p,"
                 f"fade=t=in:st=0:d=0.25,fade=t=out:st={fadeout:.3f}:d=0.25")
        command(["ffmpeg","-y","-stream_loop","-1","-i",str(clip),"-i",str(voice),
                 "-t",str(seconds),"-filter_complex",f"[0:v]{filters}[v]",
                 "-map","[v]","-map","1:a:0","-c:v","libx264","-preset","veryfast",
                 "-crf","24","-c:a","aac","-ar","44100","-b:a","160k",
                 "-movflags","+faststart",str(segment)])
        scene_files.append(segment)
        plans.append({"scene":i+1,"narration":part,"query":query,
                      "visual_title":chosen["title"],"duration":round(seconds,2)})
        credits.append({"scene":i+1,"title":chosen["title"],"creator":chosen["creator"],
                        "license":chosen["license"],"source":chosen["source"]})
    set_status(jid,stage="Final encoding",progress=90)
    concat=job/"concat.txt"
    concat.write_text("".join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in scene_files))
    video=job/"final.mp4"
    command(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
             "-c:v","libx264","-preset","veryfast","-crf","23",
             "-c:a","aac","-b:a","160k","-movflags","+faststart",str(video)])
    (job/"manifest.json").write_text(json.dumps({
        "channel":profile["name"],"note":"Visual matching is keyword-based, not fact verification.",
        "scenes":plans,"attributions":credits
    },indent=2))
    set_status(jid,stage="Completed",progress=100,state="done",
               video=f"/api/download/{jid}",manifest=f"/api/manifest/{jid}",
               duration=round(probe(video),1))

def start(script,profile):
    jid=uuid.uuid4().hex
    with LOCK:
        JOBS[jid]={"id":jid,"state":"queued","stage":"Waiting","progress":0}
    def worker():
        try:
            set_status(jid,state="running",stage="Starting")
            asyncio.run(produce(jid,script,profile))
        except Exception as exc:
            set_status(jid,state="error",stage="Failed",error=str(exc)[:500])
    threading.Thread(target=worker,daemon=True).start()
    return jid

def status(jid):
    with LOCK:
        return dict(JOBS[jid]) if jid in JOBS else None
