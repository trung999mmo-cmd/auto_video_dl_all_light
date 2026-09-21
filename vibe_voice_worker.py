from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
import wave
from pathlib import Path

# Chặn lỗi Windows cp1252 với tiếng Việt.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")


def fmt(sec: float) -> str:
    ms = max(0, int(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def parse_srt(path: str):
    text = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    rx = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [x.strip() for x in block.splitlines() if x.strip()]
        ti = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if ti is None:
            continue
        m = rx.search(lines[ti])
        if not m:
            continue
        a = list(map(int, m.groups()))
        st = a[0] * 3600 + a[1] * 60 + a[2] + a[3] / 1000
        en = a[4] * 3600 + a[5] * 60 + a[6] + a[7] / 1000
        body = " ".join(lines[ti + 1:]).strip()
        if body:
            out.append((st, en, body))
    return out


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def _message(kind: str, title: str, text: str) -> bool:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        if kind == "yesno":
            result = bool(messagebox.askyesno(title, text, parent=root))
        elif kind == "info":
            messagebox.showinfo(title, text, parent=root)
            result = True
        else:
            messagebox.showerror(title, text, parent=root)
            result = False
        root.destroy()
        return result
    except Exception:
        return False


def ensure_xtts_terms() -> None:
    marker = Path(__file__).resolve().parent / ".xtts_cpml_agreed"
    if os.environ.get("COQUI_TOS_AGREED") == "1" or marker.exists():
        os.environ["COQUI_TOS_AGREED"] = "1"
        return

    text = (
        "XTTS v2 yêu cầu xác nhận Coqui Public Model License (CPML) trước lần tải model đầu tiên.\n\n"
        "Điều khoản: https://coqui.ai/cpml\n\n"
        "Chỉ chọn Có nếu bạn đã đọc và đồng ý với điều khoản cho mục đích sử dụng của mình.\n\n"
        "Bạn có đồng ý tiếp tục không?"
    )
    if not _message("yesno", "Vibe Video - Điều khoản XTTS v2", text):
        raise RuntimeError("Bạn chưa xác nhận điều khoản XTTS v2 (CPML).")
    marker.write_text("CPML accepted by user.\n", encoding="utf-8")
    os.environ["COQUI_TOS_AGREED"] = "1"


def prepare_sample(ffmpeg: str, sample: str, temp_dir: Path) -> Path:
    """Chuẩn hóa mọi MP3/WAV/M4A/FLAC thành WAV mono 24k để XTTS đọc ổn định."""
    out = temp_dir / "reference_24k.wav"
    cmd = [
        ffmpeg, "-y", "-i", sample,
        "-t", "30",
        "-ac", "1", "-ar", "24000",
        "-af", "highpass=f=60,lowpass=f=11000",
        str(out),
    ]
    cp = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if cp.returncode != 0 or not out.exists():
        raise RuntimeError("Không chuyển được giọng mẫu sang WAV: " + (cp.stderr or "")[-1000:])
    d = wav_duration(str(out))
    if d < 2.0:
        raise RuntimeError("Giọng mẫu quá ngắn. Hãy dùng mẫu rõ tiếng dài ít nhất khoảng 3-6 giây.")
    print(f"Giọng mẫu đã chuẩn hóa: {d:.1f}s, mono 24kHz", flush=True)
    return out


def fit_and_delay(ffmpeg: str, src: str, dst: str, st: float, en: float):
    target = max(0.25, en - st)
    actual = max(0.05, wav_duration(src))
    ratio = actual / target
    filters = []
    while ratio > 2.0:
        filters.append("atempo=2.0")
        ratio /= 2.0
    while ratio < 0.5:
        filters.append("atempo=0.5")
        ratio /= 0.5
    filters.append(f"atempo={ratio:.5f}")
    delay = int(st * 1000)
    af = ",".join(filters) + f",adelay={delay}|{delay}"
    subprocess.run(
        [ffmpeg, "-y", "-i", src, "-af", af, "-ac", "2", "-ar", "44100", dst],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--srt", required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--ffmpeg", required=True)
    args = ap.parse_args()

    try:
        import torch
        import transformers
        from TTS.api import TTS
    except Exception as e:
        raise RuntimeError("Không import được XTTS. Hãy chạy INSTALL-VIBE-VOICE.bat: " + repr(e)) from e

    print("Vibe Voice | torch", torch.__version__, "| transformers", transformers.__version__, flush=True)

    items = parse_srt(args.srt)
    if not items:
        raise RuntimeError("SRT không có câu hợp lệ.")
    if not Path(args.sample).exists():
        raise FileNotFoundError("Không tìm thấy audio giọng mẫu: " + args.sample)

    ensure_xtts_terms()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Thiết bị XTTS:", device, flush=True)

    tmp = Path(tempfile.mkdtemp(prefix="vibe_voice_"))
    clips = []
    try:
        sample_wav = prepare_sample(args.ffmpeg, args.sample, tmp)

        print("Đang tải/khởi tạo model XTTS v2. Lần đầu có thể tải model lớn...", flush=True)
        _message(
            "info",
            "Vibe Video - Khởi tạo giọng",
            "Đang khởi tạo XTTS v2. Lần đầu có thể phải tải model khá lớn.\n\n"
            "Bấm OK rồi chờ. Khi hoàn tất, Vibe Video sẽ tự mở file nghe thử hoặc tiếp tục ghép video."
        )
        tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        for i, (st, en, text) in enumerate(items):
            raw = tmp / f"raw_{i:05}.wav"
            delayed = tmp / f"tts_{i:05}.wav"
            print(f"XTTS {i + 1}/{len(items)}: {text[:100]}", flush=True)
            tts.tts_to_file(
                text=text,
                speaker_wav=str(sample_wav),
                language=args.language,
                file_path=str(raw),
            )
            if not raw.exists() or raw.stat().st_size < 1000:
                raise RuntimeError(f"XTTS không tạo được audio block {i + 1}.")
            fit_and_delay(args.ffmpeg, str(raw), str(delayed), st, en)
            clips.append(delayed)

        cmd = [args.ffmpeg, "-y"]
        for c in clips:
            cmd += ["-i", str(c)]
        cmd += [
            "-filter_complex", f"amix=inputs={len(clips)}:normalize=0:dropout_transition=0",
            "-ac", "2", "-ar", "44100", args.out
        ]
        cp = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        if cp.returncode != 0 or not Path(args.out).exists():
            raise RuntimeError("Không ghép được audio XTTS: " + (cp.stderr or "")[-1200:])
        print("VIBE VOICE OK:", args.out, flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        detail = traceback.format_exc()
        print(detail, flush=True)
        msg = f"{type(e).__name__}: {e}" if str(e).strip() else f"{type(e).__name__}: lỗi không có mô tả"
        _message("error", "Vibe Video - Lỗi Voice Clone", msg + "\n\nChi tiết cuối:\n" + detail[-1800:])
        raise
