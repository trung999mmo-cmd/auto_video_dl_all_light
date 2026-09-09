from __future__ import annotations

import os
import tempfile
import threading
import traceback
import webbrowser
from pathlib import Path

from tkinter import messagebox

from app_v4 import AppV4
from app_v3 import PREVIEW_TEXT
import recap_core_v2 as core


class AppV5(AppV4):
    """V5: V4 workflow + fixed XTTS first-run/preview behavior."""

    def __init__(self):
        super().__init__()
        self.title("Video Recap Cutter V5")

    def preview_voice(self):
        self.on_voice_selected()
        engine = self.vars["tts_engine"].get()
        voice = self.voice_value()
        core_lang = self._sync_language()
        sample = self.vars["voice_sample"].get().strip()
        session = self.vars["sessionid"].get().strip()
        text = PREVIEW_TEXT.get(core_lang, PREVIEW_TEXT["Tiếng Việt"])

        def work():
            logs = []
            try:
                self.after(0, lambda: self.set_status("Đang tạo giọng nghe thử..."))
                tmp = Path(tempfile.mkdtemp(prefix="recap_preview_"))
                srt = tmp / "preview.srt"
                wav = tmp / "preview.wav"
                srt.write_text(
                    f"1\n00:00:00,000 --> 00:00:05,000\n{text}\n",
                    encoding="utf-8",
                )

                def log_line(x):
                    line = str(x)
                    logs.append(line)
                    try:
                        self.log("PREVIEW: " + line)
                    except Exception:
                        pass

                if engine == "Edge TTS":
                    core.srt_to_wav_edge(str(srt), str(wav), voice, log_line)
                elif engine == "Piper Offline":
                    core.srt_to_wav_piper(str(srt), str(wav), voice, log_line)
                elif engine == "TikTok / CapCut":
                    core.srt_to_wav_tiktok(str(srt), str(wav), voice, session, log_line)
                else:
                    if not sample or not Path(sample).exists():
                        raise FileNotFoundError("Chưa có audio mẫu cho giọng đã chọn.")
                    ok, ready_msg = core.xtts_ready()
                    if not ok:
                        raise RuntimeError(ready_msg)
                    log_line("Voice Clone XTTS: lần đầu có thể tải model lớn và sẽ hiện hộp xác nhận điều khoản.")
                    core.srt_to_wav_xtts(str(srt), str(wav), sample, core_lang, log_line)

                if not wav.exists() or wav.stat().st_size < 1000:
                    raise RuntimeError("Không tạo được file WAV nghe thử.")

                self.after(0, lambda: self.set_status("Nghe thử xong"))
                if os.name == "nt":
                    os.startfile(str(wav))
                else:
                    webbrowser.open(wav.as_uri())
            except BaseException as e:
                detail = str(e).strip()
                if not detail or detail == "None":
                    detail = repr(e)
                tail = "\n".join(logs[-18:]).strip()
                if tail:
                    detail += "\n\nLog cuối:\n" + tail
                tb = traceback.format_exc()
                try:
                    self.log("PREVIEW ERROR: " + detail)
                    self.log(tb)
                except Exception:
                    pass
                self.after(0, lambda: self.set_status("Nghe thử lỗi"))
                self.after(0, lambda d=detail: messagebox.showerror("Nghe thử giọng lỗi", d))

        threading.Thread(target=work, daemon=True).start()


if __name__ == "__main__":
    AppV5().mainloop()
