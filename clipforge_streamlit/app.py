import json, random, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path
import requests
import streamlit as st

st.set_page_config(page_title="ClipForge Auto Studio",page_icon="🎬",layout="wide")
st.title("🎬 ClipForge Auto Studio")
st.caption("Story-first or remix editing • synchronized audio • optional licensed B-roll • MP4 + Shorts + thumbnail")
st.warning("Upload only video you have rights to reuse. B-roll licenses require review. Free cloud hosting may time out on large renders.")

def run(cmd,timeout=600):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr[-900:])
    return p.stdout
def duration(p):
    return float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(p)]).strip())
def has_audio(src):
    return bool(run(["ffprobe","-v","error","-select_streams","a:0","-show_entries","stream=index","-of","csv=p=0",str(src)]).strip())
def cut(src,start,length,out,portrait=False,mute=False,punch=False):
    w,h=(540,960) if portrait else (960,540)
    vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=24,format=yuv420p"
    if punch:
        vf=f"scale={int(w*1.07)//2*2}:{int(h*1.07)//2*2}:force_original_aspect_ratio=increase,crop={w}:{h},fps=24,format=yuv420p"
    cmd=["ffmpeg","-y","-v","error","-ss",str(start),"-i",str(src)]
    use_source_audio=has_audio(src) and not mute
    if not use_source_audio:
        cmd+=["-f","lavfi","-i","anullsrc=channel_layout=stereo:sample_rate=48000"]
    cmd+=["-t",str(length),"-map","0:v:0","-map","0:a:0" if use_source_audio else "1:a:0",
          "-vf",vf,"-af","aresample=async=1:first_pts=0",
          "-c:v","libx264","-preset","ultrafast","-crf","28",
          "-c:a","aac","-ar","48000","-ac","2","-b:a","128k",
          "-shortest",str(out)]
    run(cmd,180)
def lookup(topic):
    response=requests.get("https://commons.wikimedia.org/w/api.php",params={"action":"query","generator":"search","gsrsearch":"filetype:video "+topic,"gsrnamespace":6,"gsrlimit":50,"prop":"imageinfo","iiprop":"url|extmetadata","format":"json"},headers={"User-Agent":"ClipForgeAutoStudio/1.0 (open-source demo)"},timeout=20)
    response.raise_for_status()
    result=[]
    for item in response.json().get("query",{}).get("pages",{}).values():
        info=(item.get("imageinfo") or [{}])[0]
        url=info.get("url","")
        meta=info.get("extmetadata",{})
        license=re.sub("<[^>]*>","",meta.get("LicenseShortName",{}).get("value",""))
        if url.split("?")[0].lower().endswith((".webm",".mp4",".ogv")) and license in ("CC0","Public domain","CC BY 4.0","CC BY 3.0","CC BY-SA 4.0"):
            result.append({"title":item.get("title"),"url":url,"page":info.get("descriptionurl"),"license":license})
    return result
def download(url,path):
    with requests.get(url,stream=True,timeout=40,headers={"User-Agent":"ClipForgeAutoStudio/1.0"}) as r:
        r.raise_for_status()
        count=0
        with open(path,"wb") as f:
            for block in r.iter_content(131072):
                count+=len(block)
                if count>40000000: raise ValueError("B-roll too large")
                f.write(block)

src=st.file_uploader("Upload your source video",type=["mp4","mov","webm"])
topic=st.text_input("Topic for live B-roll search","internet technology")
minutes=st.slider("Target minutes",1,10,8)
edit_mode=st.selectbox("Editing style",["Story-first (chronological)","Remix (shuffled scenes)"],help="Story-first keeps shots in chronological order; Remix changes their order and may interrupt dialogue continuity.")
audio_mode=st.selectbox("Audio treatment",["Original synchronized audio","Mute source audio"],help="Audio is cut together with each video segment. Mute mode outputs silent audio.")
shot_length=st.slider("Average source shot length (seconds)",6,40,20,2)
short_count=st.slider("Number of vertical Shorts",0,3,3)
st.subheader("⚡ Engagement editor")
pacing=st.selectbox("Pacing",["Balanced","Fast-paced","Very fast"],help="Faster pacing uses shorter clips; can cut speech mid-sentence.")
punch_zoom=st.checkbox("Subtle punch-in on alternating shots",True,help="Adds a small static zoom to alternating clips, not AI camera motion.")
st.caption("Fast pacing and zoom add energy, but this version does not detect punchlines, viral moments or sentence boundaries.")
st.caption("Story-first is the safer choice for dialogue, interviews and narrative videos. Remix is intended for independent visual moments.")
broll=st.checkbox("Find Wikimedia Commons B-roll automatically",True,help="Automatically uses available eligible Wikimedia footage. B-roll is silent and may interrupt dialogue; review licenses before publishing.")
st.caption("B-roll quantity is automatic: depends on search results, target duration and free server resources.")
seed=st.number_input("Shuffle seed",min_value=1,max_value=99999,value=42)
if st.button("Generate video package",type="primary",disabled=src is None):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        st.error("Host is missing FFmpeg / ffprobe."); st.stop()
    work=Path(tempfile.mkdtemp(prefix="clipforge_"))
    try:
        inp=work/("source"+Path(src.name).suffix.lower())
        with inp.open("wb") as f:
            while part:=src.read(1048576): f.write(part)
        length=duration(inp)
        if length<15: raise ValueError("Source must be at least 15 seconds")
        target=min(minutes*60,length)
        if target<minutes*60: st.warning("Source shorter than target; output will be shorter")
        rng=random.Random(int(seed))
        step=float(min(shot_length,12 if pacing=="Fast-paced" else 7 if pacing=="Very fast" else shot_length))
        n=max(1,int((target+step-0.001)//step))
        # Sample without duplicating time ranges. Chronological mode retains story order.
        if length <= target+0.5:
            starts=[i*step for i in range(n)]
        else:
            spacing=(length-target)/max(1,n)
            starts=[min(length-step,i*(step+spacing)) for i in range(n)]
        if edit_mode.startswith("Remix"):
            rng.shuffle(starts)
        parts=[]
        bar=st.progress(0)
        for i,start in enumerate(starts):
            seconds=min(step,target-i*step)
            if seconds<=0: break
            out=work/f"part_{i:03}.mp4"
            cut(inp,round(start,2),round(seconds,2),out,mute=audio_mode.startswith("Mute"),punch=punch_zoom and i%2==1)
            parts.append(out)
            bar.progress(min(0.55,(i+1)/n*0.55))
        credits=[]
        if broll:
            try:
                options=lookup(topic);rng.shuffle(options)
                # Avoid overwhelming the free host and drowning out the source.
                count=min(len(options),max(1,int(target//45)),12)
                for item in options:
                    if len(credits)>=count:break
                    raw=work/f"stock_{len(credits)}{Path(item['url'].split('?')[0]).suffix}"
                    try:
                        download(item["url"],raw)
                        sec=min(4,duration(raw))
                        if sec<1:continue
                        out=work/f"stockcut_{len(credits)}.mp4"
                        cut(raw,0,sec,out,mute=True)
                        parts.insert(min(len(parts),max(1,len(parts)//(count+1)*(len(credits)+1))),out)
                        credits.append(item)
                    except Exception:continue
            except Exception as e:st.warning(f"B-roll search unavailable: {e}")
        listing=work/"concat.txt"
        listing.write_text("".join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in parts))
        joined=work/"joined.mp4"
        run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(listing),
             "-c","copy",str(joined)],600)
        final=work/"compilation.mp4"
        # Audio and video are cut together for every shot before rearranging.
        run(["ffmpeg","-y","-v","error","-i",str(joined),"-map","0:v:0","-map","0:a:0",
             "-af","loudnorm=I=-16:TP=-1.5:LRA=11","-c:v","copy",
             "-c:a","aac","-b:a","128k",str(final)],600)
        bar.progress(.8)
        shorts=[]
        for i in range(short_count):
            start=max(0,(i+.5)*duration(final)/3-15)
            clip=work/f"short_{i+1}.mp4"
            # preserve source audio from final during portrait crop
            run(["ffmpeg","-y","-v","error","-ss",str(start),"-i",str(final),"-t","30","-vf","scale=540:960:force_original_aspect_ratio=increase,crop=540:960,fps=24","-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac",str(clip)],240)
            shorts.append(clip)
        thumb=work/"thumbnail.jpg"
        run(["ffmpeg","-y","-v","error","-ss",str(duration(final)/3),"-i",str(final),"-frames:v","1","-vf","scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",str(thumb)],90)
        (work/"BROLL_CREDITS.json").write_text(json.dumps(credits,indent=2))
        (work/"EDIT_SETTINGS.json").write_text(json.dumps({
            "editing_style":edit_mode,"audio":audio_mode,"target_minutes":minutes,
            "source_seconds":round(length,2),"shot_seconds":shot_length,
            "broll_topic":topic if broll else None,"broll_shots":len(credits),
            "shorts":short_count,"seed":int(seed),"pacing":pacing,"punch_zoom":punch_zoom
        },indent=2))
        package=work/"clipforge_outputs.zip"
        with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_STORED) as z:
            for p in [final,*shorts,thumb,work/"BROLL_CREDITS.json",work/"EDIT_SETTINGS.json"]:z.write(p,p.name)
        bar.progress(1.)
        st.success("Render completed")
        st.video(str(final))
        st.caption("Preview the full video and verify cuts, dialogue, B-roll relevance and licensing before publishing.")
        st.download_button("Download full package",package.read_bytes(),"clipforge_outputs.zip","application/zip")
        st.download_button("Download long MP4",final.read_bytes(),"compilation.mp4","video/mp4")
        st.json({"seconds":round(duration(final),1),"B-roll shots":len(credits),"Shorts":short_count,"Editing style":edit_mode,"Audio":audio_mode})
    except Exception as e:
        st.error(f"Render failed: {e}")
