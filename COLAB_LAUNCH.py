# FAISAL AUTO STUDIO: one-cell Colab launcher
# Run in a fresh Google Colab notebook (CPU runtime is sufficient).
import os, secrets, subprocess, sys
from pathlib import Path

repo=Path("/content/faisal-auto-studio")
if not repo.exists():
    subprocess.run(["git","clone","https://github.com/miang20/faisal-auto-studio.git",str(repo)],check=True)
else:
    subprocess.run(["git","-C",str(repo),"pull","--ff-only"],check=True)
os.chdir(repo)
subprocess.run([sys.executable,"-m","pip","install","-q","-r","requirements.txt"],check=True)
subprocess.run([sys.executable,"-m","py_compile","app.py","auto_engine.py","footage.py","colab_ui.py"],check=True)
password=secrets.token_urlsafe(12)
os.environ["STUDIO_PASSWORD"]=password
print("Username: studio")
print("Password:",password)
print("Opening temporary Gradio share link below. Keep this password private.")
print("This notebook must remain running. No unlimited free GPU is included.")
subprocess.run([sys.executable,"colab_ui.py"],check=True)
