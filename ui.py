"""
JARVIS — Minimal HUD Interface
Dark Navy / Blue Neon — Matching reference design
"""

import math
import random
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import psutil
import tkinter as tk
from tkinter import font as tkfont

from app_config import has_gemini_api_key, load_app_config, save_app_config

BASE_DIR = Path(__file__).resolve().parent

# ── Renkler ───────────────────────────────────────────────────────────────────
C_BG        = "#141924"
C_GRID      = "#1c2232"
C_GRID_ACT  = "#242d42"
C_ORB_INNER = "#050e1a"
C_ORB_RING  = "#0088ff"
C_ORB_GLOW  = "#003366"
C_WHITE     = "#ffffff"
C_TEXT      = "#ccdcff"
C_TEXT2     = "#4466aa"
C_TICK      = "#99bbdd"
C_ACCENT    = "#00aaff"
C_GREEN     = "#00ff88"
C_RED       = "#ff2244"
C_GOLD      = "#ffaa00"
C_DIM       = "#0a1020"
C_BORDER    = "#1e2d44"

ORB_COLORS = {
    "LISTENING":    (0,  136, 255),
    "SPEAKING":     (0,  200, 255),
    "THINKING":     (80, 160, 255),
    "MUTED":        (160, 50,  0),
    "PAUSED":       (30,  60, 100),
    "ERROR":        (255, 30,  50),
    "INITIALISING": (0,   80, 200),
}
STATE_LABELS = {
    "LISTENING":    "LISTENING",
    "SPEAKING":     "SPEAKING",
    "THINKING":     "PROCESSING",
    "MUTED":        "MUTED",
    "PAUSED":       "PAUSED",
    "ERROR":        "ERROR",
    "INITIALISING": "INITIALISING",
}

VOICES = ["Charon", "Puck", "Aoede", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]


# ── SoundManager ──────────────────────────────────────────────────────────────
class SoundManager:
    def __init__(self):
        self._enabled = True
        self._volume  = 0.20

    def start_ambient(self):  pass
    def play_startup(self):   self._play(BASE_DIR / "SFX" / "Start.mp3")
    def play_success(self):   self._play(BASE_DIR / "SFX" / "Done.mp3")
    def play_error(self):     self._play(BASE_DIR / "SFX" / "Error.mp3")
    def start_thinking(self): pass
    def stop_thinking(self):  pass
    def stop_all(self):       pass
    def get_volume(self):     return self._volume
    def set_volume(self, v):  self._volume = max(0.0, min(1.0, float(v)))
    def toggle(self):
        self._enabled = not self._enabled
        return self._enabled
    def set_enabled(self, e): self._enabled = bool(e)

    def _play(self, path: Path):
        if not self._enabled or not path.exists():
            return
        def _r():
            try:
                import subprocess
                subprocess.Popen(
                    ["powershell", "-c",
                     f"Add-Type -AssemblyName presentationCore;"
                     f"$p=New-Object System.Windows.Media.MediaPlayer;"
                     f"$p.Open('{path}');$p.Play();Start-Sleep 4"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except Exception:
                pass
        threading.Thread(target=_r, daemon=True).start()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _rgb(r, g, b):
    return f"#{int(max(0,min(255,r))):02x}{int(max(0,min(255,g))):02x}{int(max(0,min(255,b))):02x}"


# ── Ana UI ────────────────────────────────────────────────────────────────────
class JarvisUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("JARVIS")
        self.root.update_idletasks()

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.W = sw
        self.H = sh
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)
        self.root.state("zoomed")  # Windows tam ekran
        self.root.attributes("-topmost", True)
        self.root.after(3000, lambda: self.root.attributes("-topmost", False))

        # Fontlar
        avail = set(tkfont.families())
        self._fm = next((f for f in ["Consolas","Courier New","Lucida Console"] if f in avail), "Courier New")
        self._fu = next((f for f in ["Segoe UI","Arial"] if f in avail), "Arial")
        self._marvel = self._load_marvel_font()

        # ── Durum ─────────────────────────────────────────────────────────────
        self._state      = "INITIALISING"
        self._orb_col    = list(ORB_COLORS["INITIALISING"])
        self._tgt_col    = list(ORB_COLORS["INITIALISING"])
        self.muted       = False
        self.paused      = False
        self._tick       = 0
        self._started_at = time.time()
        self._err_until  = 0.0
        self._user_act   = 0.0
        self._settings_open = False
        self._debug_entries = deque(maxlen=120)
        self._panel_focus       = ""
        self._panel_focus_until = 0.0
        self.setup_frame        = None
        self.api_entry          = None
        self.youtube_api_entry  = None
        self.youtube_handle_entry = None
        self._current_voice     = self._load_voice()
        self._weather_temp      = "--"
        self._weather_city      = "ISTANBUL"
        self._weather_text      = []

        # Stats
        self._stats = {"cpu": 0.0, "ram": 0.0, "disk": 0.0, "battery": 100.0}

        # Callbacks
        self.on_text_command         = None
        self.on_pause_toggle         = None
        self.on_stop_command         = None
        self.on_voice_change         = None
        self.on_effects_state_change = None
        self.sound = SoundManager()

        # ── Animasyon verileri ────────────────────────────────────────────────
        # Orb ring açıları
        self._ring_angles = [0.0, 90.0, 180.0, 270.0]
        self._ring_speeds = [0.9, -0.6, 0.4, -1.1]

        # HUD tick döndürme açısı
        self._hud_rot = 0.0

        # Altın arc'lar (yay şeklinde, orb çevresini kısmen kaplıyor)
        extents = [72, 216, 108, 288, 54, 180, 90, 252, 36, 144, 198, 324]
        self._gold_arcs = [
            {
                "start":  random.uniform(0, 360),
                "extent": extents[i],           # kaç derece kaplar
                "speed":  random.uniform(0.25, 0.85) * random.choice([-1, 1]),
                "radius": random.uniform(1.18, 1.55),  # orb_r katı
                "alpha":  random.uniform(0.55, 0.95),
                "width":  random.choice([1, 1, 2, 2, 3]),
                "ph":     random.uniform(0, math.tau),
            }
            for i in range(12)
        ]

        # Orb içi partiküller
        self._orb_p = [
            {
                "nx":  random.gauss(0, 0.30),
                "ny":  random.gauss(0, 0.30),
                "sz":  random.uniform(0.8, 2.5),
                "br":  random.uniform(0.3, 0.9),
                "ph":  random.uniform(0, math.tau),
                "sp":  random.uniform(0.02, 0.07),
            }
            for _ in range(80)
        ]
        # Merkez temiz kalsın: 0.35'ten küçük olanları çıkar
        self._orb_p = [p for p in self._orb_p
                       if 0.38 < p["nx"]**2 + p["ny"]**2 < 0.74][:45]

        # Ses dalgası
        self._wave = [random.uniform(1, 5) for _ in range(22)]

        # Grid parlama (aktif olunca belirir)
        self._grid_alpha = 0.0

        # Log satırları
        self._log_lines = deque(maxlen=6)

        # ── Canvas ────────────────────────────────────────────────────────────
        self.cv = tk.Canvas(self.root, width=self.W, height=self.H,
                            bg=C_BG, highlightthickness=0)
        self.cv.place(x=0, y=0)

        # ── Metin girişi (alt ortada) ──────────────────────────────────────────
        inp_w = min(500, int(self.W * 0.35))
        self._inp_var = tk.StringVar()
        self._inp = tk.Entry(
            self.root, textvariable=self._inp_var,
            bg="#0d1520", fg=C_TEXT, font=(self._fm, 10),
            relief="flat", bd=0, insertbackground=C_ACCENT,
            selectbackground="#1a2a44",
        )
        self._inp.place(x=(self.W - inp_w)//2, y=self.H - 42,
                        width=inp_w, height=28)
        self._inp.bind("<Return>", self._on_enter)

        # ── Alt butonlar ──────────────────────────────────────────────────────
        bx = (self.W - inp_w)//2 + inp_w + 12
        self._btn_pause = self._mk_btn("⏸",  bx,      self.H-42, self._toggle_pause)
        self._btn_mute  = self._mk_btn("🔊",  bx+44,   self.H-42, self._toggle_mute)
        self._btn_set   = self._mk_btn("⚙",  bx+88,   self.H-42, self._open_settings)

        # Pre-create canvas items
        self._build_grid_items()
        self._build_orb_items()

        self.root.bind("<Configure>", self._on_resize)
        self._animate()
        self._update_stats()
        self._refresh_weather()

    # ── Font ─────────────────────────────────────────────────────────────────
    def _load_marvel_font(self) -> str:
        font_path = BASE_DIR / "Fonts" / "Orbitron.ttf"
        if font_path.exists():
            try:
                import ctypes
                ctypes.windll.gdi32.AddFontResourceExW(str(font_path), 0x10, 0)
                self.root.update()
                for name in tkfont.families():
                    if "orbitron" in name.lower():
                        return name
                return "Orbitron"
            except Exception:
                pass
        return "Arial Black"

    # ── Buton fabrikası ───────────────────────────────────────────────────────
    def _mk_btn(self, txt, x, y, cmd):
        b = tk.Button(self.root, text=txt, bg="#0d1520", fg=C_TEXT,
                      font=(self._fu, 11), relief="flat", bd=0,
                      activebackground="#1a2535", activeforeground=C_WHITE,
                      cursor="hand2", command=cmd)
        b.place(x=x, y=y, width=36, height=28)
        return b

    # ── Grid canvas item'ları (bir kere oluştur) ───────────────────────────────
    def _build_grid_items(self):
        self.cv.delete("grid")
        spacing = 46
        self._grid_ids = []
        for x in range(0, self.W + spacing, spacing):
            lid = self.cv.create_line(x, 0, x, self.H, fill=C_GRID, width=1, tags="grid")
            self._grid_ids.append(lid)
        for y in range(0, self.H + spacing, spacing):
            lid = self.cv.create_line(0, y, self.W, y, fill=C_GRID, width=1, tags="grid")
            self._grid_ids.append(lid)

    # ── Orb canvas item'ları (bir kere oluştur) ────────────────────────────────
    def _build_orb_items(self):
        # Glow hale katmanları (8 adet)
        self._glow_ids = [
            self.cv.create_oval(-10,-10,-10,-10, fill=C_DIM, outline="")
            for _ in range(8)
        ]
        # Ana orb
        self._orb_id = self.cv.create_oval(-10,-10,-10,-10, fill=C_ORB_INNER, outline="")
        # Ring arcs (4 adet)
        self._ring_ids = [
            self.cv.create_arc(-10,-10,-10,-10, start=0, extent=260,
                               outline=C_WHITE, fill="", width=3, style="arc")
            for _ in range(4)
        ]
        # Orb içi partiküller
        self._part_ids = [
            self.cv.create_oval(-5,-5,-5,-5, fill="#0a1525", outline="")
            for _ in range(len(self._orb_p))
        ]
        # Hub merkez noktası
        self._hub_id = self.cv.create_oval(-5,-5,-5,-5, fill=C_WHITE, outline="")
        # Altın arc'lar (12 adet)
        self._gold_line_ids = [
            self.cv.create_arc(-10,-10,-10,-10, start=0, extent=72,
                               outline=C_GOLD, fill="", width=2, style="arc")
            for _ in range(12)
        ]
        # HUD tick/corner id'leri artık kullanılmıyor ama referans hatası olmaması için boş bırak
        self._tick_ids   = []
        self._dot_ids    = []
        self._corner_ids = []
        # Ses dalgası arki
        self._wave_id = self.cv.create_arc(-10,-10,-10,-10, start=200, extent=140,
                                            outline=C_GREEN, fill="", width=2, style="arc")

    # ── Ana animasyon ─────────────────────────────────────────────────────────
    def _animate(self):
        try:
            self._tick += 1
            self.cv.delete("dynamic")
            self._lerp_color()
            self._update_grid_alpha()
            self._draw_frame()
        except Exception:
            pass
        self.root.after(50, self._animate)

    def _lerp_color(self):
        for i in range(3):
            self._orb_col[i] += (self._tgt_col[i] - self._orb_col[i]) * 0.07

    def _update_grid_alpha(self):
        active = self._state in ("LISTENING", "SPEAKING", "THINKING")
        target = 1.0 if active else 0.0
        self._grid_alpha += (target - self._grid_alpha) * 0.05
        # Grid rengi güncelle
        v = int(self._grid_alpha * 255)
        col = _rgb(
            int(C_GRID[1:3], 16) * (1 - self._grid_alpha) + int(C_GRID_ACT[1:3], 16) * self._grid_alpha,
            int(C_GRID[3:5], 16) * (1 - self._grid_alpha) + int(C_GRID_ACT[3:5], 16) * self._grid_alpha,
            int(C_GRID[5:7], 16) * (1 - self._grid_alpha) + int(C_GRID_ACT[5:7], 16) * self._grid_alpha,
        )
        for lid in self._grid_ids:
            self.cv.itemconfig(lid, fill=col)

    def _draw_frame(self):
        W, H   = self.W, self.H
        tick   = self._tick
        r, g, b = self._orb_col

        # Orb merkezi
        cx = W // 2
        cy = int(H * 0.44)
        orb_r = min(W, H) * 0.135

        # ── Glow haleler (ince, az katman) ────────────────────────────────────
        for i, gid in enumerate(self._glow_ids):
            fr = (i + 1) / len(self._glow_ids)
            gr = orb_r * (1.0 + fr * 0.38)
            gc = _rgb(r * fr * 0.12, g * fr * 0.12, b * fr * 0.18)
            self.cv.coords(gid, cx-gr, cy-gr, cx+gr, cy+gr)
            self.cv.itemconfig(gid, fill=gc)

        # ── Ana orb ───────────────────────────────────────────────────────────
        pulse = 1.0 + math.sin(tick * 0.06) * 0.010
        self.cv.coords(self._orb_id,
            cx - orb_r*pulse, cy - orb_r*pulse,
            cx + orb_r*pulse, cy + orb_r*pulse)
        # Mavi dış çizgi — ince (width=1)
        self.cv.itemconfig(self._orb_id, fill=C_ORB_INNER,
                           outline=_rgb(r*0.55, g*0.55, b), width=1)

        # ── Dönen ring arcs ────────────────────────────────────────────────────
        is_act = self._state in ("SPEAKING", "THINKING")
        ring_configs = [
            (0.95, 280, 3, 1.0),
            (0.88, 200, 2, 0.75),
            (1.00, 120, 3, 0.90),
            (0.82, 320, 2, 0.60),
        ]
        for i, (rid, (rf, ext, w, alpha)) in enumerate(zip(self._ring_ids, ring_configs)):
            self._ring_angles[i] = (self._ring_angles[i] + self._ring_speeds[i] * (1.5 if is_act else 1.0)) % 360
            rr = orb_r * rf
            # Beyaz tonları — tam beyaz ile hafif mavi beyaz arası
            v  = int(alpha * 255)
            rc = _rgb(v, v, min(255, v + 10))
            self.cv.coords(rid, cx-rr, cy-rr, cx+rr, cy+rr)
            self.cv.itemconfig(rid, start=self._ring_angles[i], extent=ext,
                               outline=rc, width=w)

        # ── Orb içi partiküller ───────────────────────────────────────────────
        for i, p in enumerate(self._orb_p):
            tw = 0.5 + 0.5 * math.sin(tick * p["sp"] + p["ph"])
            a  = p["br"] * tw
            px = cx + p["nx"] * orb_r * 0.82
            py = cy + p["ny"] * orb_r * 0.82
            if (px-cx)**2 + (py-cy)**2 > (orb_r*0.88)**2:
                self.cv.coords(self._part_ids[i], -5,-5,-5,-5)
                continue
            if a > 0.7 and p["sz"] > 1.8:
                pc = _rgb(min(255,180+a*75), min(255,210+a*45), 255)
            else:
                pc = _rgb(a*60, a*130, a*255)
            pr = p["sz"] * (0.6 + a * 0.4)
            self.cv.coords(self._part_ids[i], px-pr, py-pr, px+pr, py+pr)
            self.cv.itemconfig(self._part_ids[i], fill=pc)

        # ── Parlak merkez ─────────────────────────────────────────────────────
        ip = 1.0 + math.sin(tick * 0.08) * 0.15
        cr = orb_r * 0.06 * ip
        self.cv.coords(self._hub_id, cx-cr, cy-cr, cx+cr, cy+cr)
        self.cv.itemconfig(self._hub_id,
            fill=_rgb(min(255,r*1.5+80), min(255,g*1.5+80), 255))

        # ── JARVIS yazısı — temiz merkez, gölgeli ────────────────────────────
        fs = int(orb_r * 0.28)
        # Koyu arka plan (yazının okunması için)
        cr2 = orb_r * 0.42
        self.cv.create_oval(cx-cr2, cy-cr2, cx+cr2, cy+cr2,
            fill="#050e1a", outline="", tags="dynamic")
        # Gölge
        self.cv.create_text(cx+2, cy+2, text="JARVIS",
            fill="#001122", font=(self._marvel, fs, "bold"),
            anchor="center", tags="dynamic")
        # Neon mavi glow
        for ox, oy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
            self.cv.create_text(cx+ox, cy+oy, text="JARVIS",
                fill=_rgb(r*0.4, g*0.4, b*0.5),
                font=(self._marvel, fs, "bold"),
                anchor="center", tags="dynamic")
        # Ana yazı — beyaz
        self.cv.create_text(cx, cy, text="JARVIS",
            fill="#ffffff", font=(self._marvel, fs, "bold"),
            anchor="center", tags="dynamic")

        # ── Altın dönen uzun çizgiler ──────────────────────────────────────────
        self._draw_gold_lines(cx, cy, orb_r)

        # ses dalgası kaldırıldı

        # ── JARVIS durum etiketi ───────────────────────────────────────────────
        state_lbl  = STATE_LABELS.get(self._state, self._state)
        blink      = (tick // 18) % 2 == 0
        lbl        = state_lbl if blink else ""
        self.cv.create_text(cx, cy + orb_r + 22, text=lbl,
            fill=_rgb(r*0.7, g*0.7, b*0.7),
            font=(self._fm, 9), anchor="center", tags="dynamic")

        # ── Saat / tarih (boştayken büyük, aktifken küçük) ────────────────────
        self._draw_time(cx, cy, orb_r)

        # ── Üst köşe info ──────────────────────────────────────────────────────
        self._draw_top_bar()

        # ── Log overlay (altta) ───────────────────────────────────────────────
        self._draw_log_overlay()

        # ── Metin giriş çerçevesi ─────────────────────────────────────────────
        inp_w = min(500, int(self.W * 0.35))
        ix = (self.W - inp_w) // 2
        iy = self.H - 44
        self.cv.create_rectangle(ix-1, iy-1, ix+inp_w+1, iy+30,
            outline=C_BORDER, fill="#0d1520", tags="dynamic")

    def _draw_gold_lines(self, cx, cy, orb_r):
        """Orb etrafında farklı açı kapsamında dönen altın arc'lar."""
        is_act = self._state in ("SPEAKING", "THINKING", "LISTENING")
        for i, ga in enumerate(self._gold_arcs):
            ga["start"] = (ga["start"] + ga["speed"] * (1.3 if is_act else 1.0)) % 360

            rr    = orb_r * ga["radius"]
            pulse = 0.65 + 0.35 * math.sin(self._tick * 0.035 + ga["ph"])
            a     = ga["alpha"] * pulse
            v     = int(a * 255)
            col   = _rgb(v, int(v * 0.70), 0)  # altın

            lid = self._gold_line_ids[i]
            self.cv.coords(lid, cx-rr, cy-rr, cx+rr, cy+rr)
            self.cv.itemconfig(lid,
                start=ga["start"],
                extent=ga["extent"],
                outline=col,
                width=ga["width"])

    def _draw_hud_ticks(self, cx, cy, radius, alpha):
        """Image 4/5'teki dönen HUD tick işaretleri."""
        rot  = self._hud_rot
        # 8 pozisyon (her 45°)
        tick_types = [
            ("long",  0),   ("short", 45),  ("long",  90),  ("short", 135),
            ("long",  180), ("short", 225), ("long",  270), ("short", 315),
        ]
        dot_angles = [22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5]

        tc = _rgb(int(alpha * 180), int(alpha * 200), int(alpha * 220))
        dc = _rgb(int(alpha * 120), int(alpha * 150), int(alpha * 180))

        for i, (ttype, base_angle) in enumerate(tick_types):
            angle_rad = math.radians(base_angle + rot)
            tx = cx + radius * math.cos(angle_rad)
            ty = cy + radius * math.sin(angle_rad)

            # Tick yönü: radyal (içe doğru)
            inner = 10 if ttype == "long" else 6
            outer = 0
            ix1 = tx + inner * math.cos(angle_rad)
            iy1 = ty + inner * math.sin(angle_rad)
            ix2 = tx - outer * math.cos(angle_rad)
            iy2 = ty - outer * math.sin(angle_rad)

            # "Long" tiplerde çift çizgi (|| veya =)
            perp = angle_rad + math.pi / 2
            gap  = 3 if ttype == "long" else 1.5
            for sign in (-1, 1) if ttype == "long" else (0,):
                ox = sign * gap * math.cos(perp)
                oy = sign * gap * math.sin(perp)
                tid = self._tick_ids[i * 2 + (0 if sign <= 0 else 1)]
                self.cv.coords(tid,
                    ix1 + ox, iy1 + oy, tx + ox, ty + oy)
                self.cv.itemconfig(tid, fill=tc, width=1)

        # Araya küçük dot'lar
        for i, da in enumerate(dot_angles):
            angle_rad = math.radians(da + rot)
            dx = cx + radius * math.cos(angle_rad)
            dy = cy + radius * math.sin(angle_rad)
            dr = 2.5
            self.cv.coords(self._dot_ids[i],
                dx-dr, dy-dr, dx+dr, dy+dr)
            self.cv.itemconfig(self._dot_ids[i], fill=dc)

        # Köşe braketleri (4 köşe, square targeting)
        sq_r = radius * 0.88
        corners = [45, 135, 225, 315]
        bk_len  = 14
        for i, ca in enumerate(corners):
            angle_rad  = math.radians(ca + rot)
            bx = cx + sq_r * math.cos(angle_rad)
            by = cy + sq_r * math.sin(angle_rad)
            perp = angle_rad + math.pi / 2
            # İki kol
            ax1 = bx + bk_len * math.cos(angle_rad)
            ay1 = by + bk_len * math.sin(angle_rad)
            ax2 = bx + bk_len * math.cos(perp)
            ay2 = by + bk_len * math.sin(perp)
            self.cv.coords(self._corner_ids[i*2],   bx, by, ax1, ay1)
            self.cv.coords(self._corner_ids[i*2+1], bx, by, ax2, ay2)
            bc = _rgb(int(alpha*200), int(alpha*220), int(alpha*240))
            self.cv.itemconfig(self._corner_ids[i*2],   fill=bc, width=2)
            self.cv.itemconfig(self._corner_ids[i*2+1], fill=bc, width=2)

    def _draw_wave_arc(self, cx, cy, orb_r):
        """Orb alt kısmında ses dalgası."""
        is_s  = self._state == "SPEAKING"
        is_u  = time.time() < self._user_act
        r_, g_, b_ = self._orb_col

        if is_s:
            wave_col = C_GREEN;   amp_m = 1.6
        elif is_u:
            wave_col = C_WHITE;   amp_m = 1.2
        else:
            wave_col = _rgb(r_*0.6, g_*0.6, b_*0.6); amp_m = 0.5

        # Dalga noktaları (altta yay)
        n    = len(self._wave)
        ww   = orb_r * 1.6
        wy0  = cy + orb_r * 0.6
        tick = self._tick
        pts  = []
        for i, amp in enumerate(self._wave):
            wx = cx - ww/2 + (i/(n-1)) * ww
            wy = wy0 + math.sin(tick*0.1 + i*0.4) * amp * amp_m
            pts.extend([wx, wy])
        if len(pts) >= 4:
            self.cv.create_line(*pts, fill=_rgb(
                int(C_DIM[1:3],16), int(C_DIM[3:5],16), int(C_DIM[5:7],16)
            ), width=4, smooth=True, tags="dynamic")
            self.cv.create_line(*pts, fill=wave_col,
                                width=2, smooth=True, tags="dynamic")

    def _draw_time(self, cx, cy, orb_r):
        now   = datetime.now()
        is_idle = self._state == "INITIALISING" or (
            self._state == "LISTENING" and self._grid_alpha < 0.3)
        size_time = int(orb_r * 0.38) if is_idle else int(orb_r * 0.22)
        size_date = 9

        size_time = int(orb_r * 0.22)
        size_date = 10
        ty = cy + orb_r + 130

        # Gölge
        self.cv.create_text(cx+2, ty+2, text=now.strftime("%H:%M"),
            fill="#000a14", font=(self._marvel, size_time, "bold"),
            anchor="center", tags="dynamic")
        # Ana saat — beyaz
        self.cv.create_text(cx, ty, text=now.strftime("%H:%M"),
            fill="#ffffff", font=(self._marvel, size_time, "bold"),
            anchor="center", tags="dynamic")
        # Tarih — beyaz, Marvel fontu
        self.cv.create_text(cx, ty + size_time + 10,
            text=now.strftime("%A  %d  %B").upper(),
            fill="#ffffff", font=(self._marvel, size_date),
            anchor="center", tags="dynamic")

    def _draw_top_bar(self):
        W = self.W
        # Sağ üst: durum
        blink = (self._tick // 20) % 2 == 0
        dot   = "●" if blink else "○"
        self.cv.create_text(W-14, 16, text=f"{dot} ONLINE",
            fill="#00ff88", font=(self._fm, 9, "bold"), anchor="e", tags="dynamic")

        # Sol üst: hava durumu
        self.cv.create_text(14, 16, text=f"{self._weather_temp}  {self._weather_city}",
            fill=C_TEXT2, font=(self._fm, 9), anchor="w", tags="dynamic")

    def _draw_log_overlay(self):
        """Altta son mesajları göster."""
        if not self._log_lines:
            return
        lx  = 16
        ly  = self.H - 80
        lw  = int(self.W * 0.38)
        for i, (tag, txt) in enumerate(list(self._log_lines)[-4:]):
            col = (C_ACCENT if tag == "jarvis" else
                   C_TEXT   if tag == "user"   else
                   C_TEXT2)
            self.cv.create_text(lx, ly + i * 16, text=txt[:60],
                fill=col, font=(self._fm, 8), anchor="w", tags="dynamic")

    def _update_wave(self):
        is_s = self._state == "SPEAKING"
        is_t = self._state == "THINKING"
        for i in range(len(self._wave)):
            tgt = (random.uniform(5, 22) if is_s else
                   random.uniform(2, 10)  if is_t else
                   random.uniform(0.5, 3))
            self._wave[i] += (tgt - self._wave[i]) * 0.12

    # ── İstatistik güncelleme ─────────────────────────────────────────────────
    def _update_stats(self):
        try:
            self._stats["cpu"]  = psutil.cpu_percent()
            self._stats["ram"]  = psutil.virtual_memory().percent
            self._stats["disk"] = psutil.disk_usage("C:\\").percent
            bat = psutil.sensors_battery()
            self._stats["battery"] = bat.percent if bat else 100.0
        except Exception:
            pass
        self.root.after(3000, self._update_stats)

    def _refresh_weather(self):
        def _fetch():
            try:
                import re
                from actions.weather import get_weather_summary
                raw = get_weather_summary("Istanbul")
                if not raw or "alınamadı" in raw:
                    return
                m = re.search(r"(\d+)\s*derece", raw)
                if m:
                    self._weather_temp = f"{m.group(1)}°C"
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()
        self.root.after(300000, self._refresh_weather)

    # ── Public API ─────────────────────────────────────────────────────────────
    def set_state(self, state: str):
        if state == "ERROR":
            if self._err_until > time.time():
                return
            self._err_until = time.time() + 3.0
        self._state   = state
        self._tgt_col = list(ORB_COLORS.get(state, ORB_COLORS["LISTENING"]))

    def write_log(self, text: str):
        if not text:
            return
        self.root.after(0, lambda: self._append_log(text))

    def _append_log(self, text: str):
        t = text.strip()
        tag = ("jarvis" if t.startswith("JARVIS") else
               "user"   if t.startswith("Siz:")   else
               "err"    if t.startswith("ERR:")   else "sys")
        self._log_lines.append((tag, t[:70]))

    def write_debug(self, text: str, level: str = "INFO"):
        self._debug_entries.append((time.time(), level, text))

    def mark_user_activity(self, active: bool):
        if active:
            self._user_act = time.time() + 2.0

    def focus_panel(self, panel: str, duration_ms: int = 3000):
        self._panel_focus       = panel
        self._panel_focus_until = time.time() + duration_ms / 1000.0

    def play_success_sfx(self): self.sound.play_success()
    def play_error_sfx(self):   self.sound.play_error()

    # ── Buton aksiyonları ─────────────────────────────────────────────────────
    def _toggle_mute(self):
        self.muted = not self.muted
        self._btn_mute.config(fg=C_RED if self.muted else C_TEXT)
        self.set_state("MUTED" if self.muted else "LISTENING")

    def _toggle_pause(self):
        self.paused = not self.paused
        self._btn_pause.config(fg="#cc4400" if self.paused else C_TEXT)
        if self.on_pause_toggle:
            self.on_pause_toggle(self.paused)
        self.set_state("PAUSED" if self.paused else "LISTENING")

    # ── Giriş ─────────────────────────────────────────────────────────────────
    def _on_enter(self, event=None):
        text = self._inp_var.get().strip()
        if not text:
            return
        self._inp_var.set("")
        if self.on_text_command:
            self.on_text_command(text)

    # ── Ayarlar ───────────────────────────────────────────────────────────────
    def _open_settings(self):
        if self._settings_open:
            return
        self._settings_open = True
        win = tk.Toplevel(self.root)
        win.title("JARVIS — Ayarlar")
        win.configure(bg=C_BG)
        win.geometry("460x320")
        win.resizable(False, False)
        win.grab_set()

        def on_close():
            self._settings_open = False
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

        tk.Label(win, text="JARVIS  AYARLARI", bg=C_BG, fg=C_ACCENT,
                 font=(self._marvel, 12, "bold")).pack(pady=(18, 4))

        def lbl(t):
            tk.Label(win, text=t, bg=C_BG, fg=C_TEXT2,
                     font=(self._fm, 9), anchor="w").pack(fill="x", padx=24, pady=(8,0))
        def ent(default=""):
            e = tk.Entry(win, bg=C_DIM, fg=C_TEXT, font=(self._fm, 10),
                         relief="flat", bd=0, insertbackground=C_ACCENT)
            e.insert(0, default)
            e.pack(fill="x", padx=24, ipady=5)
            return e

        cfg = load_app_config()
        lbl("Gemini API Anahtarı")
        api_e = ent(cfg.get("gemini_api_key",""))
        lbl("YouTube API Anahtarı")
        yt_e  = ent(cfg.get("youtube_api_key",""))
        lbl("YouTube Kanal Handle")
        hnd_e = ent(cfg.get("youtube_channel_handle",""))

        def save():
            save_app_config({
                "gemini_api_key":         api_e.get().strip(),
                "youtube_api_key":        yt_e.get().strip(),
                "youtube_channel_handle": hnd_e.get().strip(),
            })
            on_close()

        tk.Button(win, text="KAYDET", command=save,
                  bg="#0d1a2e", fg=C_WHITE, font=(self._fm, 10, "bold"),
                  relief="flat", bd=0, cursor="hand2").pack(pady=14, ipadx=28, ipady=5)

    # ── API bekleme ───────────────────────────────────────────────────────────
    def wait_for_api_key(self):
        while not has_gemini_api_key():
            event = threading.Event()
            self.root.after(0, lambda: self._show_api_setup(event))
            event.wait()
            time.sleep(0.2)

    def _show_api_setup(self, done: threading.Event):
        if self.setup_frame:
            try:
                self.setup_frame.destroy()
            except Exception:
                pass
        f = tk.Frame(self.root, bg="#0d1520", bd=0)
        cx, cy2 = self.W//2, self.H//2
        f.place(x=cx-220, y=cy2-100, width=440, height=200)
        self.setup_frame = f

        tk.Label(f, text="API ANAHTARI GEREKLİ", bg="#0d1520", fg=C_ACCENT,
                 font=(self._marvel, 11, "bold")).pack(pady=(16,4))
        tk.Label(f, text="Gemini API anahtarını gir:", bg="#0d1520", fg=C_TEXT,
                 font=(self._fm, 9)).pack()
        e = tk.Entry(f, bg=C_DIM, fg=C_TEXT, font=(self._fm, 10),
                     relief="flat", bd=0, insertbackground=C_ACCENT, show="*")
        e.pack(fill="x", padx=24, pady=8, ipady=6)
        self.api_entry = e

        def save_key():
            key = e.get().strip()
            if key:
                save_app_config({"gemini_api_key": key})
                f.destroy()
                self.setup_frame = None
                done.set()

        tk.Button(f, text="BAŞLAT", command=save_key,
                  bg="#0a1a30", fg=C_WHITE, font=(self._fm, 10, "bold"),
                  relief="flat", bd=0, cursor="hand2").pack(pady=8, ipadx=24, ipady=5)

    # ── Yeniden boyutlandırma ─────────────────────────────────────────────────
    def _on_resize(self, event):
        if event.widget != self.root:
            return
        self.W, self.H = event.width, event.height
        self.cv.config(width=self.W, height=self.H)
        inp_w = min(500, int(self.W * 0.35))
        self._inp.place(x=(self.W - inp_w)//2, y=self.H - 42, width=inp_w)
        bx = (self.W - inp_w)//2 + inp_w + 12
        self._btn_pause.place(x=bx,    y=self.H-42)
        self._btn_mute.place( x=bx+44, y=self.H-42)
        self._btn_set.place(  x=bx+88, y=self.H-42)
        self._build_grid_items()

    def _load_voice(self) -> str:
        return str(load_app_config().get("voice", "Charon") or "Charon")
