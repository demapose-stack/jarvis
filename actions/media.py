"""
Medya oynatma — Windows'ta YouTube, Spotify ve webbrowser ile çalışır.
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from actions.browser import browser_control


SPOTIFY_PATH_CANDIDATES = [
    Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps" / "Spotify.exe",
    Path(r"C:\Program Files\Spotify\Spotify.exe"),
    Path(r"C:\Program Files (x86)\Spotify\Spotify.exe"),
]


def _copy_to_clipboard(text: str) -> tuple[bool, str]:
    try:
        import pyperclip
        pyperclip.copy(text)
        return True, "ok"
    except Exception:
        pass
    try:
        subprocess.run(
            ["clip"],
            input=text.encode("utf-16-le"),
            check=True,
            timeout=5,
        )
        return True, "ok"
    except Exception as exc:
        return False, f"Panoya kopyalanamadı: {exc}"


def _spotify_exe() -> str | None:
    for path in SPOTIFY_PATH_CANDIDATES:
        if path.exists():
            return str(path)
    return None


def _play_youtube(query: str) -> str:
    return browser_control("play_youtube", query=query)


def _play_spotify(query: str, autoplay: bool = True) -> str:
    encoded_query = urllib.parse.quote(query.strip())
    uri = f"spotify:search:{encoded_query}"

    exe = _spotify_exe()
    if exe:
        try:
            os.startfile(uri)
        except Exception:
            try:
                subprocess.Popen(["cmd", "/c", "start", "", uri],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            except Exception as exc:
                return f"Spotify açılamadı: {exc}"

        if not autoplay:
            return f"Spotify içinde '{query}' araması açıldı."

        try:
            import time
            import pyautogui
            time.sleep(2.2)
            pyautogui.press("tab")
            time.sleep(0.2)
            pyautogui.press("down")
            time.sleep(0.2)
            pyautogui.press("enter")
            time.sleep(0.4)
            pyautogui.press("space")
            return f"Spotify'da oynatılıyor: {query}"
        except Exception:
            return f"Spotify araması açıldı ama otomatik oynatma tamamlanamadı: '{query}'"

    # Spotify yüklü değilse web player
    web_url = f"https://open.spotify.com/search/{encoded_query}"
    webbrowser.open(web_url)
    return f"Spotify Web Player'da '{query}' araması açıldı."


def play_media(query: str, provider: str = "auto", autoplay: bool = True) -> str:
    if not query or not query.strip():
        return "Çalınacak içerik belirtilmedi."

    normalized_provider = (provider or "auto").strip().lower()
    if normalized_provider in {"yt", "youtube music"}:
        normalized_provider = "youtube"
    elif normalized_provider in {"apple music", "music", "apple_music"}:
        # Windows'ta Apple Music yok, YouTube'a yönlendir
        normalized_provider = "youtube"

    if normalized_provider == "spotify":
        return _play_spotify(query, autoplay=autoplay)
    if normalized_provider == "youtube":
        return _play_youtube(query)

    # auto: Spotify varsa dene, yoksa YouTube
    if _spotify_exe():
        result = _play_spotify(query, autoplay=autoplay)
        if "açılamadı" not in result and "yüklü görünmüyor" not in result:
            return result
    return _play_youtube(query)
