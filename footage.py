"""License-aware Commons video discovery with search fallbacks and diagnostics."""
import html, re, requests
from urllib.parse import urlparse

API="https://commons.wikimedia.org/w/api.php"
HEADERS={"User-Agent":"FaisalAutoStudio/0.3 (https://github.com/miang20/faisal-auto-studio; documentary tool)"}
ALLOWED={"cc0","cc by 4.0","cc by 3.0","cc by-sa 4.0","cc by-sa 3.0","public domain","pdm","cc-by","cc-by-sa"}
MAX_SIZE=180*1024*1024

class CommonsError(RuntimeError):
    pass

def plain(value):
    return re.sub(r"<[^>]+>","",html.unescape(value or "")).strip()

def request_api(params):
    try:
        r=requests.get(API,params={"format":"json","formatversion":2,**params},headers=HEADERS,timeout=30)
        r.raise_for_status()
        payload=r.json()
    except (requests.RequestException,ValueError) as exc:
        raise CommonsError("Wikimedia Commons API unavailable: "+str(exc)[:180]) from exc
    if "error" in payload:
        raise CommonsError("Wikimedia Commons API: "+str(payload["error"])[:180])
    return payload

def items_from_pages(pages,limit):
    result=[]
    for page in pages:
        info=(page.get("imageinfo") or [{}])[0]
        meta=info.get("extmetadata") or {}
        license_name=plain(meta.get("LicenseShortName",{}).get("value","")).lower()
        license_url=plain(meta.get("LicenseUrl",{}).get("value","")).lower()
        combined=license_name+" "+license_url
        # Only known open licenses. Exclude NC/ND and unknown rights.
        if ("-nc" in combined or "-nd" in combined or
            not any(label in combined for label in ALLOWED)):
            continue
        url=info.get("url","")
        if not info.get("mime","").startswith("video/") or not url.startswith("https://upload.wikimedia.org/"):
            continue
        if not 0<info.get("size",0)<=MAX_SIZE:
            continue
        result.append({"url":url,"title":page.get("title",""),"license":license_name,
                       "creator":plain(meta.get("Artist",{}).get("value",""))[:250],
                       "source":info.get("descriptionurl",url)})
        if len(result)>=limit:break
    return result

def search_videos(query,limit=8):
    words=re.findall(r"[A-Za-z0-9-]+",query)
    phrase=" ".join(words[:3]) or "landscape"
    # Wikimedia search indexes filenames/descriptions inconsistently.
    # Try narrower and broader searches, then known Commons video categories.
    searches=[f"filetype:video {phrase}",f"filetype:video {words[0]}" if words else "filetype:video nature",
              "filetype:video landscape","filetype:video city"]
    last_error=None
    for term in dict.fromkeys(searches):
        try:
            payload=request_api({"action":"query","generator":"search","gsrsearch":term,
                "gsrnamespace":6,"gsrlimit":40,"prop":"imageinfo",
                "iiprop":"url|extmetadata|mime|size"})
            matches=items_from_pages(payload.get("query",{}).get("pages",[]),limit)
            if matches:return matches
        except CommonsError as exc:
            last_error=exc
            break
    if last_error:raise last_error
    # Last resort: browse Commons' general video categories.
    for category in ["Category:Videos of landscapes","Category:Videos of cities"]:
        try:
            payload=request_api({"action":"query","generator":"categorymembers","gcmtitle":category,
                "gcmtype":"file","gcmlimit":50,"prop":"imageinfo",
                "iiprop":"url|extmetadata|mime|size"})
            matches=items_from_pages(payload.get("query",{}).get("pages",[]),limit)
            if matches:return matches
        except CommonsError as exc:
            raise exc
    return []

def download_video(item,path):
    url=item["url"]
    if urlparse(url).hostname!="upload.wikimedia.org":
        raise ValueError("Unsupported media host")
    with requests.get(url,stream=True,timeout=90,headers=HEADERS) as response:
        response.raise_for_status()
        size=0
        with open(path,"wb") as f:
            for block in response.iter_content(1024*1024):
                if block:
                    size+=len(block)
                    if size>MAX_SIZE:raise ValueError("Clip exceeds 180 MB")
                    f.write(block)
    return path
