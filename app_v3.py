from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from app_v2 import App as BaseApp
from recap_core_v2 import *

APP_V3_NAME = "Video Recap Cutter"

LANGUAGE_DISPLAY = {
    "Tiếng Việt": "Tiếng Việt",
    "Tiếng Anh": "English",
    "Tiếng Nhật": "日本語",
    "Tiếng Hàn": "한국어",
    "Tiếng Trung": "中文",
    "Tiếng Thái": "ไทย",
    "Tiếng Pháp": "Français",
    "Tiếng Đức": "Deutsch",
    "Tiếng Tây Ban Nha": "Español",
    "Tiếng Indonesia": "Indonesia",
    "Tiếng Bồ Đào Nha": "Português",
    "Tiếng Ý": "Italiano",
    "Tiếng Nga": "Русский",
    "Tiếng Ả Rập": "العربية",
    "Tiếng Hindi": "हिन्दी",
}
CORE_TO_DISPLAY = {v: k for k, v in LANGUAGE_DISPLAY.items()}

PREVIEW_TEXT = {
    "Tiếng Việt": "Xin chào, đây là giọng đọc thử của Video Recap Cutter.",
    "English": "Hello, this is a voice preview from Video Recap Cutter.",
    "日本語": "こんにちは。これは音声のテストです。",
    "한국어": "안녕하세요. 이것은 음성 미리 듣기입니다.",
    "中文": "你好，这是语音试听。",
    "ไทย": "สวัสดี นี่คือตัวอย่างเสียงอ่าน",
    "Français": "Bonjour, ceci est un aperçu de la voix.",
    "Deutsch": "Hallo, dies ist eine Vorschau der Stimme.",
    "Español": "Hola, esta es una prueba de la voz.",
    "Indonesia": "Halo, ini adalah pratinjau suara.",
    "Português": "Olá, esta é uma prévia da voz.",
    "Italiano": "Ciao, questa è un'anteprima della voce.",
    "Русский": "Здравствуйте, это предварительное прослушивание голоса.",
    "العربية": "مرحبًا، هذه معاينة للصوت.",
    "हिन्दी": "नमस्ते, यह आवाज़ का नमूना है।",
}

TIKTOK_PREFIXES = {
    "English": ("en_",),
    "日本語": ("jp_",),
    "한국어": ("kr_",),
    "Français": ("fr_",),
    "Deutsch": ("de_",),
    "Español": ("es_",),
    "Indonesia": ("id_",),
    "Português": ("br_",),
}


class AppV3(BaseApp):
    def __init__(self):
        self.web_profile_path = app_dir() / "chrome_web_profile"
        self.voice_profiles_path = app_dir() / "voice_profiles"
        self.web_profile_path.mkdir(parents=True, exist_ok=True)
        self.voice_profiles_path.mkdir(parents=True, exist_ok=True)
        self.voice_choice_map = {}
        super().__init__()
        self.title(APP_V3_NAME)

    # ---------- AI / Web ----------
    def build_ai(self, root):
        sec = ttk.LabelFrame(root, text="2. Tạo SRT bằng AI", style="Section.TLabelframe")
        sec.pack(fill="x", padx=18, pady=6)

        top = ttk.Frame(sec)
        top.pack(fill="x", padx=8, pady=5)
        ttk.Label(top, text="Độ dài câu SRT", width=24).pack(side="left")
        ttk.Combobox(top, textvariable=self.V("density", "Vừa"), state="readonly", values=["Ít chữ", "Vừa", "Nhiều chữ"], width=14).pack(side="left")
        ttk.Label(top, text="Ít chữ = gọn hơn, Nhiều chữ = kể rõ hơn.", foreground="#555").pack(side="left", padx=15)

        api = ttk.LabelFrame(sec, text="Gemini API")
        api.pack(fill="x", padx=8, pady=5)
        ar = ttk.Frame(api)
        ar.pack(fill="x", padx=8, pady=5)
        ttk.Checkbutton(ar, text="Tạo SRT recap bằng Gemini API", variable=self.B("use_api", False), command=self.api_selected).pack(side="left")
        ttk.Label(ar, text="API key/model riêng, không liên quan Web AI.", foreground="#555").pack(side="left", padx=12)
        self.row_entry(api, "Gemini API Key(s)", self.V("api_keys"))
        mr = ttk.Frame(api)
        mr.pack(fill="x", padx=8, pady=3)
        ttk.Label(mr, text="Model", width=24).pack(side="left")
        ttk.Combobox(mr, textvariable=self.V("gemini_model", "gemini-2.5-flash"), values=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"], width=28).pack(side="left")
        ttk.Button(mr, text="Test key", command=self.test_key, width=12).pack(side="left", padx=8)
        ttk.Checkbutton(mr, text="Lưu API", variable=self.B("save_api", False)).pack(side="left", padx=8)
        self.row_entry(api, "SRT API đầu ra", self.V("api_srt"), "Lưu SRT", lambda: self.pick_save("api_srt", ".srt", [("SRT", "*.srt")]))
        self.row_entry(api, "Video gửi API", self.V("api_video"), "Chọn video", lambda: self.pick_video_for("api_video"))
        self.row_entry(api, "Ghi chú thêm API", self.V("api_note"))
        pr = ttk.Frame(api)
        pr.pack(fill="x", padx=8, pady=(3, 7))
        ttk.Checkbutton(pr, text="2 pass API", variable=self.B("api_two_pass", False)).pack(side="left")
        ttk.Label(pr, text="delay").pack(side="left", padx=(20, 5))
        ttk.Entry(pr, textvariable=self.V("api_delay", "5"), width=7).pack(side="left")
        ttk.Label(pr, text="giây").pack(side="left", padx=5)
        ttk.Label(api, text="API miễn phí có thể hết quota/429. Khi video dài hoặc API quá tải, dùng Web AI.", foreground="#b00020").pack(anchor="w", padx=8, pady=(0, 7))

        web = ttk.LabelFrame(sec, text="Web AI / Gemini - ChatGPT")
        web.pack(fill="x", padx=8, pady=5)
        wr = ttk.Frame(web)
        wr.pack(fill="x", padx=8, pady=5)
        ttk.Checkbutton(wr, text="Dùng Web AI tạo SRT khi bấm Cắt video", variable=self.B("use_web", True), command=self.web_selected).pack(side="left")
        ttk.Label(wr, text="chờ web").pack(side="left", padx=(20, 5))
        ttk.Entry(wr, textvariable=self.V("web_wait", "1800"), width=8).pack(side="left")
        ttk.Label(wr, text="giây").pack(side="left", padx=4)
        ttk.Label(wr, text="chunk").pack(side="left", padx=(20, 5))
        ttk.Combobox(wr, textvariable=self.V("chunk_min", "20"), state="readonly", values=["10", "15", "20", "25", "30"], width=6).pack(side="left")
        ttk.Label(wr, text="phút").pack(side="left", padx=4)
        ttk.Button(wr, text="Mở Gemini / ChatGPT", command=self.open_web, width=20).pack(side="right")

        cr = ttk.Frame(web)
        cr.pack(fill="x", padx=8, pady=3)
        ttk.Label(cr, text="Chế độ", width=24).pack(side="left")
        ttk.Combobox(cr, textvariable=self.V("web_mode", "Gemini Web"), state="readonly", values=["Gemini Web", "Gemini Web - 2 pass", "ChatGPT Web - Nhanh", "ChatGPT Web - 2 pass", "ChatGPT Web - 3 pass", "ChatGPT Web - 4 pass"], width=30).pack(side="left")
        ttk.Label(cr, text="Giao diện").pack(side="left", padx=(20, 6))
        ttk.Combobox(cr, textvariable=self.V("ui_mode", "Tự động"), state="readonly", values=["Tự động", "Giao diện mới", "Giao diện cũ"], width=16).pack(side="left")

        self.V("chrome_profile", str(self.web_profile_path)).set(str(self.web_profile_path))
        self.row_entry(web, "Video gửi Web AI", self.V("web_video"), "Chọn video", lambda: self.pick_video_for("web_video"))
        self.row_entry(web, "SRT Web AI đầu ra", self.V("web_srt"), "Lưu SRT", lambda: self.pick_save("web_srt", ".srt", [("SRT", "*.srt")]))
        self.row_entry(web, "Ghi chú gửi trợ lý", self.V("web_note"))

        br = ttk.Frame(web)
        br.pack(fill="x", padx=8, pady=(4, 7))
        ttk.Label(br, text="Chrome riêng của tool: tự nhớ đăng nhập, bạn không cần nhập user-data-dir.", foreground="#555").pack(side="left")
        ttk.Button(br, text="Mở thư mục phiên Chrome", command=self.open_chrome_profile, width=22).pack(side="right")
        ttk.Label(web, text="Lần đầu: bấm Mở Gemini / ChatGPT, đăng nhập xong rồi ĐÓNG cửa sổ Chrome đó trước khi bấm Cắt video / tạo recap.", foreground="#b00020").pack(anchor="w", padx=8, pady=(0, 8))

    def _find_chrome(self):
        if os.name != "nt":
            return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return shutil.which("chrome")

    def open_web(self):
        mode = self.vars["web_mode"].get()
        url = "https://gemini.google.com/" if mode.startswith("Gemini") else "https://chatgpt.com/"
        chrome = self._find_chrome()
        try:
            if chrome:
                subprocess.Popen([chrome, f"--user-data-dir={self.web_profile_path}", "--new-window", url])
                messagebox.showinfo("Chrome của tool", "Chrome riêng đã mở. Đăng nhập xong hãy đóng cửa sổ Chrome này trước khi bấm chạy. Tool sẽ nhớ phiên đăng nhập cho lần sau.")
            else:
                webbrowser.open(url)
                messagebox.showwarning("Không tìm thấy Chrome", "Đã mở bằng trình duyệt mặc định. Muốn Web AI tự động ổn định hơn, hãy cài Google Chrome.")
        except Exception as e:
            messagebox.showerror("Không mở được trợ lý Web", str(e))

    def open_chrome_profile(self):
        self.web_profile_path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.web_profile_path))
        else:
            webbrowser.open(self.web_profile_path.as_uri())

    # ---------- Language + voices ----------
    def build_tts(self, root):
        sec = ttk.LabelFrame(root, text="3. Giọng đọc và TikTok session", style="Section.TLabelframe")
        sec.pack(fill="x", padx=18, pady=6)
        self.row_entry(sec, "File audio WAV", self.V("wav_path"), "Lưu audio", lambda: self.pick_save("wav_path", ".wav", [("WAV", "*.wav")]))

        old_core = self.cfg.get("language", "Tiếng Việt")
        default_display = self.cfg.get("language_display", CORE_TO_DISPLAY.get(old_core, "Tiếng Việt"))
        lr = ttk.Frame(sec)
        lr.pack(fill="x", padx=8, pady=4)
        ttk.Label(lr, text="Ngôn ngữ SRT/giọng", width=24).pack(side="left")
        self.lang_cb = ttk.Combobox(lr, textvariable=self.V("language_display", default_display), state="readonly", values=list(LANGUAGE_DISPLAY.keys()), width=25)
        self.lang_cb.pack(side="left")
        self.lang_cb.bind("<<ComboboxSelected>>", lambda e: self.on_language_changed())
        ttk.Label(lr, text="Chọn tiếng muốn AI viết SRT và giọng đọc sẽ nói.", foreground="#555").pack(side="left", padx=15)

        vr = ttk.Frame(sec)
        vr.pack(fill="x", padx=8, pady=4)
        ttk.Label(vr, text="Giọng đọc", width=24).pack(side="left")
        self.voice_cb = ttk.Combobox(vr, textvariable=self.V("voice_display", ""), state="readonly")
        self.voice_cb.pack(side="left", fill="x", expand=True)
        self.voice_cb.bind("<<ComboboxSelected>>", lambda e: self.on_voice_selected())
        ttk.Button(vr, text="Làm mới giọng", command=self.refresh_voices, width=15).pack(side="left", padx=7)
        ttk.Button(vr, text="Nghe thử giọng", command=self.preview_voice, width=15).pack(side="left")

        self.V("tts_engine", "Piper Offline")
        self.V("voice_sample", "")
        ttk.Checkbutton(sec, text="Tạo giọng đọc và ghép video", variable=self.B("use_tts", True)).pack(anchor="w", padx=32, pady=(1, 5))

        profiles = ttk.LabelFrame(sec, text="Kho giọng mẫu của tôi")
        profiles.pack(fill="x", padx=8, pady=5)
        p1 = ttk.Frame(profiles)
        p1.pack(fill="x", padx=8, pady=5)
        ttk.Label(p1, text="Các WAV/MP3 đã lưu sẽ luôn hiện trong ô Giọng đọc ở trên.", foreground="#555").pack(side="left", fill="x", expand=True)
        ttk.Button(p1, text="Thêm 1 giọng mẫu", command=self.add_voice_sample, width=18).pack(side="left", padx=4)
        ttk.Button(p1, text="Nhập thư mục VietVoice", command=self.import_vietvoice_profiles, width=20).pack(side="left", padx=4)
        p2 = ttk.Frame(profiles)
        p2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(p2, text="Thư mục lưu:").pack(side="left")
        ttk.Label(p2, text=str(self.voice_profiles_path), foreground="#555").pack(side="left", padx=6, fill="x", expand=True)
        ttk.Button(p2, text="Mở kho giọng", command=self.open_voice_profiles, width=16).pack(side="left", padx=4)
        ttk.Button(p2, text="Xóa giọng đang chọn", command=self.remove_selected_profile, width=19).pack(side="left", padx=4)

        orow = ttk.Frame(sec)
        orow.pack(fill="x", padx=8, pady=4)
        ttk.Label(orow, text="Giọng Piper offline", width=24).pack(side="left")
        ttk.Label(orow, text="Muốn thêm model offline: chép .onnx + .onnx.json vào thư mục voices.", foreground="#555").pack(side="left", fill="x", expand=True)
        ttk.Button(orow, text="Mở thư mục voices", command=self.open_voices_folder, width=18).pack(side="right")

        sr = ttk.Frame(sec)
        sr.pack(fill="x", padx=8, pady=4)
        ttk.Label(sr, text="TikTok session ID", width=24).pack(side="left")
        ttk.Entry(sr, textvariable=self.V("sessionid"), show="").pack(side="left", fill="x", expand=True)
        ttk.Button(sr, text="Lưu ID", command=self.save_session_now, width=14).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(sr, text="Tự nhớ ID", variable=self.B("save_session", False)).pack(side="left", padx=8)

        ar = ttk.Frame(sec)
        ar.pack(fill="x", padx=8, pady=(3, 8))
        ttk.Checkbutton(ar, text="Giữ tiếng gốc nhỏ phía dưới", variable=self.B("keep_original_audio", True)).pack(side="left")
        ttk.Label(ar, text="Âm lượng gốc").pack(side="left", padx=(20, 5))
        ttk.Entry(ar, textvariable=self.V("original_volume", "0.12"), width=8).pack(side="left")

        ttk.Label(sec, text="Giọng mẫu WAV/MP3 dùng Voice Clone XTTS. Lần đầu cần chạy INSTALL-VOICE-CLONE.bat một lần.", foreground="#555").pack(anchor="w", padx=8, pady=(0, 8))
        self._sync_language()
        self.refresh_voices()

    def _sync_language(self):
        display = self.vars.get("language_display", tk.StringVar(value="Tiếng Việt")).get()
        core = LANGUAGE_DISPLAY.get(display, "Tiếng Việt")
        self.V("language", core).set(core)
        return core

    def on_language_changed(self):
        self._sync_language()
        self.refresh_voices()
        self.save_cfg()

    def _safe_profile_name(self, name: str):
        name = re.sub(r"[^0-9A-Za-zÀ-ỹ _.-]+", "_", name.strip())
        name = re.sub(r"\s+", " ", name).strip(" ._")
        return name or "giong-moi"

    def list_voice_profiles(self):
        self.voice_profiles_path.mkdir(parents=True, exist_ok=True)
        found = []
        exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
        for d in sorted([x for x in self.voice_profiles_path.iterdir() if x.is_dir()], key=lambda x: x.name.lower()):
            refs = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts and (p.stem.lower() == "reference" or p.name.lower().startswith("reference."))]
            if not refs:
                refs = [p for p in d.iterdir() if p.is_file() and p.suffix.lower() in exts]
            if refs:
                found.append((d.name, refs[0]))
        for p in sorted(self.voice_profiles_path.iterdir(), key=lambda x: x.name.lower()):
            if p.is_file() and p.suffix.lower() in exts:
                found.append((p.stem, p))
        return found

    def refresh_voices(self):
        core_lang = self._sync_language()
        locale = LANGUAGES.get(core_lang, "vi-VN")
        self.voice_choice_map = {}
        values = []

        # 1) Giọng mẫu của người dùng: ưu tiên hiển thị đầu tiên và nhớ vĩnh viễn trong voice_profiles.
        for name, path in self.list_voice_profiles():
            disp = f"Giọng của tôi - {name} (Voice Clone)"
            self.voice_choice_map[disp] = ("Voice Clone XTTS", "XTTS", str(path))
            values.append(disp)

        # 2) Piper offline.
        for name, path in list_piper_models():
            disp = f"Offline - {name}"
            self.voice_choice_map[disp] = ("Piper Offline", path, "")
            values.append(disp)

        # 3) Edge TTS lọc theo ngôn ngữ đang chọn.
        prefix = locale.split("-")[0].lower() + "-"
        for code, desc in EDGE_VOICES.items():
            if code.lower().startswith(prefix):
                disp = f"Online - {desc}"
                self.voice_choice_map[disp] = ("Edge TTS", code, "")
                values.append(disp)

        # 4) TikTok/CapCut nếu có voice code phù hợp ngôn ngữ.
        prefixes = TIKTOK_PREFIXES.get(core_lang, ())
        for code, desc in TIKTOK_VOICES.items():
            if prefixes and code.startswith(prefixes):
                disp = f"TikTok/CapCut - {desc}"
                self.voice_choice_map[disp] = ("TikTok / CapCut", code, "")
                values.append(disp)

        if not values:
            values = ["Chưa có giọng - hãy thêm giọng mẫu"]
            self.voice_choice_map[values[0]] = ("Voice Clone XTTS", "XTTS", "")
        self.voice_cb["values"] = values
        cur = self.vars["voice_display"].get()
        if cur not in values:
            # Nếu đã có giọng mẫu, ưu tiên giọng mẫu đầu tiên; nếu không thì lựa chọn đầu tiên.
            self.vars["voice_display"].set(values[0])
        self.on_voice_selected()

    def on_voice_selected(self):
        disp = self.vars.get("voice_display", tk.StringVar(value="")).get()
        engine, value, sample = self.voice_choice_map.get(disp, ("Piper Offline", disp, ""))
        self.V("tts_engine", engine).set(engine)
        if sample:
            self.V("voice_sample", sample).set(sample)
        elif engine != "Voice Clone XTTS":
            self.V("voice_sample", "").set("")
        self.save_cfg()

    def voice_value(self):
        disp = self.vars["voice_display"].get()
        engine, value, sample = self.voice_choice_map.get(disp, (self.vars.get("tts_engine", tk.StringVar(value="Piper Offline")).get(), disp, ""))
        return value

    def add_voice_sample(self):
        p = filedialog.askopenfilename(filetypes=[("Audio giọng mẫu", "*.wav *.mp3 *.m4a *.flac *.ogg"), ("Tất cả", "*.*")])
        if not p:
            return
        default = Path(p).stem
        name = simpledialog.askstring("Tên giọng", "Đặt tên để giọng này luôn hiện trong tool:", initialvalue=default, parent=self)
        if not name:
            return
        name = self._safe_profile_name(name)
        dest_dir = self.voice_profiles_path / name
        if dest_dir.exists() and any(dest_dir.iterdir()):
            if not messagebox.askyesno("Đã có giọng", f"Giọng '{name}' đã tồn tại. Ghi đè audio mẫu?"):
                return
            shutil.rmtree(dest_dir, ignore_errors=True)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / ("reference" + Path(p).suffix.lower())
        shutil.copy2(p, dest)
        (dest_dir / "profile.json").write_text(json.dumps({"name": name, "reference": dest.name}, ensure_ascii=False, indent=2), encoding="utf-8")
        self.refresh_voices()
        target = f"Giọng của tôi - {name} (Voice Clone)"
        if target in self.voice_choice_map:
            self.vars["voice_display"].set(target)
            self.on_voice_selected()
        messagebox.showinfo("Đã thêm giọng", f"Đã lưu '{name}' vào kho giọng. Lần sau mở tool giọng vẫn còn trong danh sách.")

    def import_vietvoice_profiles(self):
        root = filedialog.askdirectory(title="Chọn thư mục voice-profiles của VietVoice")
        if not root:
            return
        rootp = Path(root)
        candidates = []
        exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
        for p in rootp.rglob("*"):
            if p.is_file() and p.suffix.lower() in exts and p.stem.lower() == "reference":
                candidates.append(p)
        if not candidates:
            messagebox.showwarning("Không thấy giọng", "Không tìm thấy file reference.wav/mp3/m4a/flac/ogg trong thư mục đã chọn.")
            return
        imported = 0
        skipped = 0
        for p in candidates:
            name = self._safe_profile_name(p.parent.name)
            dest_dir = self.voice_profiles_path / name
            if dest_dir.exists() and any(dest_dir.iterdir()):
                skipped += 1
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / ("reference" + p.suffix.lower())
            shutil.copy2(p, dest)
            (dest_dir / "profile.json").write_text(json.dumps({"name": name, "reference": dest.name, "imported_from": str(p)}, ensure_ascii=False, indent=2), encoding="utf-8")
            imported += 1
        self.refresh_voices()
        messagebox.showinfo("Nhập VietVoice", f"Đã nhập {imported} giọng. Bỏ qua {skipped} giọng đã tồn tại. Các giọng đã nhập sẽ được nhớ vĩnh viễn trong tool.")

    def open_voice_profiles(self):
        self.voice_profiles_path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.voice_profiles_path))
        else:
            webbrowser.open(self.voice_profiles_path.as_uri())

    def remove_selected_profile(self):
        disp = self.vars.get("voice_display", tk.StringVar(value="")).get()
        info = self.voice_choice_map.get(disp)
        if not info or info[0] != "Voice Clone XTTS" or not info[2]:
            messagebox.showinfo("Không phải giọng mẫu", "Giọng đang chọn không nằm trong Kho giọng mẫu của tôi.")
            return
        sample = Path(info[2])
        d = sample.parent
        if messagebox.askyesno("Xóa giọng", f"Xóa giọng mẫu '{d.name}' khỏi tool?"):
            shutil.rmtree(d, ignore_errors=True)
            self.refresh_voices()

    def preview_voice(self):
        self.on_voice_selected()
        engine = self.vars["tts_engine"].get()
        voice = self.voice_value()
        core_lang = self._sync_language()
        sample = self.vars["voice_sample"].get().strip()
        session = self.vars["sessionid"].get().strip()
        text = PREVIEW_TEXT.get(core_lang, PREVIEW_TEXT["Tiếng Việt"])

        def work():
            try:
                tmp = Path(tempfile.mkdtemp(prefix="recap_preview_"))
                srt = tmp / "preview.srt"
                wav = tmp / "preview.wav"
                srt.write_text(f"1\n00:00:00,000 --> 00:00:05,000\n{text}\n", encoding="utf-8")
                if engine == "Edge TTS":
                    srt_to_wav_edge(str(srt), str(wav), voice, lambda x: None)
                elif engine == "Piper Offline":
                    srt_to_wav_piper(str(srt), str(wav), voice, lambda x: None)
                elif engine == "TikTok / CapCut":
                    srt_to_wav_tiktok(str(srt), str(wav), voice, session, lambda x: None)
                else:
                    if not sample or not Path(sample).exists():
                        raise FileNotFoundError("Chưa có audio mẫu cho giọng đã chọn.")
                    srt_to_wav_xtts(str(srt), str(wav), sample, core_lang, lambda x: None)
                if os.name == "nt":
                    os.startfile(str(wav))
                else:
                    webbrowser.open(wav.as_uri())
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Nghe thử lỗi", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def show_help(self):
        text = """VIDEO RECAP CUTTER V3 - HƯỚNG DẪN NHANH

1. Ngôn ngữ SRT/giọng
Chọn đúng tiếng muốn AI viết nội dung và giọng đọc sẽ nói: Tiếng Việt, Tiếng Anh, Tiếng Nhật, Tiếng Hàn, Tiếng Trung... tổng 15 ngôn ngữ.

2. Giọng đọc
Không cần chọn 'hệ giọng'. Chỉ chọn trực tiếp tên giọng trong ô Giọng đọc.
- Giọng của tôi - ...: audio mẫu đã lưu, dùng Voice Clone XTTS.
- Offline - ...: model Piper trong thư mục voices.
- Online - ...: Edge TTS theo ngôn ngữ đang chọn.
- TikTok/CapCut - ...: voice code TikTok nếu ngôn ngữ đó có hỗ trợ.

3. Thêm giọng VietVoice
Bấm 'Nhập thư mục VietVoice' rồi chọn thư mục data\\voice-profiles của VietVoice. Tool tìm các file reference.mp3/wav và copy vào thư mục voice_profiles. Sau đó các giọng luôn được nhớ và hiện trong danh sách Giọng đọc.

4. Chrome / Gemini / ChatGPT
Không cần nhập Chrome user-data-dir. Tool tự dùng thư mục chrome_web_profile để nhớ đăng nhập.
Lần đầu bấm 'Mở Gemini / ChatGPT', đăng nhập, sau đó đóng cửa sổ Chrome đó rồi mới bấm chạy.

5. Voice Clone
Nếu dùng 'Giọng của tôi', lần đầu chạy INSTALL-VOICE-CLONE.bat một lần để cài XTTS.
"""
        w = tk.Toplevel(self)
        w.title("Hướng dẫn Video Recap Cutter V3")
        w.geometry("780x650")
        t = tk.Text(w, wrap="word", font=("Segoe UI", 10))
        t.pack(fill="both", expand=True, padx=10, pady=10)
        t.insert("1.0", text)
        t.configure(state="disabled")


if __name__ == "__main__":
    AppV3().mainloop()
