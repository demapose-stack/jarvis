"""
Hatırlatıcı aracı — Windows'ta Outlook Görevleri veya web tarayıcı üzerinden çalışır.
Apple Reminders / EventKit Windows'ta mevcut değildir.
"""

from __future__ import annotations

import datetime as dt
import webbrowser


TR_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _try_outlook_tasks(query: str, limit: int, list_name: str) -> str | None:
    """win32com ile Outlook görevlerini okumayı dene."""
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        tasks_folder = ns.GetDefaultFolder(13)  # olFolderTasks
        items = tasks_folder.Items

        lines = []
        count = 0
        now = dt.datetime.now()
        for item in items:
            if count >= limit:
                break
            try:
                if item.Complete:
                    continue
                subject = item.Subject or "Adsiz gorev"
                due = item.DueDate
                if due and due.year > 1900:
                    due_str = due.strftime("%d %b %H:%M")
                else:
                    due_str = "tarihi yok"
                lines.append(f"- {due_str} — {subject}")
                count += 1
            except Exception:
                continue

        if not lines:
            return "Bekleyen Outlook görevi bulunamadı."
        return f"Outlook'ta {count} görev:\n" + "\n".join(lines)
    except ImportError:
        return None
    except Exception:
        return None


def get_reminders(query: str = "upcoming", limit: int = 8, list_name: str = "") -> str:
    result = _try_outlook_tasks(query, limit, list_name)
    if result:
        return result
    webbrowser.open("https://tasks.google.com")
    return (
        "Windows'ta doğrudan hatırlatıcı erişimi için Outlook yüklü ve pywin32 kurulu olmalıdır. "
        "Google Görevler tarayıcıda açıldı. "
        "Outlook kullanıyorsanız 'pip install pywin32' komutuyla entegrasyonu etkinleştirebilirsiniz."
    )


def add_reminder(
    title: str,
    due_iso: str = "",
    notes: str = "",
    list_name: str = "",
    priority: str = "",
    all_day: bool = False,
) -> str:
    if not title or not title.strip():
        return "Hatırlatıcı başlığı boş olamaz."

    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        task = outlook.CreateItem(3)  # olTaskItem
        task.Subject = title.strip()
        if notes:
            task.Body = notes
        if priority:
            prio_map = {"high": 2, "medium": 1, "low": 0}
            task.Importance = prio_map.get(priority.lower(), 1)
        if due_iso and due_iso.strip():
            try:
                due_dt = dt.datetime.fromisoformat(due_iso)
                task.DueDate = due_dt.strftime("%m/%d/%Y %H:%M %p")
            except Exception:
                pass
        task.Save()
        when = f" — {due_iso}" if due_iso else ""
        return f"Outlook görevi oluşturuldu: {title}{when}"
    except ImportError:
        pass
    except Exception as exc:
        return f"Outlook görevi oluşturulamadı: {exc}"

    webbrowser.open("https://tasks.google.com")
    return (
        f"Outlook kullanılabilir değil. Google Görevler açıldı. "
        f"Hatırlatıcı: '{title}'"
        + (f" — {due_iso}" if due_iso else "")
    )
