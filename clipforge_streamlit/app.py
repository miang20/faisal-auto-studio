import json, random, re, shutil, subprocess, tempfile, zipfile
from pathlib import Path
import requests
import streamlit as st

st.set_page_config(page_title="ClipForge Auto Studio",page_icon="🎬",layout="wide")
st.title("🎬 ClipForge Auto Studio")
st.caption("Card-free video compilation • Wikimedia Commons B-roll • MP4 + Shorts + thumbnail")
st.warning("Upload only video you have rights to reuse. B-roll licenses require review. Free cloud hosting may time out on large renders.")

def run(cmd,timeout=600):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if p.returncode: raise RuntimeError(p.stderr[-900:])
    return p.stdout
def duration(p):
    return float(run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(p)]).strip())
def cut(src,start,length,out,portrait=False):
    w,h=(540,960) if portrait else (960,540)
    vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=24,format=yuv420p"
    run(["ffmpeg","-y","-v","error","-ss",str(start),"-i",str(src),"-t",str(length),"-vf",vf,"-c:v","libx264","-preset","ultrafast","-crf","28","-an",str(out)],180)
def lookup(topic):
    response=requests.get("https://commons.wikimedia.org/w/api.php",params={"action":"query","generator":"search","gsrsearch":"filetype:video "+topic,"gsrnamespace":6,"gsrlimit":12,"prop":"imageinfo","iiprop":"url|extmetadata","format":"json"},headers={"User-Agent":"ClipForgeAutoStudio/1.0 (open-source demo)"},timeout=20)
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
broll=st.checkbox("Find Wikimedia Commons B-roll automatically",True)
count=st.slider("Maximum B-roll shots",0,4,2)
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
        step=min(20,max(6,target/12))
        n=max(1,int(target/step))
        starts=[max(0,(length-step)*i/max(1,n-1)) for i in range(n)]
        rng.shuffle(starts)
        parts=[]
        bar=st.progress(0)
        for i,start in enumerate(starts):
            seconds=min(step,target-i*step)
            if seconds<=0: break
            out=work/f"part_{i:03}.mp4"
            cut(inp,round(start,2),round(seconds,2),out)
            parts.append(out)
            bar.progress(min(0.55,(i+1)/n*0.55))
        credits=[]
        if broll and count:
            try:
                options=lookup(topic);rng.shuffle(options)
                for item in options:
                    if len(credits)>=count:break
                    raw=work/f"stock_{len(credits)}{Path(item['url'].split('?')[0]).suffix}"
                    try:
                        download(item["url"],raw)
                        sec=min(4,duration(raw))
                        if sec<1:continue
                        out=work/f"stockcut_{len(credits)}.mp4"
                        cut(raw,0,sec,out)
                        parts.insert(min(len(parts),max(1,len(parts)//(count+1)*(len(credits)+1))),out)
                        credits.append(item)
                    except Exception:continue
            except Exception as e:st.warning(f"B-roll search unavailable: {e}")
        listing=work/"concat.txt"
        listing.write_text("".join("file '"+str(p.resolve()).replace("'","'\\''")+"'\n" for p in parts))
        silent=work/"silent.mp4"
        run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",str(listing),"-c:v","libx264","-preset","ultrafast","-crf","28","-an",str(silent)],600)
        final=work/"compilation.mp4"
        # Audio is taken from original video; it will not be semantically aligned to shuffled shots.
        run(["ffmpeg","-y","-v","error","-i",str(silent),"-stream_loop","-1","-i",str(inp),"-map","0:v:0","-map","1:a:0?","-af","loudnorm=I=-16:TP=-1.5:LRA=11","-c:v","copy","-c:a","aac","-b:a","128k","-shortest",str(final)],600)
        bar.progress(.8)
        shorts=[]
        for i in range(3):
            start=max(0,(i+.5)*duration(final)/3-15)
            clip=work/f"short_{i+1}.mp4"
            # preserve source audio from final during portrait crop
            run(["ffmpeg","-y","-v","error","-ss",str(start),"-i",str(final),"-t","30","-vf","scale=540:960:force_original_aspect_ratio=increase,crop=540:960,fps=24","-c:v","libx264","-preset","ultrafast","-crf","28","-c:a","aac",str(clip)],240)
            shorts.append(clip)
        thumb=work/"thumbnail.jpg"
        run(["ffmpeg","-y","-v","error","-ss",str(duration(final)/3),"-i",str(final),"-frames:v","1","-vf","scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",str(thumb)],90)
        (work/"BROLL_CREDITS.json").write_text(json.dumps(credits,indent=2))
        package=work/"clipforge_outputs.zip"
        with zipfile.ZipFile(package,"w",compression=zipfile.ZIP_STORED) as z:
            for p in [final,*shorts,thumb,work/"BROLL_CREDITS.json"]:z.write(p,p.name)
        bar.progress(1.)
        st.success("Render completed")
        st.video(str(final))
        st.download_button("Download full package",package.read_bytes(),"clipforge_outputs.zip","application/zip")
        st.download_button("Download long MP4",final.read_bytes(),"compilation.mp4","video/mp4")
        st.json({"seconds":round(duration(final),1),"B-roll shots":len(credits),"Shorts":3})
    except Exception as e:
        st.error(f"Render failed: {e}")
