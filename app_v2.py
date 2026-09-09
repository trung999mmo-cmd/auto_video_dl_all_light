from __future__ import annotations

import asyncio
import json
import os
import queue
import shutil
import tempfile
import threading
import traceback
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from recap_core_v2 import *

APP_NAME = "Video Recap Cutter"
CFG = Path.home() / ".video_recap_cutter_v2.json"

HELP_TEXT = """1. Chọn video và nơi lưu
- Bấm Chọn video ở mục Video và đầu ra.
- Tool tự điền video đầu ra, map JSON, SRT Gem Web/API và audio WAV.
- Nếu muốn lưu chỗ khác, bấm Chọn nơi lưu.

2. Chọn nhịp cắt
- Khuyến nghị Giữ 2 giây, Bỏ 8 giây hoặc Giữ 2 giây, Bỏ 10 giây.

3. Tạo SRT
- Có thể chọn Gemini API hoặc Web AI. Hai cách tách nhau, chỉ bật một cách khi chạy.
- Web AI hỗ trợ Gemini Web / ChatGPT Web, chia chunk 10-30 phút.

4. Giọng đọc
- Edge TTS: nhiều ngôn ngữ, cần Internet.
- Piper Offline: trong thư mục voices có sẵn một giọng Việt; muốn thêm giọng Piper, chép cặp .onnx + .onnx.json vào thư mục voices rồi bấm Làm mới giọng.
- TikTok/CapCut: nhập session ID, dịch vụ có thể thay đổi theo TikTok.
- Voice Clone XTTS: chọn audio giọng mẫu WAV/MP3. Lần đầu chạy INSTALL-VOICE-CLONE.bat để cài engine riêng.

5. Chạy
- Kiểm tra video, nhịp cắt, SRT, ngôn ngữ và giọng.
- Bấm Cắt video / tạo recap. Xem Log để biết đang ở bước nào.
"""


class ScrollFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, background="#f4f6f8")
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _wheel(self, event):
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1120x940")
        self.minsize(980, 720)
        self.configure(bg="#f4f6f8")
        self.q = queue.Queue()
        self.cfg = self.load_cfg()
        self.vars = {}
        self.piper_map = {}
        self.voice_map = {}
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("vista")
        except Exception:
            pass
        self.style.configure("Section.TLabelframe", padding=8)
        self.style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"))
        self.build()
        self.after(100, self.flush_log)

    def load_cfg(self):
        try:
            return json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_cfg(self):
        d = {}
        for k, v in self.vars.items():
            if k in {"api_keys", "sessionid"}:
                continue
            try:
                d[k] = v.get()
            except Exception:
                pass
        if self.vars["save_api"].get():
            d["api_keys"] = self.vars["api_keys"].get()
        if self.vars["save_session"].get():
            d["sessionid"] = self.vars["sessionid"].get()
        try:
            CFG.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def V(self, name, default=""):
        if name in self.vars:
            return self.vars[name]
        v = tk.StringVar(value=self.cfg.get(name, default))
        self.vars[name] = v
        return v

    def B(self, name, default=False):
        if name in self.vars:
            return self.vars[name]
        v = tk.BooleanVar(value=bool(self.cfg.get(name, default)))
        self.vars[name] = v
        return v

    def row_entry(self, parent, label, var, button_text=None, command=None, label_width=24):
        r = ttk.Frame(parent)
        r.pack(fill="x", padx=8, pady=3)
        ttk.Label(r, text=label, width=label_width).pack(side="left")
        ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)
        if button_text and command:
            ttk.Button(r, text=button_text, command=command, width=16).pack(side="left", padx=(8, 0))
        return r

    def build(self):
        self.scroll = ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)
        root = self.scroll.inner

        header = tk.Frame(root, bg="#147d72", height=98)
        header.pack(fill="x", padx=18, pady=(16, 10))
        header.pack_propagate(False)
        tk.Label(header, text="Video Recap Cutter", bg="#147d72", fg="white", font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=20, pady=(18, 4))
        tk.Label(header, text="Chọn video, đặt nhịp cắt, tạo SRT bằng AI, chọn giọng đọc rồi bấm chạy.", bg="#147d72", fg="white", font=("Segoe UI", 10)).pack(anchor="center")

        guide = ttk.LabelFrame(root, text="Hướng dẫn", style="Section.TLabelframe")
        guide.pack(fill="x", padx=18, pady=5)
        gr = ttk.Frame(guide)
        gr.pack(fill="x")
        ttk.Label(gr, text="Khuyến nghị nhanh: Giữ 2 giây, Bỏ 8 giây hoặc Giữ 2 giây, Bỏ 10 giây. Dùng Web AI khi cần SRT bám nội dung video.", wraplength=820).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(gr, text="Mở hướng dẫn chi tiết", command=self.show_help, width=22).pack(side="right", padx=8)

        self.build_video(root)
        self.build_ai(root)
        self.build_tts(root)
        self.build_run(root)
        self.build_log(root)

    def build_video(self, root):
        sec = ttk.LabelFrame(root, text="1. Video và đầu ra", style="Section.TLabelframe")
        sec.pack(fill="x", padx=18, pady=6)
        self.row_entry(sec, "Video gốc", self.V("input_video"), "Chọn video", self.pick_video)
        self.row_entry(sec, "Nơi lưu video", self.V("output_video"), "Chọn nơi lưu", lambda: self.pick_save("output_video", ".mp4", [("MP4", "*.mp4")]))
        self.row_entry(sec, "Map JSON", self.V("map_json"), "Lưu map", lambda: self.pick_save("map_json", ".json", [("JSON", "*.json")]))

        r = ttk.Frame(sec)
        r.pack(fill="x", padx=8, pady=4)
        ttk.Label(r, text="Nhịp cắt", width=24).pack(side="left")
        ttk.Label(r, text="Giữ").pack(side="left")
        ttk.Entry(r, textvariable=self.V("keep_sec", "2"), width=7).pack(side="left", padx=5)
        ttk.Label(r, text="giây, bỏ").pack(side="left")
        ttk.Entry(r, textvariable=self.V("drop_sec", "8"), width=7).pack(side="left", padx=5)
        ttk.Label(r, text="giây").pack(side="left")
        pre = ttk.Combobox(r, state="readonly", values=["Giữ 2 / Bỏ 8", "Giữ 2 / Bỏ 10", "Giữ 5 / Bỏ 10"], width=18)
        pre.set("Giữ 2 / Bỏ 8")
        pre.pack(side="left", padx=20)
        pre.bind("<<ComboboxSelected>>", lambda e: self.set_preset(pre.get()))

        rr = ttk.Frame(sec)
        rr.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Checkbutton(rr, text="Tạo thêm SRT template từ nhịp cắt", variable=self.B("make_template", False)).pack(side="left")
        ttk.Entry(rr, textvariable=self.V("template_srt")).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(rr, text="Lưu SRT", command=lambda: self.pick_save("template_srt", ".srt", [("SRT", "*.srt")]), width=16).pack(side="left")

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
        ttk.Label(api, text="Lưu ý: API miễn phí có thể hết quota/429. Khi video dài hoặc API quá tải, dùng Web AI.", foreground="#b00020").pack(anchor="w", padx=8, pady=(0, 7))

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
        ttk.Button(wr, text="Mở trợ lý Web", command=self.open_web, width=18).pack(side="right")

        cr = ttk.Frame(web)
        cr.pack(fill="x", padx=8, pady=3)
        ttk.Label(cr, text="Chế độ", width=24).pack(side="left")
        ttk.Combobox(cr, textvariable=self.V("web_mode", "Gemini Web"), state="readonly", values=["Gemini Web", "Gemini Web - 2 pass", "ChatGPT Web - Nhanh", "ChatGPT Web - 2 pass", "ChatGPT Web - 3 pass", "ChatGPT Web - 4 pass"], width=30).pack(side="left")
        ttk.Label(cr, text="Giao diện").pack(side="left", padx=(20, 6))
        ttk.Combobox(cr, textvariable=self.V("ui_mode", "Tự động"), state="readonly", values=["Tự động", "Giao diện mới", "Giao diện cũ"], width=16).pack(side="left")
        self.row_entry(web, "Chrome user-data-dir", self.V("chrome_profile"), "Chọn thư mục", self.pick_profile)
        self.row_entry(web, "Video gửi Web AI", self.V("web_video"), "Chọn video", lambda: self.pick_video_for("web_video"))
        self.row_entry(web, "SRT Web AI đầu ra", self.V("web_srt"), "Lưu SRT", lambda: self.pick_save("web_srt", ".srt", [("SRT", "*.srt")]))
        self.row_entry(web, "Ghi chú gửi trợ lý", self.V("web_note"))
        ttk.Label(web, text="Gemini Web/ChatGPT Web mở Chrome thật. Lần đầu hãy đăng nhập tài khoản trong cửa sổ Chrome mà tool mở.", foreground="#555").pack(anchor="w", padx=8, pady=(0, 7))

    def build_tts(self, root):
        sec = ttk.LabelFrame(root, text="3. Giọng đọc và TikTok session", style="Section.TLabelframe")
        sec.pack(fill="x", padx=18, pady=6)
        self.row_entry(sec, "File audio WAV", self.V("wav_path"), "Lưu audio", lambda: self.pick_save("wav_path", ".wav", [("WAV", "*.wav")]))

        lr = ttk.Frame(sec)
        lr.pack(fill="x", padx=8, pady=4)
        ttk.Label(lr, text="Ngôn ngữ SRT/giọng", width=24).pack(side="left")
        lang = ttk.Combobox(lr, textvariable=self.V("language", "Tiếng Việt"), state="readonly", values=list(LANGUAGES.keys()), width=25)
        lang.pack(side="left")
        lang.bind("<<ComboboxSelected>>", lambda e: self.refresh_voices())
        ttk.Label(lr, text="15 ngôn ngữ; dùng để lọc giọng và yêu cầu AI viết SRT.", foreground="#555").pack(side="left", padx=15)

        er = ttk.Frame(sec)
        er.pack(fill="x", padx=8, pady=4)
        ttk.Label(er, text="Hệ giọng", width=24).pack(side="left")
        eng = ttk.Combobox(er, textvariable=self.V("tts_engine", "Piper Offline"), state="readonly", values=["Piper Offline", "Edge TTS", "TikTok / CapCut", "Voice Clone XTTS"], width=25)
        eng.pack(side="left")
        eng.bind("<<ComboboxSelected>>", lambda e: self.refresh_voices())
        ttk.Checkbutton(er, text="Tạo giọng đọc và ghép video", variable=self.B("use_tts", True)).pack(side="left", padx=16)

        vr = ttk.Frame(sec)
        vr.pack(fill="x", padx=8, pady=4)
        ttk.Label(vr, text="Giọng đọc", width=24).pack(side="left")
        self.voice_cb = ttk.Combobox(vr, textvariable=self.V("voice_display", ""), state="readonly")
        self.voice_cb.pack(side="left", fill="x", expand=True)
        ttk.Button(vr, text="Làm mới giọng", command=self.refresh_voices, width=15).pack(side="left", padx=7)
        ttk.Button(vr, text="Nghe thử giọng", command=self.preview_voice, width=15).pack(side="left")

        self.row_entry(sec, "Audio giọng mẫu", self.V("voice_sample"), "Chọn audio", self.pick_voice_sample)

        orow = ttk.Frame(sec)
        orow.pack(fill="x", padx=8, pady=4)
        ttk.Label(orow, text="Giọng offline", width=24).pack(side="left")
        ttk.Label(orow, text="Thêm cặp .onnx + .onnx.json vào thư mục voices rồi bấm Làm mới giọng.", foreground="#555").pack(side="left", fill="x", expand=True)
        ttk.Button(orow, text="Mở thư mục voices", command=self.open_voices_folder, width=18).pack(side="right")

        sr = ttk.Frame(sec)
        sr.pack(fill="x", padx=8, pady=4)
        ttk.Label(sr, text="TikTok session ID", width=24).pack(side="left")
        ttk.Entry(sr, textvariable=self.V("sessionid"), show="").pack(side="left", fill="x", expand=True)
        ttk.Button(sr, text="Lưu ID", command=self.save_session_now, width=14).pack(side="left", padx=(8, 0))
        ttk.Checkbutton(sr, text="Tự nhớ ID", variable=self.B("save_session", False)).pack(side="left", padx=8)
        ttk.Label(sec, text="Không gửi session ID cho người khác. Voice Clone XTTS dùng audio mẫu của bạn trên máy và cần bộ cài riêng lần đầu.", foreground="#555").pack(anchor="w", padx=8, pady=(0, 8))

        ar = ttk.Frame(sec)
        ar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Checkbutton(ar, text="Giữ tiếng gốc nhỏ phía dưới", variable=self.B("keep_original_audio", True)).pack(side="left")
        ttk.Label(ar, text="Âm lượng gốc").pack(side="left", padx=(20, 5))
        ttk.Entry(ar, textvariable=self.V("original_volume", "0.12"), width=8).pack(side="left")
        self.refresh_voices()

    def build_run(self, root):
        sec = ttk.LabelFrame(root, text="4. Chạy tool", style="Section.TLabelframe")
        sec.pack(fill="x", padx=18, pady=6)
        r = ttk.Frame(sec)
        r.pack(fill="x", padx=8, pady=8)
        self.run_btn = tk.Button(r, text="Cắt video / tạo recap", bg="#087f72", fg="white", activebackground="#0a6b61", activeforeground="white", font=("Segoe UI", 11, "bold"), command=self.run_pipeline, padx=18, pady=8)
        self.run_btn.pack(side="left")
        self.status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(r, textvariable=self.status).pack(side="left", padx=15)

    def build_log(self, root):
        sec = ttk.LabelFrame(root, text="Log", style="Section.TLabelframe")
        sec.pack(fill="both", expand=True, padx=18, pady=(6, 18))
        self.logbox = tk.Text(sec, height=16, wrap="word", font=("Consolas", 9))
        self.logbox.pack(fill="both", expand=True, padx=8, pady=8)

    def show_help(self):
        w = tk.Toplevel(self)
        w.title("Hướng dẫn Video Recap Cutter")
        w.geometry("760x650")
        t = tk.Text(w, wrap="word", font=("Segoe UI", 10))
        t.pack(fill="both", expand=True, padx=10, pady=10)
        t.insert("1.0", HELP_TEXT)
        t.configure(state="disabled")

    def set_preset(self, text):
        import re
        m = re.search(r"Giữ (\d+) / Bỏ (\d+)", text)
        if m:
            self.vars["keep_sec"].set(m.group(1))
            self.vars["drop_sec"].set(m.group(2))

    def pick_video(self):
        p = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v"), ("Tất cả", "*.*")])
        if not p:
            return
        self.vars["input_video"].set(p)
        base = str(Path(p).with_suffix(""))
        self.vars["output_video"].set(base + "_recap.mp4")
        self.vars["map_json"].set(base + "_segments.json")
        self.vars["template_srt"].set(base + "_template.srt")
        self.vars["api_srt"].set(base + "_gemini_api.srt")
        self.vars["web_srt"].set(base + "_gem_web.srt")
        self.vars["wav_path"].set(base + "_tts.wav")
        self.vars["api_video"].set(p)
        self.vars["web_video"].set(p)

    def pick_video_for(self, key):
        p = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v"), ("Tất cả", "*.*")])
        if p:
            self.vars[key].set(p)

    def pick_voice_sample(self):
        p = filedialog.askopenfilename(filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac *.ogg"), ("Tất cả", "*.*")])
        if p:
            self.vars["voice_sample"].set(p)

    def pick_profile(self):
        p = filedialog.askdirectory()
        if p:
            self.vars["chrome_profile"].set(p)

    def pick_save(self, key, ext, types):
        p = filedialog.asksaveasfilename(defaultextension=ext, filetypes=types + [("Tất cả", "*.*")])
        if p:
            self.vars[key].set(p)

    def api_selected(self):
        if self.vars["use_api"].get():
            self.vars["use_web"].set(False)

    def web_selected(self):
        if self.vars["use_web"].get():
            self.vars["use_api"].set(False)

    def open_web(self):
        mode = self.vars["web_mode"].get()
        webbrowser.open("https://gemini.google.com/" if mode.startswith("Gemini") else "https://chatgpt.com/")

    def open_voices_folder(self):
        p = voices_dir()
        if os.name == "nt":
            os.startfile(str(p))
        else:
            webbrowser.open(p.as_uri())

    def save_session_now(self):
        self.vars["save_session"].set(True)
        self.save_cfg()
        messagebox.showinfo("Đã lưu", "Đã lưu TikTok session ID trên máy này.")

    def test_key(self):
        keys = [x.strip() for x in self.vars["api_keys"].get().replace("\n", ";").replace(",", ";").split(";") if x.strip()]
        if not keys:
            messagebox.showwarning("Thiếu key", "Chưa nhập API key.")
            return
        def work():
            ok, msg = test_gemini_key(keys[0], self.vars["gemini_model"].get())
            self.after(0, lambda: messagebox.showinfo("Test key" if ok else "Key lỗi", msg))
        threading.Thread(target=work, daemon=True).start()

    def refresh_voices(self):
        engine = self.vars.get("tts_engine", tk.StringVar(value="Piper Offline")).get()
        lang_name = self.vars.get("language", tk.StringVar(value="Tiếng Việt")).get()
        locale = LANGUAGES.get(lang_name, "vi-VN")
        self.voice_map = {}
        values = []
        if engine == "Edge TTS":
            prefix = locale.split("-")[0]
            for code, desc in EDGE_VOICES.items():
                if code.lower().startswith(prefix.lower() + "-"):
                    disp = f"{desc} ({code})"
                    self.voice_map[disp] = code
                    values.append(disp)
            if not values:
                for code, desc in EDGE_VOICES.items():
                    disp = f"{desc} ({code})"
                    self.voice_map[disp] = code
                    values.append(disp)
        elif engine == "Piper Offline":
            self.piper_map = {name: path for name, path in list_piper_models()}
            for name, path in self.piper_map.items():
                disp = f"{name} - Offline"
                self.voice_map[disp] = path
                values.append(disp)
            if not values:
                values = ["Chưa có model - mở thư mục voices"]
        elif engine == "TikTok / CapCut":
            for code, desc in TIKTOK_VOICES.items():
                disp = f"{desc} ({code})"
                self.voice_map[disp] = code
                values.append(disp)
        else:
            values = ["Dùng audio giọng mẫu bên dưới"]
            self.voice_map[values[0]] = "XTTS"
        self.voice_cb["values"] = values
        current = self.vars["voice_display"].get()
        if current not in values and values:
            self.vars["voice_display"].set(values[0])

    def voice_value(self):
        return self.voice_map.get(self.vars["voice_display"].get(), self.vars["voice_display"].get())

    def preview_voice(self):
        engine = self.vars["tts_engine"].get()
        voice = self.voice_value()
        lang = self.vars["language"].get()
        sample = self.vars["voice_sample"].get().strip()
        session = self.vars["sessionid"].get().strip()
        def work():
            try:
                tmp = Path(tempfile.mkdtemp(prefix="recap_preview_"))
                srt = tmp / "preview.srt"
                wav = tmp / "preview.wav"
                srt.write_text("1\n00:00:00,000 --> 00:00:04,000\nXin chào, đây là giọng đọc thử của Video Recap Cutter.\n", encoding="utf-8")
                if engine == "Edge TTS":
                    srt_to_wav_edge(str(srt), str(wav), voice, lambda x: None)
                elif engine == "Piper Offline":
                    srt_to_wav_piper(str(srt), str(wav), voice, lambda x: None)
                elif engine == "TikTok / CapCut":
                    srt_to_wav_tiktok(str(srt), str(wav), voice, session, lambda x: None)
                else:
                    srt_to_wav_xtts(str(srt), str(wav), sample, lang, lambda x: None)
                if os.name == "nt":
                    os.startfile(str(wav))
                else:
                    webbrowser.open(wav.as_uri())
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Nghe thử lỗi", str(e)))
        threading.Thread(target=work, daemon=True).start()

    def log(self, s):
        self.q.put(str(s))

    def flush_log(self):
        try:
            while True:
                s = self.q.get_nowait()
                self.logbox.insert("end", s + "\n")
                self.logbox.see("end")
        except queue.Empty:
            pass
        self.after(100, self.flush_log)

    def set_status(self, s):
        self.after(0, lambda: self.status.set(s))

    def run_pipeline(self):
        self.save_cfg()
        self.logbox.delete("1.0", "end")
        threading.Thread(target=self.pipeline, daemon=True).start()

    def _ai_mode(self):
        if self.vars["use_api"].get():
            return "api"
        if self.vars["use_web"].get():
            return "web"
        return "none"

    def pipeline(self):
        temp_cut = None
        try:
            inp = self.vars["input_video"].get().strip()
            out = self.vars["output_video"].get().strip()
            if not inp or not Path(inp).exists():
                raise FileNotFoundError("Chưa chọn video gốc")
            if not out:
                raise ValueError("Chưa chọn nơi lưu video")
            keep = float(self.vars["keep_sec"].get())
            drop = float(self.vars["drop_sec"].get())
            total = duration(inp)
            segs = build_segments(total, keep, drop)
            self.log(f"Video gốc: {total:.1f}s | Giữ {keep}s / Bỏ {drop}s | {len(segs)} đoạn")

            if self.vars["map_json"].get().strip():
                save_map(segs, self.vars["map_json"].get().strip())
                self.log("Đã tạo map JSON")
            if self.vars["make_template"].get() and self.vars["template_srt"].get().strip():
                template_srt(segs, self.vars["template_srt"].get().strip())
                self.log("Đã tạo SRT template")

            temp_cut = str(Path(out).with_name(Path(out).stem + "__cut_temp.mp4"))
            self.set_status("Đang cắt video...")
            cut_video(inp, temp_cut, segs, self.log)
            recap_dur = duration(temp_cut)
            self.log(f"Đã cắt video recap tạm: {recap_dur:.1f}s")

            ai = self._ai_mode()
            srt_path = ""
            if ai == "api":
                srt_path = self.vars["api_srt"].get().strip()
                if not srt_path:
                    raise ValueError("Chưa chọn SRT API đầu ra")
                keys = [x.strip() for x in self.vars["api_keys"].get().replace("\n", ";").replace(",", ";").split(";") if x.strip()]
                if not keys:
                    raise ValueError("Chưa nhập Gemini API key")
                source = self.vars["api_video"].get().strip()
                # Để timeline SRT khớp video cuối, mặc định xử lý video đã cắt nếu người dùng vẫn để video gốc.
                if not source or Path(source).resolve() == Path(inp).resolve():
                    source = temp_cut
                last = None
                srt_text = ""
                for idx, key in enumerate(keys, 1):
                    try:
                        self.set_status(f"Gemini API key {idx}/{len(keys)}...")
                        srt_text = gemini_api_srt(source, key, self.vars["gemini_model"].get().strip(), self.vars["language"].get(), self.vars["api_note"].get(), self.vars["density"].get(), self.log, self.vars["api_two_pass"].get(), int(float(self.vars["api_delay"].get() or 0)))
                        break
                    except Exception as e:
                        last = e
                        self.log("API key lỗi, thử key tiếp theo: " + str(e))
                if not srt_text:
                    raise last or RuntimeError("Không tạo được SRT bằng API")
                srt_text = normalize_srt(srt_text, recap_dur)
                Path(srt_path).write_text(srt_text, encoding="utf-8")
                self.log("Đã lưu SRT API: " + srt_path)

            elif ai == "web":
                srt_path = self.vars["web_srt"].get().strip()
                if not srt_path:
                    raise ValueError("Chưa chọn SRT Web AI đầu ra")
                mode = self.vars["web_mode"].get()
                provider = "Gemini" if mode.startswith("Gemini") else "ChatGPT"
                passes = 1
                if "2 pass" in mode:
                    passes = 2
                elif "3 pass" in mode:
                    passes = 3
                elif "4 pass" in mode:
                    passes = 4
                source = self.vars["web_video"].get().strip()
                if not source or Path(source).resolve() == Path(inp).resolve():
                    source = temp_cut
                self.set_status("Đang chạy Web AI...")
                srt_text = web_ai_srt_chunked(source, provider, self.vars["language"].get(), self.vars["web_note"].get(), self.vars["density"].get(), int(float(self.vars["web_wait"].get() or 1800)), self.vars["chrome_profile"].get().strip() or None, int(self.vars["chunk_min"].get()), self.log, passes, self.vars["ui_mode"].get())
                srt_text = normalize_srt(srt_text, recap_dur)
                Path(srt_path).write_text(srt_text, encoding="utf-8")
                self.log("Đã lưu SRT Web AI: " + srt_path)

            if self.vars["use_tts"].get():
                if not srt_path or not Path(srt_path).exists():
                    raise ValueError("Đã bật tạo giọng nhưng chưa có SRT. Hãy bật Gemini API/Web AI hoặc chọn cách tạo SRT trước.")
                wav = self.vars["wav_path"].get().strip()
                if not wav:
                    raise ValueError("Chưa chọn file audio WAV")
                engine = self.vars["tts_engine"].get()
                voice = self.voice_value()
                self.set_status("Đang tạo giọng đọc...")
                if engine == "Edge TTS":
                    srt_to_wav_edge(srt_path, wav, voice, self.log)
                elif engine == "Piper Offline":
                    srt_to_wav_piper(srt_path, wav, voice, self.log)
                elif engine == "TikTok / CapCut":
                    srt_to_wav_tiktok(srt_path, wav, voice, self.vars["sessionid"].get().strip(), self.log)
                else:
                    srt_to_wav_xtts(srt_path, wav, self.vars["voice_sample"].get().strip(), self.vars["language"].get(), self.log)
                self.set_status("Đang ghép audio vào video...")
                mix_video_audio(temp_cut, wav, out, self.vars["keep_original_audio"].get(), float(self.vars["original_volume"].get()), self.log)
            else:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(temp_cut, out)

            self.log("HOÀN TẤT: " + out)
            self.set_status("Hoàn tất")
            self.after(0, lambda: messagebox.showinfo("Hoàn tất", "Đã xử lý xong. Xem Log để biết chi tiết."))
        except Exception as e:
            self.log("\nLỖI: " + str(e))
            self.log(traceback.format_exc())
            self.set_status("Có lỗi")
            self.after(0, lambda: messagebox.showerror("Lỗi", str(e)))
        finally:
            if temp_cut:
                try:
                    Path(temp_cut).unlink(missing_ok=True)
                except Exception:
                    pass


if __name__ == "__main__":
    App().mainloop()
