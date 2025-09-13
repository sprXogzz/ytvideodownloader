from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import threading
from urllib.parse import urlparse, parse_qs

app = Flask(__name__, template_folder="templates", static_folder="static")

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

state = {
    "status": "idle",
    "progress": 0.0,
    "title": "",
    "size": "",
    "thumbnail": "",
    "filepath": "",
    "error": "",
    "message": ""
}

def sanitize_filename(title: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()

def clean_youtube_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        vid = qs.get("v", [None])[0]
        if vid:
            return f"https://www.youtube.com/watch?v={vid}"
        if "youtu.be" in parsed.netloc:
            path = parsed.path.strip("/")
            if path:
                return f"https://www.youtube.com/watch?v={path}"
    except Exception:
        pass
    return url

ansi_regex = re.compile(r'\x1b\[[0-9;]*m')

def clean_percent_str(s: str) -> float:
    if not s:
        return 0.0
    s2 = ansi_regex.sub('', s).strip()
    s2 = s2.replace('%', '').strip()
    try:
        return float(s2)
    except:
        m = re.search(r'(\d+(\.\d+)?)', s2)
        if m:
            return float(m.group(1))
    return 0.0

def progress_hook(d: dict):
    status = d.get("status")
    if status == "downloading":
        pct = clean_percent_str(d.get("_percent_str", "0%"))
        state["progress"] = pct
        state["status"] = "downloading"
        state["size"] = d.get("_total_bytes_str") or d.get("total_bytes_str") or state.get("size", "")
    elif status == "finished":
        state["status"] = "finished"
        state["progress"] = 100.0
        fn = d.get("filename")
        if fn:
            state["filepath"] = fn
            try:
                size_bytes = os.path.getsize(fn)
                state["size"] = f"{round(size_bytes / (1024*1024), 2)} MB"
            except:
                pass

def pick_first_entry(info):
    if not info:
        return None
    if "entries" not in info:
        return info
    entries = info["entries"]
    if isinstance(entries, list):
        for e in entries:
            if e:
                return e
        return None
    try:
        for e in entries:
            if e:
                return e
    except TypeError:
        pass
    return None

def download_worker(raw_url: str, format_type: str):
    try:
        state.update({"status":"starting","progress":0.0,"title":"","size":"","thumbnail":"","filepath":"","error":"","message":""})
        url = clean_youtube_url(raw_url)

        # Playlist varsa sadece ilk videoyu al
        with yt_dlp.YoutubeDL({'noplaylist': False}) as ydl_info:
            info_all = ydl_info.extract_info(url, download=False)

        first = pick_first_entry(info_all) or info_all
        video_title = sanitize_filename(first.get("title","Unknown Title"))
        video_url = first.get("webpage_url") or first.get("original_url") or first.get("url")
        thumbnail = first.get("thumbnail") or ""

        state["title"] = video_title
        state["thumbnail"] = thumbnail
        state["message"] = "Playlist URL gönderildi; sadece ilk video indiriliyor." if "entries" in info_all else ""

        outtmpl = os.path.join(DOWNLOAD_FOLDER, f"{video_title}.%(ext)s")

        
        for ext in (".mp3",".mp4",".mkv",".webm",".m4a",".opus"):
            p = os.path.join(DOWNLOAD_FOLDER, f"{video_title}{ext}")
            if os.path.exists(p):
                try: os.remove(p)
                except: pass

        ydl_opts = {
            "outtmpl": outtmpl,
            "progress_hooks": [progress_hook],
            "overwrites": True,
            "noplaylist": True  # sadece tek video indirecen #ogi
        }

        if format_type == "mp3":
            ydl_opts.update({
                "format":"bestaudio/best",
                "postprocessors":[{
                    "key":"FFmpegExtractAudio",
                    "preferredcodec":"mp3",
                    "preferredquality":"192"
                }]
            })
        else:
            ydl_opts.update({
                "format":"bestvideo+bestaudio/best",
                "merge_output_format":"mp4"
            })

        state["status"] = "downloading"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Dosya yolunu doğrula
        fp = state.get("filepath")
        if not fp or not os.path.exists(fp):
            for ext in (".mp3",".mp4",".mkv",".webm"):
                candidate = os.path.join(DOWNLOAD_FOLDER, f"{video_title}{ext}")
                if os.path.exists(candidate):
                    fp = candidate
                    break
            state["filepath"] = fp or ""

        if not fp or not os.path.exists(fp):
            state["status"] = "error"
            state["error"] = "Download finished but output file not found."
        else:
            state["status"] = "finished"
    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def start_download():
    url = request.form.get("url","").strip()
    fmt = request.form.get("format","mp3")
    if not url:
        return ("No URL provided", 400)
    threading.Thread(target=download_worker, args=(url, fmt), daemon=True).start()
    return ("started", 202)

@app.route("/progress")
def get_progress():
    return jsonify(state)

@app.route("/getfile")
def get_file():
    fp = state.get("filepath")
    if fp and os.path.exists(fp):
        return send_file(fp, as_attachment=True)
    return ("file not ready", 404)

if __name__ == "__main__":
    # PowerShell de başlatcan #ogi
    app.run(host="0.0.0.0", port=5000, debug=True)
