import os
import re
import tempfile
from io import BytesIO
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import Response
import yt_dlp

app = FastAPI(title="Kola YouTube Downloader")

MIME_MAP = {
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "webm": "audio/webm",
    "opus": "audio/opus",
    "mp4": "video/mp4",
}


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r'[^\x20-\x7E]', "_", name)
    return name.strip()


def get_file(tmp_dir: str) -> str:
    files = [f for f in Path(tmp_dir).iterdir() if f.is_file()]
    if files:
        return str(files[0])
    raise HTTPException(500, "Fichier non trouvé après téléchargement")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/download")
def download(
    v: str = Query(..., description="YouTube video ID"),
    f: str = Query("m4a", description="Format: m4a, mp3, wav, mp4"),
    t: str = Query("", description="Title for filename"),
):
    if not v:
        raise HTTPException(400, "Video ID requis")

    url = f"https://www.youtube.com/watch?v={v}"
    safe_title = sanitize_filename(t)[:100] if t else "audio"
    is_audio = f in ("mp3", "wav", "m4a")

    with tempfile.TemporaryDirectory(suffix="-yt-dl") as tmp_dir:
        output_template = os.path.join(tmp_dir, "audio.%(ext)s")

        ydl_opts = {
            "outtmpl": output_template,
            "nocheckcertificate": True,
            "prefer_free_formats": True,
        }

        if is_audio:
            ydl_opts["format"] = "bestaudio/best"
        else:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            except Exception as e:
                raise HTTPException(500, f"Erreur téléchargement: {str(e)[:300]}")

        file_path = get_file(tmp_dir)
        actual_ext = Path(file_path).suffix[1:] or "m4a"

        if is_audio:
            ext = actual_ext
            media_type = MIME_MAP.get(ext, "audio/mp4")
        else:
            ext = "mp4"
            media_type = "video/mp4"

        filename = f"{safe_title}.{ext}"
        data = BytesIO(Path(file_path).read_bytes())

    return Response(content=data.getvalue(), media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"'
    })
