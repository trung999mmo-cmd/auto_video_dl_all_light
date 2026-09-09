from __future__ import annotations

import shutil
import threading
import traceback
from pathlib import Path

from tkinter import messagebox, ttk

from app_v3 import AppV3
import recap_core_v2 as core
from recap_core_v4 import (
    gemini_api_srt_mapped,
    output_duration,
    web_ai_srt_mapped_chunked,
)


class AppV4(AppV3):
    """V4: luồng xử lý giống tool mẫu hơn.

    Quan trọng: AI nhìn VIDEO GỐC + biết quy tắc LẤY/BỎ, tạo SRT theo timeline
    VIDEO SAU CẮT. Sau đó tool mới tạo TTS, cắt video và ghép audio.
    """

    def __init__(self):
        super().__init__()
        self.title("Video Recap Cutter V4")

    def build_video(self, root):
        sec = ttk.LabelFrame(root, text="1. Video và đầu ra", style="Section.TLabelframe")
        sec.pack(fill="x", padx=18, pady=6)
        self.row_entry(sec, "Video gốc", self.V("input_video"), "Chọn video", self.pick_video)
        self.row_entry(sec, "Nơi lưu video", self.V("output_video"), "Chọn nơi lưu", lambda: self.pick_save("output_video", ".mp4", [("MP4", "*.mp4")]))
        self.row_entry(sec, "Map JSON", self.V("map_json"), "Lưu map", lambda: self.pick_save("map_json", ".json", [("JSON", "*.json")]))

        r = ttk.Frame(sec)
        r.pack(fill="x", padx=8, pady=4)
        ttk.Label(r, text="Nhịp cắt", width=24).pack(side="left")
        ttk.Label(r, text="Lấy").pack(side="left")
        ttk.Entry(r, textvariable=self.V("keep_sec", "2"), width=7).pack(side="left", padx=5)
        ttk.Label(r, text="giây, bỏ").pack(side="left")
        ttk.Entry(r, textvariable=self.V("drop_sec", "8"), width=7).pack(side="left", padx=5)
        ttk.Label(r, text="giây").pack(side="left")
        pre = ttk.Combobox(r, state="readonly", values=["Lấy 2 / Bỏ 8", "Lấy 2 / Bỏ 10", "Lấy 3 / Bỏ 2", "Lấy 5 / Bỏ 10"], width=18)
        pre.set("Lấy 2 / Bỏ 8")
        pre.pack(side="left", padx=20)
        pre.bind("<<ComboboxSelected>>", lambda e: self.set_preset_v4(pre.get()))

        ttk.Label(sec, text="Bạn điền Lấy/Bỏ ở đây. Khi chạy Web AI, tool tự chèn đúng hai số này vào prompt recap và gửi tự động.", foreground="#555").pack(anchor="w", padx=32, pady=(2, 4))

        rr = ttk.Frame(sec)
        rr.pack(fill="x", padx=8, pady=(4, 8))
        ttk.Checkbutton(rr, text="Tạo thêm SRT template từ nhịp cắt", variable=self.B("make_template", False)).pack(side="left")
        ttk.Entry(rr, textvariable=self.V("template_srt")).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(rr, text="Lưu SRT", command=lambda: self.pick_save("template_srt", ".srt", [("SRT", "*.srt")]), width=16).pack(side="left")

    def set_preset_v4(self, text):
        import re
        m = re.search(r"Lấy (\d+(?:\.\d+)?) / Bỏ (\d+(?:\.\d+)?)", text)
        if m:
            self.vars["keep_sec"].set(m.group(1))
            self.vars["drop_sec"].set(m.group(2))

    def build_ai(self, root):
        super().build_ai(root)
        # Không thêm ô prompt thủ công: prompt recap dài được tool tự sinh từ Lấy/Bỏ + ngôn ngữ.

    def pipeline(self):
        temp_cut = None
        try:
            self.log("Bat dau xu ly...")
            inp = self.vars["input_video"].get().strip()
            out = self.vars["output_video"].get().strip()
            if not inp or not Path(inp).exists():
                raise FileNotFoundError("Chưa chọn video gốc")
            if not out:
                raise ValueError("Chưa chọn nơi lưu video")

            keep = float(self.vars["keep_sec"].get())
            drop = float(self.vars["drop_sec"].get())
            total = core.duration(inp)
            segs = core.build_segments(total, keep, drop)
            recap_dur = output_duration(segs)
            out_dir = str(Path(out).parent)

            self.log(f"Video sau khi cat se luu tai: {out}")
            self.log(f"Thu muc output: {out_dir}")
            self.log(f"INFO: Input video duration={total:.3f}s")
            self.log(f"INFO: Built {len(segs)} kept segments | Lay {keep:g}s / Bo {drop:g}s | output={recap_dur:.3f}s")

            if self.vars["map_json"].get().strip():
                core.save_map(segs, self.vars["map_json"].get().strip())
                self.log("INFO: Wrote mapping JSON: " + self.vars["map_json"].get().strip())
            if self.vars["make_template"].get() and self.vars["template_srt"].get().strip():
                core.template_srt(segs, self.vars["template_srt"].get().strip())
                self.log("INFO: Wrote SRT template: " + self.vars["template_srt"].get().strip())

            # ---------- 1) Tạo SRT TRƯỚC, từ video gốc ----------
            ai = self._ai_mode()
            srt_path = ""
            core_lang = self._sync_language()

            if ai == "web":
                srt_path = self.vars["web_srt"].get().strip()
                if not srt_path:
                    raise ValueError("Chưa chọn SRT Web AI đầu ra")
                mode = self.vars["web_mode"].get()
                provider = "ChatGPT" if mode.startswith("ChatGPT") else "Gemini"
                passes = 1
                if "2 pass" in mode:
                    passes = 2
                elif "3 pass" in mode:
                    passes = 3
                elif "4 pass" in mode:
                    passes = 4

                source = self.vars["web_video"].get().strip() or inp
                if not Path(source).exists():
                    source = inp
                source_dur = core.duration(source)
                if abs(source_dur - total) > 0.75:
                    raise ValueError("Video gửi Web AI khác thời lượng video gốc. Hãy chọn chính video gốc để mapping Lấy/Bỏ khớp chính xác.")

                self.log(f"INFO: {provider} web video: {source}")
                self.log(f"INFO: {provider} web mapping: {len(segs)} block, duration={total:.3f}s")
                self.set_status(f"Đang chạy {provider} Web...")
                srt_text = web_ai_srt_mapped_chunked(
                    source,
                    provider,
                    core_lang,
                    keep,
                    drop,
                    self.vars["density"].get(),
                    self.vars["web_note"].get(),
                    int(float(self.vars["web_wait"].get() or 1800)),
                    str(self.web_profile_path),
                    int(self.vars["chunk_min"].get()),
                    self.log,
                    passes,
                )
                Path(srt_path).parent.mkdir(parents=True, exist_ok=True)
                Path(srt_path).write_text(srt_text, encoding="utf-8")
                self.log(f"INFO: Da luu SRT {mode}: {srt_path}")

            elif ai == "api":
                srt_path = self.vars["api_srt"].get().strip()
                if not srt_path:
                    raise ValueError("Chưa chọn SRT API đầu ra")
                keys = [x.strip() for x in self.vars["api_keys"].get().replace("\n", ";").replace(",", ";").split(";") if x.strip()]
                if not keys:
                    raise ValueError("Chưa nhập Gemini API key")
                source = self.vars["api_video"].get().strip() or inp
                if not Path(source).exists():
                    source = inp
                if abs(core.duration(source) - total) > 0.75:
                    raise ValueError("Video gửi API khác thời lượng video gốc. Hãy chọn chính video gốc để mapping Lấy/Bỏ khớp.")
                last = None
                srt_text = ""
                for i, key in enumerate(keys, 1):
                    try:
                        self.set_status(f"Gemini API key {i}/{len(keys)}...")
                        srt_text = gemini_api_srt_mapped(
                            source, key, self.vars["gemini_model"].get().strip(), core_lang,
                            keep, drop, self.vars["density"].get(), self.vars["api_note"].get(), segs, self.log
                        )
                        break
                    except Exception as e:
                        last = e
                        self.log("INFO: API key loi, thu key tiep theo: " + str(e))
                if not srt_text:
                    raise last or RuntimeError("Không tạo được SRT bằng Gemini API")
                Path(srt_path).parent.mkdir(parents=True, exist_ok=True)
                Path(srt_path).write_text(srt_text, encoding="utf-8")
                self.log("INFO: Da luu SRT Gemini API: " + srt_path)

            # ---------- 2) Tạo giọng TTS từ SRT TRƯỚC KHI render video ----------
            wav = ""
            if self.vars["use_tts"].get():
                if not srt_path or not Path(srt_path).exists():
                    raise ValueError("Đã bật tạo giọng nhưng chưa có SRT. Hãy bật Gemini/ChatGPT Web hoặc Gemini API.")
                wav = self.vars["wav_path"].get().strip()
                if not wav:
                    raise ValueError("Chưa chọn file audio WAV")
                self.on_voice_selected()
                engine = self.vars["tts_engine"].get()
                voice = self.voice_value()
                self.log(f"INFO: Generating TTS audio from SRT first: {srt_path}")
                self.set_status("Đang tạo giọng đọc...")
                if engine == "Edge TTS":
                    core.srt_to_wav_edge(srt_path, wav, voice, self.log)
                elif engine == "Piper Offline":
                    core.srt_to_wav_piper(srt_path, wav, voice, self.log)
                elif engine == "TikTok / CapCut":
                    core.srt_to_wav_tiktok(srt_path, wav, voice, self.vars["sessionid"].get().strip(), self.log)
                else:
                    core.srt_to_wav_xtts(srt_path, wav, self.vars["voice_sample"].get().strip(), core_lang, self.log)
                self.log("INFO: Generated TTS audio: " + wav)

            # ---------- 3) Sau khi SRT/TTS xong mới cắt video ----------
            temp_cut = str(Path(out).with_name(Path(out).stem + "__cut_temp.mp4"))
            self.set_status("Đang cắt video...")
            self.log(f"INFO: Rendering {len(segs)} kept segments: {temp_cut}")
            core.cut_video(inp, temp_cut, segs, self.log)
            self.log("INFO: Wrote cut video: " + temp_cut)

            # ---------- 4) Ghép TTS vào video cuối ----------
            if self.vars["use_tts"].get():
                self.set_status("Đang ghép audio vào video...")
                if self.vars["keep_original_audio"].get():
                    self.log("INFO: Mixing generated TTS with low original audio: " + out)
                else:
                    self.log("INFO: Replacing original video audio with generated TTS audio: " + out)
                core.mix_video_audio(
                    temp_cut, wav, out,
                    self.vars["keep_original_audio"].get(),
                    float(self.vars["original_volume"].get()),
                    self.log,
                )
                self.log("INFO: Wrote final video with TTS audio: " + out)
            else:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(temp_cut, out)

            self.log("Hoan tat: " + out)
            self.log("Thu muc output: " + out_dir)
            self.set_status("Hoàn tất")
            self.after(0, lambda: messagebox.showinfo("Hoàn tất", "Đã xử lý xong. Chrome Web AI được giữ mở để bạn kiểm tra SRT."))
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
    AppV4().mainloop()
