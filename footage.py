"""Keyless, license-aware Wikimedia Commons video search.
Only returns files whose API metadata includes an accepted free license.
Always preserve creator attribution in the generated manifest.
"""
import html
import re
from urllib.parse import urlparse
import requests

API = "https://commons.wikimedia.org/w/api.php"
ALLOWED = ("cc-by", "cc0", "public domain", "pdm", "cc-by-sa")
HEADERS = {"User-Agent": "FaisalAutoStudio/0.2 (educational documentary assembly; contact via GitHub)"}

def plain(value):
    return re.sub(r"<[^>]+>", "", html.unescape(value or "")).strip()

def search_videos(query, limit=8):
    """Search Commons File namespace; return license-qualified video URLs."""
    query = " ".join(re.findall(r"[a-zA-Z0-9-]+", query)[:5]) or "nature"
    try:
        r = requests.get(API, params={
            "action":"query", "generator":"search", "gsrsearch":f"filetype:video {query}",
            "gsrnamespace":6, "gsrlimit":min(limit*3,30), "prop":"imageinfo",
            "iiprop":"url|extmetadata|mime|size", "format":"json"
        }, headers=HEADERS, timeout=22)
        r.raise_for_status()
        pages = r.json().get("query",{}).get("pages",{})
    except (requests.RequestException, ValueError):
        return []
    results=[]
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta=info.get("extmetadata") or {}
        lic=plain(meta.get("LicenseShortName",{}).get("value","")).lower()
        url=info.get("url","")
        mime=info.get("mime","")
        if not any(tag in lic for tag in ALLOWED):
            continue
        if not mime.startswith("video/") or not url.startswith("https://"):
            continue
        if info.get("size",0)>180*1024*1024:
            continue
        results.append({
            "url":url, "title":page.get("title",""),
            "license":lic, "creator":plain(meta.get("Artist",{}).get("value",""))[:250],
            "source":info.get("descriptionurl",url)
        })
        if len(results)>=limit:break
    return results

def download_video(item, path):
    url=item["url"]
    if urlparse(url).hostname not in ("upload.wikimedia.org",):
        raise ValueError("Unsupported media host")
    with requests.get(url,stream=True,timeout=60,headers=HEADERS) as response:
        response.raise_for_status()
        size=0
        with open(path,"wb") as f:
            for block in response.iter_content(1024*1024):
                if block:
                    size+=len(block)
                    if size>180*1024*1024:
                        raise ValueError("Clip exceeds 180 MB")
                    f.write(block)
    return path
