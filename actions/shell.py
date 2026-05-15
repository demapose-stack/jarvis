"""
Terminal komutu çalıştırma — Windows PowerShell/cmd
"""

import subprocess
import sys


BLOCKED = [
    "rd /s /q c:\\",
    "del /f /s /q c:\\",
    "format c:",
    "diskpart",
    ":(){:|:&};:",
    "shutdown /r",
    "shutdown /s",
    "taskkill /f",
    "reg delete hklm",
    "reg delete hkcu",
    "net user",
    "netsh firewall",
    "bcdedit",
    "bootrec",
]

BLOCKED_PREFIXES = (
    "del ",
    "rd ",
    "rmdir ",
    "move ",
    "copy ",
    "xcopy ",
    "robocopy ",
    "icacls ",
    "takeown ",
    "runas ",
)


def shell_run(command: str, timeout: int = 30) -> str:
    if not command:
        return "Komut belirtilmedi."

    cmd_lower = command.lower().strip()

    if cmd_lower.startswith(BLOCKED_PREFIXES):
        return (
            "Güvenlik: Dosya veya yetki değiştiren komutlar doğrudan çalıştırılmıyor. "
            "Daha güvenli ve dar kapsamlı bir komut dene."
        )

    for blocked in BLOCKED:
        if blocked in cmd_lower:
            return f"Güvenlik: Bu komut engellendi → {blocked}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return "Komut başarıyla çalıştı (çıktı yok)."
        if len(output) > 800:
            output = output[:800] + "\n... (çıktı kısaltıldı)"
        return output
    except subprocess.TimeoutExpired:
        return f"Komut zaman aşımına uğradı ({timeout}s)."
    except Exception as e:
        return f"Hata: {e}"
