from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


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
    subprocess.run([ffmpeg, "-y", "-i", src, "-af", af, "-ac", "2", "-ar", "44100", dst], check=True)


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
        from TTS.api import TTS
    except Exception as e:
        raise SystemExit("Chưa cài Coqui TTS/XTTS. Hãy chạy INSTALL-VOICE-CLONE.bat. Chi tiết: " + str(e))

    items = parse_srt(args.srt)
    if not items:
        raise SystemExit("SRT không có câu hợp lệ")
    if not Path(args.sample).exists():
        raise SystemExit("Không tìm thấy audio giọng mẫu")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("Đang tải XTTS v2 trên", device, "- lần đầu có thể phải tải model lớn...")
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    tmp = Path(tempfile.mkdtemp(prefix="xtts_recap_"))
    clips = []
    try:
        for i, (st, en, text) in enumerate(items):
            raw = tmp / f"raw_{i:05}.wav"
            delayed = tmp / f"tts_{i:05}.wav"
            print(f"XTTS {i + 1}/{len(items)}: {text[:80]}")
            tts.tts_to_file(text=text, speaker_wav=args.sample, language=args.language, file_path=str(raw))
            fit_and_delay(args.ffmpeg, str(raw), str(delayed), st, en)
            clips.append(delayed)

        cmd = [args.ffmpeg, "-y"]
        for c in clips:
            cmd += ["-i", str(c)]
        cmd += ["-filter_complex", f"amix=inputs={len(clips)}:normalize=0:dropout_transition=0", "-ac", "2", "-ar", "44100", args.out]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
