from __future__ import annotations

import os
import shutil
import webbrowser
from pathlib import Path

from tkinter import messagebox

import app_v4 as app4
import app_v5 as app5
import recap_core_v2 as core
import vibe_core
from app_v6 import AppV6

# Route toàn bộ Web AI và Voice Clone qua lõi Vibe.
app4.web_ai_srt_mapped_chunked = vibe_core.web_ai_srt_mapped_chunked
core.srt_to_wav_xtts = vibe_core.srt_to_wav_xtts
core.xtts_ready = vibe_core.xtts_ready

# Câu nghe thử mang đúng thương hiệu.
app5.PREVIEW_TEXT["Tiếng Việt"] = "Xin chào, đây là giọng đọc thử của Vibe Video."
app5.PREVIEW_TEXT["English"] = "Hello, this is a voice preview from Vibe Video."


class VibeVideo(AppV6):
    def __init__(self):
        os.environ["PYTHONIOENCODING"] = "utf-8"
        os.environ["PYTHONUTF8"] = "1"
        super().__init__()

        self.title("Vibe Video")
        self._manual_driver = None

        local = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        root = local / "VibeVideo"
        stable_chrome = root / "ChromeProfile"
        stable_voices = root / "VoiceProfiles"
        stable_chrome.mkdir(parents=True, exist_ok=True)
        stable_voices.mkdir(parents=True, exist_ok=True)

        # Tự mang giọng mẫu nằm trong gói sang kho cố định để các bản sau không phải copy lại.
        old_voice_dir = Path(self.voice_profiles_path)
        try:
            if old_voice_dir.exists() and old_voice_dir.resolve() != stable_voices.resolve():
                for item in old_voice_dir.iterdir():
                    if item.name.lower().startswith("readme"):
                        continue
                    dst = stable_voices / item.name
                    if item.is_dir():
                        shutil.copytree(item, dst, dirs_exist_ok=True)
                    elif item.is_file():
                        shutil.copy2(item, dst)
        except Exception as e:
            self.log("VIBE: Không tự chuyển được kho giọng cũ: " + str(e))

        self.web_profile_path = stable_chrome
        self.voice_profiles_path = stable_voices
        if "chrome_profile" in self.vars:
            self.vars["chrome_profile"].set(str(stable_chrome))

        self._rebrand(self)
        self._replace_path_labels(self, str(old_voice_dir), str(stable_voices))
        self.refresh_voices()

        self.log("VIBE VIDEO READY")
        self.log("VIBE: Chrome cố định: " + str(stable_chrome))
        self.log("VIBE: Kho giọng cố định: " + str(stable_voices))
        ok, msg = vibe_core.xtts_ready()
        self.log("VIBE: Voice Clone: " + ("Đã cài" if ok else msg))

    def _rebrand(self, widget):
        try:
            for child in widget.winfo_children():
                try:
                    t = child.cget("text")
                    if isinstance(t, str):
                        nt = t.replace("Video Recap Cutter", "Vibe Video")
                        nt = nt.replace("VideoRecapCutter", "VibeVideo")
                        nt = nt.replace("INSTALL-VOICE-CLONE.bat", "INSTALL-VIBE-VOICE.bat")
                        if nt != t:
                            child.configure(text=nt)
                        # Cập nhật đường dẫn kho giọng cũ hiển thị trên UI.
                        if "voice_profiles" in nt.lower() and "Thư mục lưu" not in nt:
                            pass
                except Exception:
                    pass
                self._rebrand(child)
        except Exception:
            pass

    def _replace_path_labels(self, widget, old_path: str, new_path: str):
        try:
            for child in widget.winfo_children():
                try:
                    t = child.cget("text")
                    if isinstance(t, str) and old_path and old_path in t:
                        child.configure(text=t.replace(old_path, new_path))
                except Exception:
                    pass
                self._replace_path_labels(child, old_path, new_path)
        except Exception:
            pass

    def open_web(self):
        mode = self.vars["web_mode"].get()
        url = "https://gemini.google.com/" if mode.startswith("Gemini") else "https://chatgpt.com/"
        try:
            d = vibe_core.open_automation_driver(str(self.web_profile_path), self.log)
            d.get(url)
            self._manual_driver = d
            messagebox.showinfo(
                "Vibe Video - Chrome riêng",
                "Đã mở đúng Chrome riêng của Vibe Video.\n\n"
                "Lần đầu: đăng nhập ChatGPT/Gemini trong Chrome này một lần.\n"
                "Sau đó CỨ GIỮ CHROME MỞ cũng được. Khi bấm chạy, tool bám lại chính Chrome này, không mở profile khác."
            )
        except Exception as e:
            messagebox.showerror("Vibe Video - Không mở được Chrome", str(e))

    def open_chrome_profile(self):
        self.web_profile_path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.web_profile_path))
        else:
            webbrowser.open(self.web_profile_path.as_uri())

    def open_voice_profiles(self):
        self.voice_profiles_path.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(str(self.voice_profiles_path))
        else:
            webbrowser.open(self.voice_profiles_path.as_uri())

    def show_help(self):
        messagebox.showinfo(
            "Vibe Video - Hướng dẫn nhanh",
            "1. Chọn video gốc và nhập Lấy/Bỏ.\n"
            "2. Chọn ChatGPT Web hoặc Gemini Web.\n"
            "3. Lần đầu bấm Mở Gemini / ChatGPT và đăng nhập vào Chrome riêng của Vibe Video.\n"
            "4. Chọn ngôn ngữ và giọng đọc. Giọng mẫu/VietVoice sẽ dùng Voice Clone XTTS.\n"
            "5. Bấm Nghe thử giọng để kiểm tra trước.\n"
            "6. Bấm Cắt video / tạo recap đúng một lần.\n\n"
            "Luồng Web AI: đính kèm VIDEO -> chờ upload -> điền TOÀN BỘ prompt -> gửi đúng 1 lần -> lấy SRT -> tạo giọng -> cắt -> ghép video."
        )


if __name__ == "__main__":
    VibeVideo().mainloop()
