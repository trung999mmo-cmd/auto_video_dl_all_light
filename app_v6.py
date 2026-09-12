from __future__ import annotations

import os
import threading
from pathlib import Path

from tkinter import messagebox

import app_v4 as app4
from app_v5 import AppV5
import recap_core_v6 as core_v6

# AppV4.pipeline() resolves this function from globals in app_v4.
# Route it to the V6 Web AI implementation.
app4.web_ai_srt_mapped_chunked = core_v6.web_ai_srt_mapped_chunked


class AppV6(AppV5):
    """V6: one persistent dedicated Chrome + robust composer detection + no double runs."""

    def __init__(self):
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ.setdefault("PYTHONUTF8", "1")
        super().__init__()
        self.title("Video Recap Cutter V6")
        self._pipeline_running = False

        # IMPORTANT: use a NEW, clean, stable profile outside the version folder.
        # Do not import the old V5 Chrome profile because that profile may contain
        # Chrome's multi-profile picker state. The user logs in once here; V6 and
        # later versions can keep reusing this exact folder automatically.
        local = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        stable = local / "VideoRecapCutter" / "ChromeProfile"
        stable.mkdir(parents=True, exist_ok=True)
        self.web_profile_path = stable
        if "chrome_profile" in self.vars:
            self.vars["chrome_profile"].set(str(stable))

        self._replace_old_chrome_hint(self)
        self.log("V6: Chrome rieng SACH va co dinh: " + str(stable))
        self.log("V6: KHONG dung chrome_web_profile cu cua V5. Lan dau dang nhap ChatGPT mot lan; sau do tool dung lai dung Chrome nay.")
        self.log("V6: Da chan bam Chay 2 lan cung luc.")

    def _replace_old_chrome_hint(self, widget):
        try:
            for child in widget.winfo_children():
                try:
                    text = child.cget("text")
                    if isinstance(text, str) and "ĐÓNG cửa sổ Chrome" in text:
                        child.configure(
                            text="Lần đầu: bấm Mở Gemini / ChatGPT và đăng nhập. Có thể GIỮ Chrome mở; khi chạy tool sẽ bám đúng Chrome này và tự nhớ lần sau."
                        )
                except Exception:
                    pass
                self._replace_old_chrome_hint(child)
        except Exception:
            pass

    def open_web(self):
        mode = self.vars["web_mode"].get()
        url = "https://gemini.google.com/" if mode.startswith("Gemini") else "https://chatgpt.com/"
        try:
            core_v6.open_tool_browser(str(self.web_profile_path), url, self.log)
            messagebox.showinfo(
                "Chrome riêng của tool",
                "Đã mở Chrome RIÊNG của Video Recap Cutter.\n\n"
                "Lần đầu chỉ cần đăng nhập ChatGPT/Gemini trong Chrome này. "
                "Không cần chọn hồ sơ Chrome và KHÔNG cần đóng cửa sổ trước khi chạy.\n\n"
                "Từ lần sau tool sẽ dùng lại đúng Chrome/session này."
            )
        except Exception as e:
            messagebox.showerror("Không mở được Chrome riêng", str(e))

    def run_pipeline(self):
        if self._pipeline_running:
            messagebox.showwarning(
                "Tool đang chạy",
                "Đang có một lượt xử lý. Không bấm chạy lần hai; hãy xem Log của lượt hiện tại."
            )
            return

        self.save_cfg()
        self.logbox.delete("1.0", "end")
        self._pipeline_running = True
        try:
            self.run_btn.configure(state="disabled", text="Đang chạy...")
        except Exception:
            pass

        def worker():
            try:
                self.pipeline()
            finally:
                self._pipeline_running = False
                def restore():
                    try:
                        self.run_btn.configure(state="normal", text="Cắt video / tạo recap")
                    except Exception:
                        pass
                self.after(0, restore)

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    AppV6().mainloop()
