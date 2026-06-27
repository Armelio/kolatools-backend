import os
import re
import tempfile
import subprocess
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, Response
import yt_dlp

app = FastAPI(title="Kola YouTube Downloader")


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r'[^\x20-\x7E]', "_", name)
    return name.strip()


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
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": f if f != "m4a" else "aac",
                    "preferredquality": "192",
                }
            ]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except Exception as e:
                    raise HTTPException(500, f"Erreur téléchargement: {str(e)[:200]}")

            ext = f if f != "m4a" else "m4a"
            file_path = os.path.join(tmp_dir, f"audio.{ext}")
            if not os.path.exists(file_path):
                # yt-dlp sometimes uses different extension
                files = list(Path(tmp_dir).glob("*"))
                if not files:
                    files = list(Path(tmp_dir).glob("audio.*"))
                if files:
                    file_path = str(files[0])

            if not os.path.exists(file_path):
                raise HTTPException(500, "Fichier audio non trouvé après conversion")

            mime = (
                "audio/mp4"
                if ext in ("m4a", "mp3")
                else "audio/wav"
            )
            media_type = mime
            filename = f"{safe_title}.{ext}"
        else:
            ydl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except Exception as e:
                    raise HTTPException(500, f"Erreur téléchargement: {str(e)[:200]}")

            files = list(Path(tmp_dir).glob("*"))
            if not files:
                raise HTTPException(500, "Fichier vidéo non trouvé")
            file_path = str(files[0])
            media_type = "video/mp4"
            filename = f"{safe_title}.mp4"

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename,
        )
