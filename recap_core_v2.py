from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Tuple

import requests

LogFn = Callable[[str], None]

LANGUAGES = {
    "Tiếng Việt": "vi-VN",
    "English": "en-US",
    "日本語": "ja-JP",
    "한국어": "ko-KR",
    "中文": "zh-CN",
    "ไทย": "th-TH",
    "Français": "fr-FR",
    "Deutsch": "de-DE",
    "Español": "es-ES",
    "Indonesia": "id-ID",
    "Português": "pt-BR",
    "Italiano": "it-IT",
    "Русский": "ru-RU",
    "العربية": "ar-SA",
    "हिन्दी": "hi-IN",
}

XTTS_LANG = {
    "Tiếng Việt": "vi",
    "English": "en",
    "日本語": "ja",
    "한국어": "ko",
    "中文": "zh-cn",
    "ไทย": "th",
    "Français": "fr",
    "Deutsch": "de",
    "Español": "es",
    "Indonesia": "id",
    "Português": "pt",
    "Italiano": "it",
    "Русский": "ru",
    "العربية": "ar",
    "हिन्दी": "hi",
}

EDGE_VOICES = {
    "vi-VN-HoaiMyNeural": "Nữ Việt - Hoài My",
    "vi-VN-NamMinhNeural": "Nam Việt - Nam Minh",
    "en-US-AriaNeural": "US Nữ - Aria",
    "en-US-GuyNeural": "US Nam - Guy",
    "en-US-JennyNeural": "US Nữ - Jenny",
    "en-US-DavisNeural": "US Nam - Davis",
    "en-GB-SoniaNeural": "UK Nữ - Sonia",
    "en-GB-RyanNeural": "UK Nam - Ryan",
    "ja-JP-NanamiNeural": "Nhật Nữ - Nanami",
    "ja-JP-KeitaNeural": "Nhật Nam - Keita",
    "ko-KR-SunHiNeural": "Hàn Nữ - SunHi",
    "ko-KR-InJoonNeural": "Hàn Nam - InJoon",
    "zh-CN-XiaoxiaoNeural": "Trung Nữ - Xiaoxiao",
    "zh-CN-YunxiNeural": "Trung Nam - Yunxi",
    "th-TH-PremwadeeNeural": "Thái Nữ - Premwadee",
    "th-TH-NiwatNeural": "Thái Nam - Niwat",
    "fr-FR-DeniseNeural": "Pháp Nữ - Denise",
    "fr-FR-HenriNeural": "Pháp Nam - Henri",
    "de-DE-KatjaNeural": "Đức Nữ - Katja",
    "de-DE-ConradNeural": "Đức Nam - Conrad",
    "es-ES-ElviraNeural": "TBN Nữ - Elvira",
    "es-ES-AlvaroNeural": "TBN Nam - Alvaro",
    "id-ID-GadisNeural": "Indonesia Nữ - Gadis",
    "id-ID-ArdiNeural": "Indonesia Nam - Ardi",
    "pt-BR-FranciscaNeural": "Brazil Nữ - Francisca",
    "pt-BR-AntonioNeural": "Brazil Nam - Antonio",
    "it-IT-ElsaNeural": "Ý Nữ - Elsa",
    "it-IT-DiegoNeural": "Ý Nam - Diego",
    "ru-RU-SvetlanaNeural": "Nga Nữ - Svetlana",
    "ru-RU-DmitryNeural": "Nga Nam - Dmitry",
    "ar-SA-ZariyahNeural": "Ả Rập Nữ - Zariyah",
    "ar-SA-HamedNeural": "Ả Rập Nam - Hamed",
    "hi-IN-SwaraNeural": "Hindi Nữ - Swara",
    "hi-IN-MadhurNeural": "Hindi Nam - Madhur",
}

# TikTok/CapCut voice codes are unofficial and can change when TikTok changes its service.
TIKTOK_VOICES = {
    "en_us_001": "English US Female 1",
    "en_us_002": "English US Female 2",
    "en_us_006": "English US Male 1",
    "en_us_007": "English US Male 2",
    "en_us_009": "English US Male 3",
    "en_us_010": "English US Male 4",
    "en_uk_001": "English UK Male 1",
    "en_uk_003": "English UK Male 2",
    "fr_001": "French Male 1",
    "fr_002": "French Male 2",
    "de_001": "German Female",
    "de_002": "German Male",
    "es_002": "Spanish Male",
    "es_mx_002": "Spanish MX Male",
    "br_001": "Portuguese BR Female 1",
    "br_003": "Portuguese BR Female 2",
    "br_004": "Portuguese BR Female 3",
    "br_005": "Portuguese BR Male",
    "id_001": "Indonesian Female",
    "jp_001": "Japanese Female 1",
    "jp_003": "Japanese Female 2",
    "jp_005": "Japanese Female 3",
    "jp_006": "Japanese Male",
    "kr_002": "Korean Male 1",
    "kr_003": "Korean Female",
    "kr_004": "Korean Male 2",
}


@dataclass
class Segment:
    src_start: float
    src_end: float
    out_start: float
    out_end: float


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base / name


def voices_dir() -> Path:
    p = app_dir() / "voices"
    p.mkdir(parents=True, exist_ok=True)
    return p


def find_bin(name: str) -> str:
    exe = name + (".exe" if os.name == "nt" and not name.lower().endswith(".exe") else "")
    candidates = [app_dir() / exe, resource_path(exe), app_dir() / "piper" / exe]
    for c in candidates:
        if c.exists():
            return str(c)
    hit = shutil.which(name) or shutil.which(exe)
    if hit:
        return hit
    raise FileNotFoundError(f"Không tìm thấy {exe}.")


def run(cmd: List[str], log: LogFn = print, cwd: str | None = None) -> None:
    log("$ " + " ".join(f'\"{x}\"' if " " in str(x) else str(x) for x in cmd))
    p = subprocess.Popen(
        [str(x) for x in cmd],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        creationflags=(0x08000000 if os.name == "nt" else 0),
    )
    assert p.stdout
    for line in p.stdout:
        t = line.rstrip()
        if t:
            log(t)
    rc = p.wait()
    if rc != 0:
        raise RuntimeError(f"Lệnh lỗi mã {rc}")


def duration(path: str) -> float:
    out = subprocess.check_output(
        [find_bin("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
        text=True,
        creationflags=(0x08000000 if os.name == "nt" else 0),
    )
    return float(out.strip())


def build_segments(total: float, keep: float, drop: float) -> List[Segment]:
    if keep <= 0 or drop < 0:
        raise ValueError("Giữ phải > 0 và Bỏ phải >= 0")
    segs: List[Segment] = []
    src = 0.0
    out = 0.0
    while src < total - 0.02:
        end = min(src + keep, total)
        if end - src > 0.03:
            segs.append(Segment(src, end, out, out + (end - src)))
            out += end - src
        src += keep + drop
    return segs


def save_map(segs: List[Segment], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps({"version": 2, "segments": [s.__dict__ for s in segs]}, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_srt(sec: float) -> str:
    ms = max(0, int(round(sec * 1000)))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def template_srt(segs: List[Segment], path: str) -> None:
    rows: List[str] = []
    for i, s in enumerate(segs, 1):
        rows += [str(i), f"{fmt_srt(s.out_start)} --> {fmt_srt(s.out_end)}", f"[Đoạn {i}]", ""]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(rows), encoding="utf-8")


def cut_video(input_path: str, output_path: str, segs: List[Segment], log: LogFn = print) -> None:
    ffmpeg = find_bin("ffmpeg")
    temp = Path(tempfile.mkdtemp(prefix="recap_segments_"))
    try:
        parts: List[Path] = []
        for i, s in enumerate(segs):
            p = temp / f"seg_{i:05}.mp4"
            run([
                ffmpeg, "-y", "-ss", f"{s.src_start:.3f}", "-to", f"{s.src_end:.3f}", "-i", input_path,
                "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(p)
            ], log)
            parts.append(p)
        lst = temp / "concat.txt"
        lst.write_text("\n".join("file '" + str(p).replace("'", "'\\''") + "'" for p in parts), encoding="utf-8")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", output_path], log)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def _sec(groups: Tuple[str, ...]) -> float:
    a = list(map(int, groups))
    return a[0] * 3600 + a[1] * 60 + a[2] + a[3] / 1000


def parse_srt(text: str) -> List[Tuple[float, float, str]]:
    text = text.replace("\r\n", "\n").strip()
    blocks = re.split(r"\n\s*\n", text)
    out: List[Tuple[float, float, str]] = []
    rx = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")
    for b in blocks:
        lines = [x.strip() for x in b.splitlines() if x.strip()]
        ti = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if ti is None:
            continue
        m = rx.search(lines[ti])
        if not m:
            continue
        g = m.groups()
        st = _sec(g[:4])
        en = _sec(g[4:])
        body = " ".join(lines[ti + 1:]).strip()
        if body:
            out.append((st, en, body))
    return out


def normalize_srt(text: str, max_duration: float | None = None) -> str:
    rows: List[str] = []
    for i, (st, en, body) in enumerate(parse_srt(text), 1):
        if max_duration is not None:
            st = min(st, max_duration)
            en = min(en, max_duration)
        if en <= st:
            continue
        rows += [str(i), f"{fmt_srt(st)} --> {fmt_srt(en)}", body, ""]
    return "\n".join(rows).strip() + "\n"


def shift_srt(text: str, offset: float) -> str:
    rows: List[str] = []
    for i, (st, en, body) in enumerate(parse_srt(text), 1):
        rows += [str(i), f"{fmt_srt(st + offset)} --> {fmt_srt(en + offset)}", body, ""]
    return "\n".join(rows)


def _strip_fence(text: str) -> str:
    text = (text or "").strip()
    m = re.search(r"```(?:srt)?\s*(.*?)```", text, re.I | re.S)
    if m:
        return m.group(1).strip()
    return re.sub(r"^```(?:srt)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()


def _density_hint(density: str) -> str:
    return {
        "Ít chữ": "ngắn gọn, ít câu, chỉ giữ ý quan trọng",
        "Vừa": "mật độ vừa phải, kể rõ nội dung",
        "Nhiều chữ": "chi tiết, nhiều lời dẫn nhưng không bịa",
    }.get(density, density)


def gemini_api_srt(video_path: str, api_key: str, model: str, language: str, note: str, density: str, log: LogFn = print, two_pass: bool = False, delay_sec: int = 5) -> str:
    import google.generativeai as genai

    genai.configure(api_key=api_key.strip())
    log("Đang upload video lên Gemini API...")
    f = genai.upload_file(video_path)
    while getattr(f, "state", None) and getattr(f.state, "name", "") == "PROCESSING":
        time.sleep(3)
        f = genai.get_file(f.name)
        log("Gemini đang xử lý video...")
    if getattr(getattr(f, "state", None), "name", "") == "FAILED":
        raise RuntimeError("Gemini xử lý file thất bại")

    gm = genai.GenerativeModel(model)
    hint = _density_hint(density)
    if not two_pass:
        prompt = f"""Xem toàn bộ video và viết lời thuyết minh recap bằng {language}.
Trả về DUY NHẤT SRT hợp lệ, timeline bám sát hình ảnh, không Markdown, không ```.
Mức lời: {hint}. Không bịa chi tiết không thấy/nghe được.
Ghi chú: {note or 'không có'}"""
        log(f"Đang gọi model {model}...")
        return _strip_fence(gm.generate_content([f, prompt], request_options={"timeout": 1800}).text)

    log("Gemini API pass 1/2: phân tích video...")
    p1 = f"""Phân tích video thật kỹ theo trình tự thời gian để chuẩn bị viết recap bằng {language}.
Ghi lại nhân vật, hành động, chuyển cảnh và mốc thời gian quan trọng. Không bịa.
Mức chi tiết: {hint}. Ghi chú: {note or 'không có'}"""
    analysis = (gm.generate_content([f, p1], request_options={"timeout": 1800}).text or "").strip()
    time.sleep(max(0, delay_sec))
    log("Gemini API pass 2/2: tạo SRT...")
    p2 = f"""Dựa trên video và bản phân tích dưới đây, tạo SRT recap bằng {language}.
Trả về DUY NHẤT SRT hợp lệ, không Markdown, timeline phải nằm trong video và bám hình ảnh.
Bản phân tích:\n{analysis[:30000]}"""
    return _strip_fence(gm.generate_content([f, p2], request_options={"timeout": 1800}).text)


def test_gemini_key(api_key: str, model: str) -> Tuple[bool, str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key.strip())
        r = genai.GenerativeModel(model).generate_content("Trả lời đúng một từ: OK", request_options={"timeout": 30})
        return True, (r.text or "OK").strip()[:100]
    except Exception as e:
        return False, str(e)


def split_for_web(video_path: str, minutes: int, out_dir: str, log: LogFn = print) -> List[str]:
    ffmpeg = find_bin("ffmpeg")
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    pattern = str(Path(out_dir) / "chunk_%03d.mp4")
    run([ffmpeg, "-y", "-i", video_path, "-map", "0", "-c", "copy", "-f", "segment", "-segment_time", str(minutes * 60), "-reset_timestamps", "1", pattern], log)
    return [str(p) for p in sorted(Path(out_dir).glob("chunk_*.mp4"))]


def _last_response_text(driver, provider: str) -> str:
    selectors = []
    if provider.lower().startswith("gemini"):
        selectors = ["message-content", ".model-response-text", "[data-test-id='model-response']", "main"]
    else:
        selectors = ["[data-message-author-role='assistant']", "article", "main"]
    best = ""
    for sel in selectors:
        try:
            els = driver.find_elements("css selector", sel)
            for e in els[-5:]:
                t = (e.text or "").strip()
                if len(t) > len(best):
                    best = t
        except Exception:
            pass
    return best


def web_ai_srt(video_path: str, provider: str, language: str, note: str, density: str, wait_seconds: int, profile_dir: str | None, log: LogFn = print, passes: int = 1, ui_mode: str = "Tự động") -> str:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait

    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    if profile_dir:
        Path(profile_dir).mkdir(parents=True, exist_ok=True)
        opts.add_argument(f"--user-data-dir={profile_dir}")
    driver = webdriver.Chrome(options=opts)
    provider_l = provider.lower()
    url = "https://gemini.google.com/" if provider_l.startswith("gemini") else "https://chatgpt.com/"
    try:
        driver.get(url)
        log("Chrome đã mở. Nếu chưa đăng nhập, hãy đăng nhập trong cửa sổ Chrome này.")
        time.sleep(5)

        file_input = None
        end = time.time() + 60
        while time.time() < end and file_input is None:
            try:
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if inputs:
                    file_input = inputs[-1]
                    break
            except Exception:
                pass
            time.sleep(1)
        if file_input is None:
            log("Không thấy input file ngay; thử bấm nút đính kèm bằng selector dự phòng.")
            for sel in ["button[aria-label*='Upload']", "button[aria-label*='Đính']", "button[aria-label*='Attach']", "button[aria-label*='Tải']"]:
                try:
                    driver.find_element(By.CSS_SELECTOR, sel).click()
                    time.sleep(1)
                    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if inputs:
                        file_input = inputs[-1]
                        break
                except Exception:
                    pass
        if file_input is None:
            raise RuntimeError("Không tìm thấy ô upload video trên Web AI. Website có thể đã đổi giao diện.")
        file_input.send_keys(str(Path(video_path).resolve()))
        log("Đã gửi video lên Web AI, đang chờ upload...")
        time.sleep(8)

        prompt = f"""Xem video đã upload và tạo SRT recap bằng {language}.
Chỉ trả về SRT hợp lệ, không Markdown, timeline bám sát hình ảnh và không bịa.
Mức lời: {_density_hint(density)}.
Ghi chú: {note or 'không có'}"""

        def send_prompt(text: str) -> None:
            box = None
            for sel in ["#prompt-textarea", "textarea", "[contenteditable='true']"]:
                try:
                    els = driver.find_elements(By.CSS_SELECTOR, sel)
                    vis = [e for e in els if e.is_displayed()]
                    if vis:
                        box = vis[-1]
                        break
                except Exception:
                    pass
            if box is None:
                raise RuntimeError("Không tìm thấy ô nhập prompt. Website có thể đã đổi giao diện.")
            box.click()
            try:
                box.send_keys(text)
            except Exception:
                driver.execute_script("arguments[0].innerText = arguments[1]", box, text)
            box.send_keys(Keys.ENTER)

        answers: List[str] = []
        send_prompt(prompt)
        for p in range(1, max(1, passes) + 1):
            if p > 1:
                follow = "Kiểm tra lại toàn bộ SRT vừa tạo, sửa timeline và nội dung cho khớp video hơn. Chỉ trả về SRT hoàn chỉnh, không giải thích."
                if p == 3:
                    follow = "Rà soát lần 3: kiểm tra cảnh, tên nhân vật, mốc thời gian và độ dài câu. Chỉ trả về SRT hoàn chỉnh đã sửa."
                elif p >= 4:
                    follow = "Rà soát cuối cùng: loại câu bịa/trùng, cân timeline và xuất SRT cuối. Chỉ trả về SRT."
                send_prompt(follow)
            start = time.time()
            best = ""
            stable = 0
            last_len = 0
            while time.time() - start < wait_seconds:
                time.sleep(3)
                txt = _last_response_text(driver, provider)
                if len(txt) > len(best):
                    best = txt
                if len(best) == last_len and len(best) > 100:
                    stable += 1
                else:
                    stable = 0
                    last_len = len(best)
                if stable >= 4 and "-->" in best:
                    break
            if "-->" not in best:
                raise RuntimeError("Web AI chưa trả về SRT hợp lệ trước khi hết thời gian chờ.")
            answers.append(_strip_fence(best))
            log(f"Web AI pass {p}/{passes}: nhận {len(parse_srt(answers[-1]))} block SRT")
        return max(answers, key=lambda x: len(parse_srt(x)))
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def web_ai_srt_chunked(video_path: str, provider: str, language: str, note: str, density: str, wait_seconds: int, profile_dir: str | None, chunk_minutes: int, log: LogFn = print, passes: int = 1, ui_mode: str = "Tự động") -> str:
    total = duration(video_path)
    if total <= chunk_minutes * 60 + 2:
        return web_ai_srt(video_path, provider, language, note, density, wait_seconds, profile_dir, log, passes, ui_mode)
    tmp = Path(tempfile.mkdtemp(prefix="recap_web_chunks_"))
    try:
        chunks = split_for_web(video_path, chunk_minutes, str(tmp), log)
        merged: List[str] = []
        offset = 0.0
        for i, c in enumerate(chunks, 1):
            log(f"Web AI chunk {i}/{len(chunks)}")
            txt = web_ai_srt(c, provider, language, note, density, wait_seconds, profile_dir, log, passes, ui_mode)
            merged.append(shift_srt(txt, offset))
            offset += duration(c)
        return "\n\n".join(merged)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def _edge_save(text: str, voice: str, path: str, rate: str = "+0%") -> None:
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def _fit_and_delay(src_audio: str, out_wav: str, st: float, en: float) -> None:
    ffmpeg = find_bin("ffmpeg")
    target = max(0.25, en - st)
    actual = max(0.05, duration(src_audio))
    ratio = actual / target
    filters: List[str] = []
    while ratio > 2.0:
        filters.append("atempo=2.0")
        ratio /= 2.0
    while ratio < 0.5:
        filters.append("atempo=0.5")
        ratio /= 0.5
    filters.append(f"atempo={ratio:.5f}")
    delay = int(st * 1000)
    af = ",".join(filters) + f",adelay={delay}|{delay}"
    subprocess.run([ffmpeg, "-y", "-i", src_audio, "-af", af, "-ac", "2", "-ar", "44100", out_wav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=(0x08000000 if os.name == "nt" else 0), check=True)


def _mix_wavs(clips: List[Path], wav_path: str, log: LogFn) -> None:
    if not clips:
        raise ValueError("Không có audio để ghép")
    ffmpeg = find_bin("ffmpeg")
    cmd = [ffmpeg, "-y"]
    for c in clips:
        cmd += ["-i", str(c)]
    cmd += ["-filter_complex", f"amix=inputs={len(clips)}:normalize=0:dropout_transition=0", "-ac", "2", "-ar", "44100", wav_path]
    run(cmd, log)


def srt_to_wav_edge(srt_path: str, wav_path: str, voice: str, log: LogFn = print) -> None:
    items = parse_srt(Path(srt_path).read_text(encoding="utf-8-sig"))
    if not items:
        raise ValueError("SRT không có câu hợp lệ")
    tmp = Path(tempfile.mkdtemp(prefix="recap_edge_"))
    clips: List[Path] = []
    try:
        for i, (st, en, text) in enumerate(items):
            mp3 = tmp / f"tts_{i:05}.mp3"
            wav = tmp / f"tts_{i:05}.wav"
            log(f"Edge TTS {i + 1}/{len(items)}: {text[:70]}")
            asyncio.run(_edge_save(text, voice, str(mp3)))
            _fit_and_delay(str(mp3), str(wav), st, en)
            clips.append(wav)
        _mix_wavs(clips, wav_path, log)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def list_piper_models() -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for p in sorted(voices_dir().glob("*.onnx")):
        cfg = Path(str(p) + ".json")
        if cfg.exists():
            out.append((p.stem, str(p)))
    return out


def srt_to_wav_piper(srt_path: str, wav_path: str, model_path: str, log: LogFn = print) -> None:
    piper = find_bin("piper")
    items = parse_srt(Path(srt_path).read_text(encoding="utf-8-sig"))
    if not items:
        raise ValueError("SRT không có câu hợp lệ")
    model = Path(model_path)
    if not model.exists():
        raise FileNotFoundError("Không tìm thấy model Piper .onnx")
    cfg = Path(str(model) + ".json")
    if not cfg.exists():
        raise FileNotFoundError("Thiếu file cấu hình .onnx.json đi kèm model Piper")
    tmp = Path(tempfile.mkdtemp(prefix="recap_piper_"))
    clips: List[Path] = []
    try:
        for i, (st, en, text) in enumerate(items):
            raw = tmp / f"raw_{i:05}.wav"
            delayed = tmp / f"tts_{i:05}.wav"
            log(f"Piper {i + 1}/{len(items)}: {text[:70]}")
            cp = subprocess.run([piper, "--model", str(model), "--config", str(cfg), "--output_file", str(raw)], input=text + "\n", text=True, encoding="utf-8", capture_output=True, creationflags=(0x08000000 if os.name == "nt" else 0))
            if cp.returncode != 0 or not raw.exists():
                raise RuntimeError("Piper lỗi: " + (cp.stderr or cp.stdout or f"mã {cp.returncode}")[-1000:])
            _fit_and_delay(str(raw), str(delayed), st, en)
            clips.append(delayed)
        _mix_wavs(clips, wav_path, log)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _tiktok_one(text: str, voice: str, sessionid: str, out_mp3: str) -> None:
    url = "https://api16-normal-c-useast1a.tiktokv.com/media/api/text/speech/invoke/"
    headers = {
        "User-Agent": "com.zhiliaoapp.musically/2022600030 (Linux; U; Android 12)",
        "Cookie": f"sessionid={sessionid}",
    }
    r = requests.post(url, params={"text_speaker": voice, "req_text": text, "speaker_map_type": "0", "aid": "1233"}, headers=headers, timeout=60)
    r.raise_for_status()
    data = r.json()
    v = (data.get("data") or {}).get("v_str")
    if not v:
        raise RuntimeError("TikTok TTS không trả audio: " + str(data)[:600])
    Path(out_mp3).write_bytes(base64.b64decode(v))


def srt_to_wav_tiktok(srt_path: str, wav_path: str, voice: str, sessionid: str, log: LogFn = print) -> None:
    if not sessionid.strip():
        raise ValueError("Chưa nhập TikTok session ID")
    items = parse_srt(Path(srt_path).read_text(encoding="utf-8-sig"))
    if not items:
        raise ValueError("SRT không có câu hợp lệ")
    tmp = Path(tempfile.mkdtemp(prefix="recap_tiktok_"))
    clips: List[Path] = []
    try:
        for i, (st, en, text) in enumerate(items):
            mp3 = tmp / f"tts_{i:05}.mp3"
            wav = tmp / f"tts_{i:05}.wav"
            log(f"TikTok/CapCut TTS {i + 1}/{len(items)}: {text[:70]}")
            _tiktok_one(text, voice, sessionid, str(mp3))
            _fit_and_delay(str(mp3), str(wav), st, en)
            clips.append(wav)
        _mix_wavs(clips, wav_path, log)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def xtts_ready() -> Tuple[bool, str]:
    py = app_dir() / "voice_clone_env" / "Scripts" / "python.exe"
    worker = app_dir() / "voice_clone_worker.py"
    if not py.exists():
        return False, "Chưa cài môi trường Voice Clone XTTS. Chạy INSTALL-VOICE-CLONE.bat một lần."
    if not worker.exists():
        return False, "Thiếu voice_clone_worker.py"
    return True, "OK"


def srt_to_wav_xtts(srt_path: str, wav_path: str, sample_audio: str, language_name: str, log: LogFn = print) -> None:
    ok, msg = xtts_ready()
    if not ok:
        raise RuntimeError(msg)
    if not Path(sample_audio).exists():
        raise FileNotFoundError("Chưa chọn audio giọng mẫu")
    py = app_dir() / "voice_clone_env" / "Scripts" / "python.exe"
    worker = app_dir() / "voice_clone_worker.py"
    lang = XTTS_LANG.get(language_name, "vi")
    run([str(py), str(worker), "--srt", srt_path, "--sample", sample_audio, "--out", wav_path, "--language", lang, "--ffmpeg", find_bin("ffmpeg")], log, cwd=str(app_dir()))


def mix_video_audio(video_path: str, wav_path: str, output_path: str, keep_original: bool = True, original_volume: float = 0.12, log: LogFn = print) -> None:
    ffmpeg = find_bin("ffmpeg")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if keep_original:
        fc = f"[0:a]volume={original_volume}[a0];[a0][1:a]amix=inputs=2:duration=first:normalize=0[a]"
        run([ffmpeg, "-y", "-i", video_path, "-i", wav_path, "-filter_complex", fc, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output_path], log)
    else:
        run([ffmpeg, "-y", "-i", video_path, "-i", wav_path, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output_path], log)
