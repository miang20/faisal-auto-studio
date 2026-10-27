"""Colab-first Gradio interface. Share URL is temporary and password-protected."""
import os, time, json, secrets
from pathlib import Path
import gradio as gr
from auto_engine import start, status
from app import CHANNELS

OPTIONS={p["name"]:p for p in CHANNELS}

def generate(profile_name, script, progress=gr.Progress()):
    if not script or len(script.strip())<80:
        raise gr.Error("Please paste an English script of at least 80 characters.")
    if len(script)>10000:
        raise gr.Error("Maximum 10,000 characters per render.")
    job_id=start(script.strip(),OPTIONS[profile_name])
    progress(0,desc="Starting")
    while True:
        state=status(job_id)
        if not state:
            raise gr.Error("Runtime lost job state")
        progress(state.get("progress",0)/100,desc=state.get("stage","Working"))
        if state["state"]=="error":
            raise gr.Error(state.get("error","Render failed"))
        if state["state"]=="done":
            folder=Path("outputs")/job_id
            return str(folder/"final.mp4"),str(folder/"manifest.json"),"Completed. Review footage relevance and attribution before uploading."
        time.sleep(3)

with gr.Blocks(title="FAISAL AUTO STUDIO",theme=gr.themes.Soft()) as demo:
    gr.Markdown("# FAISAL AUTO STUDIO\nAutomatic documentary assembly • Free-licensed stock footage • English voice")
    gr.Markdown("**Not generative AI video.** Wikimedia Commons may have no matching footage. Runtime is temporary. Use original scripts and review footage licenses.")
    with gr.Row():
        channel=gr.Dropdown(choices=list(OPTIONS),value=list(OPTIONS)[0],label="Channel")
    script=gr.Textbox(lines=12,label="English narration script",placeholder="Write a documentary with a compelling hook and scene-specific details...")
    go=gr.Button("Generate MP4",variant="primary")
    video=gr.Video(label="Generated video",interactive=False)
    credits=gr.File(label="Scene plan and footage credits")
    msg=gr.Textbox(label="Status")
    go.click(generate,[channel,script],[video,credits,msg],concurrency_limit=1)

if __name__=="__main__":
    # Colab public link requires explicit password; do not commit actual passwords.
    password=os.environ.get("STUDIO_PASSWORD")
    if not password:
        raise SystemExit("Set STUDIO_PASSWORD environment variable before starting.")
    demo.queue(default_concurrency_limit=1).launch(
        share=True,auth=("studio",password),server_name="0.0.0.0",
        show_error=True
    )
