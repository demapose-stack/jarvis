"""
TTS (Text-to-Speech) — Windows'ta pyttsx3 kullanır.
Ek kurulum: pip install pyttsx3
"""

import threading


def speak_text(text: str, on_done=None, blocking: bool = False):
    """
    Metni sesli olarak okur.
    on_done: okuma bitince çağrılacak fonksiyon (opsiyonel)
    blocking: True ise bitene kadar bekler
    """
    if not text or not text.strip():
        if on_done:
            on_done()
        return

    max_len = 500
    if len(text) > max_len:
        text = text[:max_len] + "..."

    def _run():
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            voices = engine.getProperty("voices")
            for voice in (voices or []):
                vid = (voice.id or "").lower()
                vname = (voice.name or "").lower()
                if "turkish" in vname or "tr" in vid or "tr-tr" in vid:
                    engine.setProperty("voice", voice.id)
                    break
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
        if on_done:
            on_done()

    if blocking:
        _run()
    else:
        threading.Thread(target=_run, daemon=True).start()


def get_available_voices() -> list[str]:
    """Mevcut TTS seslerini listeler."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        return [v.name for v in voices if v.name]
    except Exception:
        return []
