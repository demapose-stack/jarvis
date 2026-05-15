"""
Uygulama açma/kapatma — Windows'ta cmd start ve taskkill ile çalışır.
"""

import os
import shutil
import subprocess
from pathlib import Path


# Web sitesi olarak açılacak uygulamalar
WEB_ALIASES = {
    "youtube":          "https://www.youtube.com",
    "youtube.com":      "https://www.youtube.com",
    "google":           "https://www.google.com",
    "gmail":            "https://mail.google.com",
    "google mail":      "https://mail.google.com",
    "instagram":        "https://www.instagram.com",
    "twitter":          "https://www.twitter.com",
    "x":                "https://www.x.com",
    "facebook":         "https://www.facebook.com",
    "netflix":          "https://www.netflix.com",
    "twitch":           "https://www.twitch.tv",
    "reddit":           "https://www.reddit.com",
    "github":           "https://www.github.com",
    "linkedin":         "https://www.linkedin.com",
    "tiktok":           "https://www.tiktok.com",
    "whatsapp web":     "https://web.whatsapp.com",
    "chatgpt":          "https://chat.openai.com",
    "spotify web":      "https://open.spotify.com",
    "google drive":     "https://drive.google.com",
    "google docs":      "https://docs.google.com",
    "google maps":      "https://maps.google.com",
    "haritalar web":    "https://maps.google.com",
}

APP_ALIASES = {
    "chrome":              "chrome",
    "google chrome":       "chrome",
    "firefox":             "firefox",
    "edge":                "msedge",
    "microsoft edge":      "msedge",
    "terminal":            "cmd",
    "cmd":                 "cmd",
    "powershell":          "powershell",
    "notepad":             "notepad",
    "not defteri":         "notepad",
    "spotify":             "spotify",
    "vscode":              "code",
    "vs code":             "code",
    "code":                "code",
    "notion":              "notion",
    "slack":               "slack",
    "discord":             "discord",
    "whatsapp":            "WhatsApp",
    "telegram":            "telegram",
    "zoom":                "zoom",
    "calculator":          "calc",
    "hesap makinesi":      "calc",
    "paint":               "mspaint",
    "word":                "winword",
    "excel":               "excel",
    "powerpoint":          "powerpnt",
    "outlook":             "outlook",
    "ayarlar":             "ms-settings:",
    "settings":            "ms-settings:",
    "system settings":     "ms-settings:",
    "dosya gezgini":       "explorer",
    "explorer":            "explorer",
    "görev yöneticisi":    "taskmgr",
    "task manager":        "taskmgr",
    "snipping tool":       "SnippingTool",
    "ekran alıntısı":      "SnippingTool",
    "teams":               "ms-teams:",
    "microsoft teams":     "ms-teams:",
    "maps":                "bingmaps:",
    "haritalar":           "bingmaps:",
    "mail":                "outlookmail:",
    "takvim":              "outlookcal:",
    "calendar":            "outlookcal:",
    "store":               "ms-windows-store:",
    "mağaza":              "ms-windows-store:",
    "photos":              "ms-photos:",
    "fotoğraflar":         "ms-photos:",
    "camera":              "microsoft.windows.camera:",
    "kamera":              "microsoft.windows.camera:",
    "music":               "mswindowsmusic:",
    "müzik":               "mswindowsmusic:",
    "docker":              "docker",
    "postman":             "postman",
    "figma":               "figma",
    "tableplus":           "tableplus",
    "sequel pro":          "tableplus",
}

PROGRAM_DIRS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps",
]


def _try_uri(name: str) -> bool:
    """ms-settings: gibi URI şemalarını dene."""
    if ":" in name and not name.startswith("http"):
        try:
            os.startfile(name)
            return True
        except Exception:
            pass
    return False


def _try_path_command(name: str) -> bool:
    """PATH'te varsa doğrudan çalıştır."""
    if shutil.which(name):
        try:
            subprocess.Popen(
                [name],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
            return True
        except Exception:
            pass
    return False


def _try_shell_start(name: str) -> bool:
    """Windows Shell 'start' komutu ile aç."""
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", name],
            creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,
        )
        return True
    except Exception:
        pass
    return False


def _search_program_dirs(app_name: str) -> str | None:
    name_lower = app_name.lower().replace(" ", "")
    for prog_dir in PROGRAM_DIRS:
        if not prog_dir.exists():
            continue
        # Tek seviye + iki seviye ara
        for exe in list(prog_dir.glob("*.exe")) + list(prog_dir.glob("*/*.exe")) + list(prog_dir.glob("*/*/*.exe")):
            stem = exe.stem.lower().replace(" ", "").replace("-", "").replace("_", "")
            if name_lower in stem or stem in name_lower:
                return str(exe)
    return None


def open_app(app_name: str) -> str:
    """Uygulamayı veya web sitesini açar."""
    if not app_name:
        return "Uygulama adı belirtilmedi."

    normalized = app_name.lower().strip()

    # Önce web sitesi mi kontrol et
    if normalized in WEB_ALIASES:
        import webbrowser
        webbrowser.open(WEB_ALIASES[normalized])
        return f"{app_name} tarayıcıda açıldı."

    # http/https ile başlıyorsa direkt aç
    if normalized.startswith(("http://", "https://", "www.")):
        import webbrowser
        url = normalized if normalized.startswith("http") else "https://" + normalized
        webbrowser.open(url)
        return f"{app_name} tarayıcıda açıldı."

    resolved = APP_ALIASES.get(normalized, app_name)

    if _try_uri(resolved):
        return f"{app_name} açıldı."
    if _try_path_command(resolved):
        return f"{app_name} açıldı."
    if _try_shell_start(resolved):
        return f"{app_name} açıldı."

    exe_path = _search_program_dirs(resolved)
    if exe_path:
        try:
            subprocess.Popen(
                [exe_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return f"{app_name} açıldı."
        except Exception as e:
            return f"'{app_name}' açılırken hata: {e}"

    # Son çare: web'de ara
    import webbrowser, urllib.parse
    webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(app_name)}")
    return f"'{app_name}' bulunamadı, Google'da arandı."


# Uygulama adı → process adı eşlemesi
CLOSE_ALIASES = {
    "chrome":           "chrome.exe",
    "google chrome":    "chrome.exe",
    "firefox":          "firefox.exe",
    "edge":             "msedge.exe",
    "microsoft edge":   "msedge.exe",
    "spotify":          "spotify.exe",
    "discord":          "discord.exe",
    "whatsapp":         "whatsapp.exe",
    "telegram":         "telegram.exe",
    "zoom":             "zoom.exe",
    "slack":            "slack.exe",
    "notepad":          "notepad.exe",
    "not defteri":      "notepad.exe",
    "vscode":           "code.exe",
    "vs code":          "code.exe",
    "code":             "code.exe",
    "word":             "winword.exe",
    "excel":            "excel.exe",
    "powerpoint":       "powerpnt.exe",
    "outlook":          "outlook.exe",
    "teams":            "teams.exe",
    "paint":            "mspaint.exe",
    "calculator":       "calculatorapp.exe",
    "hesap makinesi":   "calculatorapp.exe",
    "explorer":         "explorer.exe",
    "dosya gezgini":    "explorer.exe",
    "cmd":              "cmd.exe",
    "terminal":         "cmd.exe",
    "powershell":       "powershell.exe",
    "notion":           "notion.exe",
    "postman":          "postman.exe",
    "docker":           "docker desktop.exe",
    "figma":            "figma.exe",
}

# Hiçbir zaman kapatılmaması gereken süreçler
PROTECTED = {"explorer.exe", "system", "svchost.exe", "lsass.exe", "csrss.exe"}


def close_app(app_name: str) -> str:
    """Uygulamayı kapatır."""
    if not app_name:
        return "Kapatılacak uygulama adı belirtilmedi."

    normalized = app_name.lower().strip()
    process_name = CLOSE_ALIASES.get(normalized, "")

    # Alias bulunamadıysa isme .exe ekle
    if not process_name:
        guess = normalized.replace(" ", "") + ".exe"
        process_name = guess

    if process_name.lower() in PROTECTED:
        return f"'{app_name}' güvenlik nedeniyle kapatılamaz."

    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", process_name],
            capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            return f"{app_name} kapatıldı."
        # Başarısız olduysa pencere başlığına göre dene
        result2 = subprocess.run(
            ["taskkill", "/f", "/fi", f"WINDOWTITLE eq *{app_name}*"],
            capture_output=True, text=True, timeout=8,
            encoding="utf-8", errors="replace",
        )
        if result2.returncode == 0:
            return f"{app_name} kapatıldı."
        return f"'{app_name}' kapatılamadı veya zaten kapalı."
    except subprocess.TimeoutExpired:
        return f"'{app_name}' kapatılırken zaman aşımı."
    except Exception as e:
        return f"Hata: {e}"
