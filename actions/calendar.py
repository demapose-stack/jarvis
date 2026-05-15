"""
Takvim aracı — Windows'ta Outlook COM veya web tarayıcı üzerinden çalışır.
Apple Calendar / EventKit Windows'ta mevcut değildir.
"""

from __future__ import annotations

import datetime as dt
import webbrowser


TR_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
TR_MONTHS = ["", "Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz", "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _try_outlook_events(query: str, limit: int) -> str | None:
    """win32com ile Outlook takvim etkinliklerini okumayı dene."""
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        calendar = ns.GetDefaultFolder(9)  # olFolderCalendar
        items = calendar.Items
        items.IncludeRecurrences = True
        items.Sort("[Start]")

        now = dt.datetime.now()
        start_filter = now.strftime("%m/%d/%Y %H:%M %p")
        end_dt = now + dt.timedelta(days=30)
        end_filter = end_dt.strftime("%m/%d/%Y %H:%M %p")
        restriction = f"[Start] >= '{start_filter}' AND [Start] <= '{end_filter}'"
        restricted = items.Restrict(restriction)

        lines = []
        count = 0
        for item in restricted:
            if count >= limit:
                break
            try:
                start = item.Start
                subject = item.Subject or "Adsiz etkinlik"
                location = item.Location or ""
                loc_str = f" @ {location}" if location else ""
                lines.append(f"- {start.strftime('%d %b %H:%M')} — {subject}{loc_str}")
                count += 1
            except Exception:
                continue

        if not lines:
            return "Yaklaşan Outlook takvim etkinliği bulunamadı."
        return f"Outlook takviminde {count} etkinlik:\n" + "\n".join(lines)
    except ImportError:
        return None
    except Exception as exc:
        return None


def get_calendar_events(query: str = "today", limit: int = 6) -> str:
    result = _try_outlook_events(query, limit)
    if result:
        return result
    webbrowser.open("https://calendar.google.com")
    return (
        "Windows'ta doğrudan takvim erişimi için Outlook yüklü ve pywin32 kurulu olmalıdır. "
        "Google Takvim tarayıcıda açıldı. "
        "Outlook kullanıyorsanız 'pip install pywin32' komutuyla entegrasyonu etkinleştirebilirsiniz."
    )


def add_calendar_event(
    title: str,
    start_iso: str,
    end_iso: str = "",
    notes: str = "",
    location: str = "",
    calendar_name: str = "",
    all_day: bool = False,
) -> str:
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        appt = outlook.CreateItem(1)  # olAppointmentItem
        appt.Subject = title
        if location:
            appt.Location = location
        if notes:
            appt.Body = notes
        appt.AllDayEvent = all_day

        start_dt = dt.datetime.fromisoformat(start_iso)
        appt.Start = start_dt.strftime("%m/%d/%Y %H:%M %p")

        if end_iso:
            end_dt = dt.datetime.fromisoformat(end_iso)
            appt.End = end_dt.strftime("%m/%d/%Y %H:%M %p")
        else:
            appt.Duration = 60  # varsayılan 1 saat

        appt.Save()
        return f"Outlook takvimine eklendi: {title} — {start_iso}"
    except ImportError:
        pass
    except Exception as exc:
        return f"Outlook takvim etkinliği eklenemedi: {exc}"

    webbrowser.open("https://calendar.google.com/calendar/r/eventedit")
    return (
        f"Outlook kullanılabilir değil. Google Takvim açıldı. "
        f"Etkinlik: '{title}' — {start_iso}"
    )


def delete_calendar_event(
    title: str,
    start_iso: str = "",
    calendar_name: str = "",
    delete_all_matches: bool = False,
) -> str:
    try:
        import win32com.client
        import pythoncom
        pythoncom.CoInitialize()
        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        calendar = ns.GetDefaultFolder(9)
        items = calendar.Items
        deleted = 0
        to_delete = []
        for item in items:
            try:
                if item.Subject and title.lower() in item.Subject.lower():
                    if start_iso:
                        item_start = str(item.Start)[:16]
                        if start_iso[:16] not in item_start:
                            continue
                    to_delete.append(item)
                    if not delete_all_matches:
                        break
            except Exception:
                continue
        for item in to_delete:
            item.Delete()
            deleted += 1
        if deleted:
            return f"Outlook takviminden {deleted} etkinlik silindi: '{title}'"
        return f"'{title}' adlı etkinlik Outlook takviminde bulunamadı."
    except ImportError:
        pass
    except Exception as exc:
        return f"Outlook takvim etkinliği silinemedi: {exc}"

    return (
        "Outlook kullanılabilir değil. Etkinliği Google Takvim veya Outlook uygulamasından manuel silin."
    )
