"""
WhatsApp mesaj gönderme — Windows'ta WhatsApp Desktop veya Web üzerinden çalışır.

Desteklenen akışlar:
- WhatsApp Desktop URL scheme ile numaraya sohbet açma
- WhatsApp Desktop içinde kişi adına göre sohbet arama (pyautogui)
- WhatsApp Web üzerinden telefon numarasıyla taslak açma
- Sık kullanılan kişileri kalıcı belleğe kaydetme
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import unicodedata
import urllib.parse
import webbrowser
from pathlib import Path

from memory.memory_manager import load_memory, update_memory


PREFERRED_BROWSERS = ["chrome", "msedge", "firefox"]
AUTO_SEND_DELAY_SECONDS = 2.4
BASE_DIR = Path(__file__).resolve().parent.parent
PHONEBOOK_FILE = BASE_DIR / "memory" / "phone_book.json"


def _normalize_phone(phone_number: str) -> str:
    digits = re.sub(r"\D+", "", phone_number or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = "90" + digits[1:]
    elif len(digits) == 10:
        digits = "90" + digits
    if len(digits) < 8 or len(digits) > 15:
        raise ValueError(
            "Telefon numarası uluslararası formatta olmalı. "
            "Örn: +905551112233"
        )
    return digits


def _normalize_lookup(text: str) -> str:
    text = (text or "").strip().casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i")
    text = re.sub(r"\s+", " ", text)
    return text


def _contact_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _normalize_lookup(name)).strip("_") or "contact"


def _load_contacts() -> dict:
    memory = load_memory()
    contacts = memory.get("whatsapp_contacts", {})
    return contacts if isinstance(contacts, dict) else {}


def _load_phone_book() -> dict:
    try:
        if PHONEBOOK_FILE.exists():
            return json.loads(PHONEBOOK_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_phone_book(phone_book: dict):
    PHONEBOOK_FILE.parent.mkdir(parents=True, exist_ok=True)
    PHONEBOOK_FILE.write_text(
        json.dumps(phone_book, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _contact_candidates() -> list[dict]:
    candidates = []
    for source_name, source in (("whatsapp", _load_contacts()), ("phone_book", _load_phone_book())):
        if not isinstance(source, dict):
            continue
        for key, entry in source.items():
            if not isinstance(entry, dict):
                continue
            item = dict(entry)
            item.setdefault("display_name", key)
            item["_source"] = source_name
            item["_key"] = key
            candidates.append(item)
    return candidates


def _match_score(needle: str, candidate: str) -> int:
    candidate_norm = _normalize_lookup(candidate)
    if not candidate_norm:
        return 0
    if candidate_norm == needle:
        return 300
    if candidate_norm.startswith(needle) or needle.startswith(candidate_norm):
        return 220
    if needle in candidate_norm:
        return 160
    needle_parts = needle.split()
    if needle_parts and all(part in candidate_norm for part in needle_parts):
        return 120
    return 0


def _find_contact(recipient_name: str) -> dict | None:
    needle = _normalize_lookup(recipient_name)
    if not needle:
        return None

    best_match = None
    best_score = 0
    for entry in _contact_candidates():
        names = [entry.get("display_name", ""), entry.get("_key", "")]
        aliases = entry.get("aliases", [])
        if isinstance(aliases, list):
            names.extend(str(alias) for alias in aliases)
        elif aliases:
            names.append(str(aliases))

        for name in names:
            score = _match_score(needle, name)
            if score > best_score:
                best_score = score
                best_match = entry

    return best_match


def save_whatsapp_contact(display_name: str, phone_number: str, aliases: str = "") -> str:
    if not display_name or not display_name.strip():
        return "Kişi adı boş olamaz."

    try:
        normalized_phone = _normalize_phone(phone_number)
    except ValueError as exc:
        return str(exc)

    alias_list = []
    if aliases and aliases.strip():
        alias_list = [part.strip() for part in aliases.split(",") if part.strip()]

    key = _contact_key(display_name)
    update_memory(
        {
            "whatsapp_contacts": {
                key: {
                    "value": f"+{normalized_phone}",
                    "display_name": display_name.strip(),
                    "aliases": alias_list,
                }
            }
        }
    )

    if alias_list:
        return f"{display_name.strip()} WhatsApp kişilerine kaydedildi. Takma adlar: {', '.join(alias_list)}"
    return f"{display_name.strip()} WhatsApp kişilerine kaydedildi."


def _unfold_vcf_lines(text: str) -> list[str]:
    unfolded = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def import_phone_book_from_vcf(vcf_path: str) -> str:
    source = Path(vcf_path).expanduser()
    if not source.exists():
        return f"Rehber dosyası bulunamadı: {source}"

    try:
        text = source.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Rehber dosyası okunamadı: {exc}"

    entries = {}
    current_lines = []
    imported = 0
    skipped = 0

    def _flush_card(lines: list[str]):
        nonlocal imported, skipped
        if not lines:
            return
        display_name = ""
        aliases = []
        numbers = []
        for line in lines:
            upper = line.upper()
            if upper.startswith("FN:"):
                display_name = line.split(":", 1)[1].strip()
            elif upper.startswith("N:") and not display_name:
                parts = [part.strip() for part in line.split(":", 1)[1].split(";") if part.strip()]
                if parts:
                    display_name = " ".join(reversed(parts[:2])).strip()
            elif "TEL" in upper and ":" in line:
                number = line.split(":", 1)[1].strip()
                if number:
                    numbers.append(number)

        if not display_name or not numbers:
            skipped += 1
            return

        normalized_numbers = []
        for raw_number in numbers:
            try:
                normalized_numbers.append("+" + _normalize_phone(raw_number))
            except ValueError:
                continue
        if not normalized_numbers:
            skipped += 1
            return

        if " " in display_name:
            aliases.extend(part for part in display_name.split() if len(part) > 1)
        key = _contact_key(display_name)
        entries[key] = {
            "display_name": display_name,
            "value": normalized_numbers[0],
            "numbers": normalized_numbers,
            "aliases": sorted({alias for alias in aliases if _normalize_lookup(alias) != _normalize_lookup(display_name)}),
            "source": "vcf_import",
        }
        imported += 1

    for line in _unfold_vcf_lines(text):
        if line.upper() == "BEGIN:VCARD":
            current_lines = []
        elif line.upper() == "END:VCARD":
            _flush_card(current_lines)
            current_lines = []
        else:
            current_lines.append(line)

    phone_book = _load_phone_book()
    phone_book.update(entries)
    _save_phone_book(phone_book)
    return f"{imported} rehber kişisi içe aktarıldı, {skipped} kayıt atlandı."


def _copy_to_clipboard(text: str) -> None:
    try:
        import pyperclip
        pyperclip.copy(text)
        return
    except Exception:
        pass
    subprocess.run(
        ["clip"],
        input=text.encode("utf-16-le"),
        check=True,
        timeout=5,
    )


def _open_in_browser(url: str) -> str:
    webbrowser.open(url)
    return "browser"


def _auto_send_with_pyautogui(delay: float = AUTO_SEND_DELAY_SECONDS) -> tuple[bool, str]:
    try:
        import pyautogui
        time.sleep(delay)
        pyautogui.press("enter")
        return True, "ok"
    except Exception as exc:
        return False, f"Otomatik gönderim tamamlanamadı: {exc}"


def _open_whatsapp_desktop_via_scheme(phone_number: str, message: str) -> tuple[bool, str]:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"whatsapp://send?phone={phone_number}&text={encoded_message}"
    try:
        os.startfile(url)
        return True, "WhatsApp Desktop sohbeti açıldı."
    except Exception:
        pass
    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", url],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True, "WhatsApp Desktop sohbeti açıldı."
    except Exception as exc:
        return False, f"WhatsApp Desktop açılamadı: {exc}"


def _open_whatsapp_desktop_by_name(recipient_name: str, message: str, send_now: bool) -> tuple[bool, str]:
    try:
        import pyautogui
    except ImportError:
        return False, "pyautogui yüklü değil. 'pip install pyautogui' ile yükleyin."

    try:
        subprocess.Popen(
            ["cmd", "/c", "start", "", "whatsapp:"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        _copy_to_clipboard(recipient_name.strip())
    except Exception as exc:
        return False, f"WhatsApp Desktop açılamadı: {exc}"

    try:
        time.sleep(1.5)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1.0)
        pyautogui.press("enter")
    except Exception as exc:
        return False, f"WhatsApp arama otomasyonu başarısız: {exc}"

    try:
        _copy_to_clipboard(message.strip())
        time.sleep(0.7)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.3)
        if send_now:
            pyautogui.press("enter")
            return True, f"WhatsApp Desktop üzerinden {recipient_name.strip()} kişisine mesaj gönderildi."
        return True, f"WhatsApp Desktop üzerinden {recipient_name.strip()} için taslak mesaj açıldı."
    except Exception as exc:
        return False, f"Mesaj yazma otomasyonu başarısız: {exc}"


def _open_whatsapp_web(phone_number: str, message: str) -> tuple[bool, str]:
    encoded_message = urllib.parse.quote(message.strip())
    url = f"https://web.whatsapp.com/send?phone={phone_number}&text={encoded_message}"
    try:
        webbrowser.open(url)
        return True, "browser"
    except Exception as exc:
        return False, f"WhatsApp Web açılamadı: {exc}"


def send_whatsapp_message(
    message: str,
    phone_number: str = "",
    recipient_name: str = "",
    send_now: bool = False,
    app_target: str = "auto",
) -> str:
    if not message or not message.strip():
        return "Mesaj boş olamaz."

    app_target = (app_target or "auto").strip().lower()
    if app_target not in {"auto", "desktop", "web"}:
        app_target = "auto"

    normalized_phone = ""
    if phone_number and phone_number.strip():
        try:
            normalized_phone = _normalize_phone(phone_number)
        except ValueError as exc:
            return str(exc)

    resolved_name = recipient_name.strip() if recipient_name else ""
    contact = _find_contact(resolved_name) if resolved_name else None

    if contact and not normalized_phone:
        stored_phone = str(contact.get("value", "")).strip()
        try:
            normalized_phone = _normalize_phone(stored_phone)
        except ValueError:
            normalized_phone = ""
        resolved_name = str(contact.get("display_name", resolved_name)).strip() or resolved_name
        contact_source = contact.get("_source", "")
    else:
        contact_source = ""

    if resolved_name and normalized_phone and (contact is None or contact.get("_source") == "phone_book"):
        alias_list = contact.get("aliases", []) if isinstance(contact, dict) else []
        aliases = ", ".join(str(alias) for alias in alias_list) if alias_list else ""
        save_whatsapp_contact(resolved_name, normalized_phone, aliases=aliases)

    if app_target in {"auto", "desktop"}:
        if normalized_phone:
            ok, detail = _open_whatsapp_desktop_via_scheme(normalized_phone, message)
            if ok:
                source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
                if not send_now:
                    label = resolved_name or f"+{normalized_phone}"
                    return f"WhatsApp Desktop içinde {label}{source_note} için taslak mesaj açıldı."
                ok_send, send_detail = _auto_send_with_pyautogui()
                if ok_send:
                    label = resolved_name or f"+{normalized_phone}"
                    return f"WhatsApp Desktop üzerinden {label}{source_note} kişisine mesaj gönderildi."
                return (
                    "WhatsApp Desktop sohbeti açıldı ama otomatik gönderim tamamlanamadı. "
                    f"{send_detail}. pyautogui yüklü değilse 'pip install pyautogui' deneyin."
                )
            if app_target == "desktop" and not resolved_name:
                return f"WhatsApp Desktop açılırken hata oldu: {detail}"

        if resolved_name:
            ok, detail = _open_whatsapp_desktop_by_name(resolved_name, message, send_now)
            if ok:
                return detail
            if app_target == "desktop":
                return (
                    "WhatsApp Desktop kişi adına göre açılırken hata oldu. "
                    f"{detail}."
                )

    if not normalized_phone:
        if resolved_name:
            return (
                f"'{resolved_name}' için kayıtlı bir telefon numarası bulamadım ve Desktop araması da tamamlanamadı. "
                "İstersen önce kişiyi numarasıyla kaydet."
            )
        return "WhatsApp mesajı için kişi adı veya telefon numarası gerekli."

    ok, detail = _open_whatsapp_web(normalized_phone, message)
    if not ok:
        return detail

    if not send_now:
        source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
        return (
            f"WhatsApp Web'de {resolved_name or f'+{normalized_phone}'}{source_note} için taslak mesajla açıldı. "
            "Göndermek için Enter'a bas."
        )

    ok_send, send_detail = _auto_send_with_pyautogui()
    if ok_send:
        label = resolved_name or f"+{normalized_phone}"
        source_note = " (rehberden bulundu)" if contact_source == "phone_book" else ""
        return f"WhatsApp Web üzerinden {label}{source_note} kişisine mesaj gönderildi."

    return (
        "WhatsApp Web sohbeti açıldı ama otomatik gönderim tamamlanamadı. "
        f"{send_detail}. 'pip install pyautogui' ile yükleyin."
    )
