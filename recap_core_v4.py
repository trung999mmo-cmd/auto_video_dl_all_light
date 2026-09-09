from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import List

import recap_core_v2 as base
from recap_core_v2 import Segment

# Giữ Chrome mở để người dùng kiểm tra kết quả sau khi tool đọc xong SRT.
_OPEN_WEB_DRIVERS = []

LANG_PROMPT = {
    "Tiếng Việt": "tiếng Việt",
    "English": "tiếng Anh",
    "日本語": "tiếng Nhật",
    "한국어": "tiếng Hàn",
    "中文": "tiếng Trung",
    "ไทย": "tiếng Thái",
    "Français": "tiếng Pháp",
    "Deutsch": "tiếng Đức",
    "Español": "tiếng Tây Ban Nha",
    "Indonesia": "tiếng Indonesia",
    "Português": "tiếng Bồ Đào Nha",
    "Italiano": "tiếng Ý",
    "Русский": "tiếng Nga",
    "العربية": "tiếng Ả Rập",
    "हिन्दी": "tiếng Hindi",
}


def _lang_name(language: str) -> str:
    return LANG_PROMPT.get(language, language or "tiếng Việt")


def output_duration(segs: List[Segment]) -> float:
    return segs[-1].out_end if segs else 0.0


def build_recap_prompt(keep_sec: float, drop_sec: float, language: str, density: str, note: str = "") -> str:
    lang = _lang_name(language)
    keep = f"{keep_sec:g}"
    drop = f"{drop_sec:g}"
    density_extra = {
        "Ít chữ": "Ưu tiên câu gọn ở nửa dưới khoảng từ quy định.",
        "Vừa": "Giữ độ dài câu cân bằng, tự nhiên như người kể recap.",
        "Nhiều chữ": "Ưu tiên câu đầy ý ở nửa trên khoảng từ quy định, nhưng không nhồi chữ.",
    }.get(density, "")
    note_line = f"\nGhi chú riêng của người dùng: {note.strip()}" if note and note.strip() else ""
    return f"""Bạn là trợ lý chuyên tạo file SRT tóm tắt phim theo ngôn ngữ đầu ra đã chọn từ video gốc người dùng gửi lên.

Nhiệm vụ lần này:
- Lấy {keep} giây, bỏ {drop} giây, lặp đến hết video.
- Timestamp SRT phải theo timeline video sau khi cắt, không dùng mốc thời gian video gốc.
- Hãy tự tính các đoạn được giữ lại theo đúng quy tắc trên, không tua nhanh, không gom nhiều đoạn cắt vào một block.
- Mỗi block phải bám đúng khung thời gian của đoạn output tương ứng. Nếu lấy {keep} giây thì block thường dài {keep} giây; đoạn cuối có thể ngắn hơn nếu video hết.
- Không cần đếm hay ép số lượng block trước; ưu tiên tính đúng timeline và bao phủ đúng các đoạn được giữ lại.
- Ngôn ngữ đầu ra bắt buộc: {lang}. Toàn bộ caption SRT phải viết bằng {lang}, không tự động quay về tiếng Việt nếu người dùng đã chọn ngôn ngữ khác.

Mục tiêu quan trọng nhất:
Tạo SRT sao cho mỗi block là một câu tóm tắt ngắn gọn theo ngôn ngữ đầu ra, khớp với nội dung đoạn video đang chạy, nhưng không dừng ở mức mô tả cảnh. Câu phải được viết như một mắt xích trong bản tóm tắt cốt truyện liền mạch của cả phim.

Mỗi block phải đạt cùng lúc 3 điều:
1. Đúng cảnh đang chạy: bám hành động, biểu cảm, tình huống, chi tiết quan trọng đang xuất hiện.
2. Phục vụ cốt truyện: giúp người xem hiểu cảnh này có ý nghĩa gì, đẩy mạch phim đi đâu, nối với cảnh trước và sau thế nào.
3. Liền mạch như recap: đọc liên tiếp các block phải thấy câu chuyện chạy rõ ràng, không phải danh sách mô tả từng cảnh.

Cách viết bắt buộc:
- Mỗi block chỉ viết 1 câu ngắn.
- Số lượng từ phải phụ thuộc vào độ dài mỗi đoạn được giữ lại: mỗi câu khoảng 7-12 chữ với đoạn khoảng 3 giây; nếu đoạn ngắn hơn thì giảm vừa phải, nếu dài hơn thì câu đầy ý hơn.
- Nếu thời lượng lấy dài hơn, câu phải đủ ý hơn, kể rõ hơn; không viết quá ngắn làm SRT bị cụt lủn.
- Viết theo ngôn ngữ đầu ra tự nhiên, gọn, rõ, có nhịp recap phim.
- Giọng văn phải giống người làm recap hơn: ưu tiên ý nghĩa của cảnh và mạch chuyện, tránh văn mẫu máy móc, tránh lặp một kiểu mở đầu quá nhiều.
- Mạch câu phải liền mạch: không viết mỗi block như một câu độc lập rời rạc. Mỗi block vẫn chỉ là 1 câu, nhưng phải có cảm giác nối tiếp block trước và chuẩn bị cho block sau.
- Ưu tiên cách viết như một đoạn recap liền mạch bị chia nhỏ theo timestamp, không phải danh sách chú thích từng cảnh.
- Có thể dùng chủ ngữ nối tiếp, từ nối nhẹ, hoặc nhắc lại ý đang dang dở một cách tự nhiên.
- Không bắt buộc mỗi block phải là một câu đơn đóng kín nghe cụt. Nếu mạch truyện cần, có thể viết block như một mệnh đề hoặc một phần của câu ghép nối tự nhiên với block liền trước hoặc liền sau, miễn block đó vẫn khớp đúng hình ở timestamp hiện tại.
- Có thể để một câu hoàn chỉnh kéo qua 2 block liên tiếp, nhưng không vắt câu quá 3 block.
- Tránh chấm câu cứng ở mọi block nếu làm lời đọc bị đứt mạch; ưu tiên cảm giác một người đang kể recap liên tục.
- Có thể dùng từ nối như “nhưng rồi”, “nào ngờ”, “chưa kịp”, “đúng lúc đó”, “ai ngờ”, “từ đây” nếu cần, nhưng dùng tiết chế.
- Hình ảnh là điểm neo, cốt truyện mới là trọng tâm câu viết.
- {density_extra}

Tuyệt đối không làm:
- Không chỉ mô tả cảnh kiểu “anh ta đi vào phòng”, “cô ấy quay đầu lại”, “người đàn ông ngồi xuống ghế” nếu câu đó không đẩy mạch truyện.
- Không kể sang nội dung chưa xuất hiện trong đoạn tương ứng.
- Không bịa.
- Không thêm tiêu đề, nhận xét, giải thích hoặc markdown.

Tự kiểm tra trước khi trả lời:
- SRT có bao phủ đủ các đoạn được giữ lại theo quy tắc lấy/bỏ không?
- Mỗi block có khớp đúng đoạn hình đang chạy không?
- Câu có chỉ là mô tả cảnh không? Nếu có, viết lại theo hướng kể cốt truyện.
- Các block có nối được với nhau thành một bản recap liền mạch không?
- Timestamp có chạy liên tục theo video sau khi cắt không?

Định dạng đầu ra:
Chỉ xuất SRT thuần, không thêm bất cứ nội dung nào ngoài SRT.

Ví dụ định dạng:
1
00:00:00,000 --> 00:00:{keep_sec:02.0f},000
[Nội dung]

2
00:00:{keep_sec:02.0f},000 --> 00:00:{keep_sec*2:02.0f},000
[Nội dung]{note_line}"""


def force_exact_timeline(srt_text: str, segs: List[Segment]) -> str:
    blocks = base.parse_srt(base._strip_fence(srt_text))
    if len(blocks) != len(segs):
        raise ValueError(f"SRT trả về {len(blocks)} block, cần đúng {len(segs)} block")
    rows = []
    for i, (seg, (_, _, body)) in enumerate(zip(segs, blocks), 1):
        rows.extend([str(i), f"{base.fmt_srt(seg.out_start)} --> {base.fmt_srt(seg.out_end)}", body.strip(), ""])
    return "\n".join(rows).strip() + "\n"


def mapping_hint(segs: List[Segment]) -> str:
    rows = []
    for i, s in enumerate(segs, 1):
        rows.append(
            f"{i}: video gốc {base.fmt_srt(s.src_start)} -> {base.fmt_srt(s.src_end)} | "
            f"output {base.fmt_srt(s.out_start)} -> {base.fmt_srt(s.out_end)}"
        )
    return "\n".join(rows)


def _chrome_version(chrome: str | None) -> int | None:
    if not chrome:
        return None
    try:
        out = subprocess.check_output([chrome, "--version"], text=True, stderr=subprocess.STDOUT, creationflags=(0x08000000 if os.name == "nt" else 0))
        m = re.search(r"(\d+)\.", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def _find_chrome() -> str | None:
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


def open_automation_driver(profile_dir: str | None, log=print):
    chrome = _find_chrome()
    major = _chrome_version(chrome)
    if major:
        log(f"INFO: Chrome version: {major}")
    profile = str(Path(profile_dir or (base.app_dir() / "chrome_web_profile")).resolve())
    Path(profile).mkdir(parents=True, exist_ok=True)

    # Ưu tiên undetected-chromedriver giống luồng tool mẫu; nếu không chạy được thì fallback Selenium Manager.
    try:
        import undetected_chromedriver as uc
        log("INFO: Dung undetected-chromedriver")
        opts = uc.ChromeOptions()
        opts.add_argument("--start-maximized")
        opts.add_argument(f"--user-data-dir={profile}")
        kwargs = {"options": opts, "use_subprocess": True}
        if major:
            kwargs["version_main"] = major
        driver = uc.Chrome(**kwargs)
        log("INFO: Chrome da mo bang undetected-chromedriver.")
        return driver
    except Exception as e:
        log(f"INFO: undetected-chromedriver khong dung duoc, fallback Selenium: {e}")

    from selenium import webdriver
    opts = webdriver.ChromeOptions()
    opts.add_argument("--start-maximized")
    opts.add_argument(f"--user-data-dir={profile}")
    try:
        opts.add_experimental_option("detach", True)
    except Exception:
        pass
    if chrome:
        opts.binary_location = chrome
    driver = webdriver.Chrome(options=opts)
    log("INFO: Chrome da mo bang Selenium Manager.")
    return driver


def _assistant_elements(driver, provider: str):
    from selenium.webdriver.common.by import By
    if provider.lower().startswith("chatgpt"):
        selectors = [
            "[data-message-author-role='assistant']",
            "article[data-turn='assistant']",
            "article",
        ]
    else:
        selectors = [
            "message-content",
            ".model-response-text",
            "[data-test-id='model-response']",
        ]
    best = []
    for sel in selectors:
        try:
            els = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
            if len(els) > len(best):
                best = els
        except Exception:
            pass
    return best


def _find_upload_input(driver, timeout: int = 60):
    from selenium.webdriver.common.by import By
    end = time.time() + timeout
    while time.time() < end:
        try:
            ins = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if ins:
                return ins[-1]
        except Exception:
            pass
        # thử mở menu đính kèm
        for sel in [
            "button[aria-label*='Attach']", "button[aria-label*='Đính']", "button[aria-label*='Upload']",
            "button[aria-label*='Tải']", "button[data-testid*='attach']",
        ]:
            try:
                btns = driver.find_elements(By.CSS_SELECTOR, sel)
                if btns:
                    btns[-1].click()
                    time.sleep(1)
            except Exception:
                pass
        time.sleep(1)
    return None


def _find_prompt_box(driver):
    from selenium.webdriver.common.by import By
    selectors = [
        "#prompt-textarea",
        "div[contenteditable='true'][data-virtualkeyboard='true']",
        "textarea",
        "div[contenteditable='true']",
    ]
    for sel in selectors:
        try:
            els = [e for e in driver.find_elements(By.CSS_SELECTOR, sel) if e.is_displayed()]
            if els:
                return els[-1]
        except Exception:
            pass
    return None


def _submit_prompt(driver, prompt: str, log=print):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    box = _find_prompt_box(driver)
    if box is None:
        raise RuntimeError("Không tìm thấy ô nhập prompt trên Web AI")
    box.click()
    try:
        box.send_keys(prompt)
    except Exception:
        driver.execute_script("arguments[0].focus(); arguments[0].innerText = arguments[1]; arguments[0].dispatchEvent(new InputEvent('input',{bubbles:true,inputType:'insertText',data:arguments[1]}));", box, prompt)
    time.sleep(1)

    for sel in [
        "button[data-testid='send-button']",
        "button[aria-label='Send prompt']",
        "button[aria-label*='Send']",
        "button[aria-label*='Gửi']",
        "button[aria-label*='Submit']",
    ]:
        try:
            btns = [b for b in driver.find_elements(By.CSS_SELECTOR, sel) if b.is_displayed() and b.is_enabled()]
            if btns:
                btns[-1].click()
                log("INFO: Da gui prompt len Web AI: SUBMIT_VERIFIED:BUTTON")
                return
        except Exception:
            pass
    box.send_keys(Keys.ENTER)
    log("INFO: Da gui prompt len Web AI: SUBMIT_VERIFIED:ENTER")


def _wait_new_response(driver, provider: str, before_count: int, wait_seconds: int, log=print) -> str:
    start = time.time()
    best = ""
    last_len = 0
    stable = 0
    last_log = 0
    while time.time() - start < wait_seconds:
        time.sleep(3)
        els = _assistant_elements(driver, provider)
        if len(els) > before_count:
            try:
                txt = (els[-1].text or "").strip()
            except Exception:
                txt = ""
            if len(txt) >= len(best):
                best = txt
        elapsed = int(time.time() - start)
        if len(best) == last_len and len(best) > 80:
            stable += 1
        else:
            stable = 0
            last_len = len(best)
        if elapsed - last_log >= 30:
            if best:
                log(f"INFO: ... Web AI van dang xu ly: {elapsed}s, {len(best)} ky tu")
            else:
                log(f"INFO: ... Chua thay response moi cua Web AI, tiep tuc cho: {elapsed}s")
            last_log = elapsed
        if stable >= 4 and "-->" in best:
            log(f"INFO: Web AI response dung yen du lau, doc ket qua hien co: {elapsed}s, {len(best)} ky tu")
            break
    if not best:
        raise RuntimeError("Không đọc được response mới từ Web AI trước khi hết thời gian chờ")
    log(f"INFO: Doc duoc response Web AI: {len(best)} ky tu")
    return base._strip_fence(best)


def web_ai_srt_mapped(video_path: str, provider: str, language: str, keep_sec: float, drop_sec: float,
                      density: str, note: str, wait_seconds: int, profile_dir: str | None,
                      segs: List[Segment], log=print, passes: int = 1, keep_chrome_open: bool = True) -> str:
    url = "https://chatgpt.com/" if provider.lower().startswith("chatgpt") else "https://gemini.google.com/"
    log(f"INFO: {provider} web video: {video_path}")
    log(f"INFO: {provider} web mapping: {len(segs)} block, duration={base.duration(video_path):.3f}s")
    size_mb = Path(video_path).stat().st_size / 1024 / 1024
    log(f"INFO: {provider} upload: file {size_mb:.1f}MB")
    log("INFO: Dang mo Chrome...")
    driver = open_automation_driver(profile_dir, log)
    try:
        log(f"INFO: Dang vao: {url}...")
        driver.get(url)
        log(f"INFO: Chrome da vao trang {provider}.")
        # Cho profile đăng nhập/website ổn định. Nếu chưa đăng nhập người dùng có thể đăng nhập ngay trong cửa sổ này.
        log(f"INFO: Chrome da mo. Neu chua dang nhap {provider}, hay dang nhap ngay trong cua so Chrome.")
        time.sleep(8)

        file_input = None
        for attempt in range(1, 4):
            log(f"INFO: Thu upload file {provider} lan {attempt}/3.")
            file_input = _find_upload_input(driver, 25)
            if file_input is not None:
                try:
                    file_input.send_keys(str(Path(video_path).resolve()))
                    log(f"INFO: {provider} da nhan file qua input web.")
                    break
                except Exception as e:
                    log(f"INFO: Upload lan {attempt} loi: {e}")
                    file_input = None
            time.sleep(2)
        if file_input is None:
            raise RuntimeError(f"Không tìm thấy/không dùng được ô upload video trên {provider}")

        log(f"INFO: {provider} upload file: {Path(video_path).name}")
        # Tool mẫu chờ cố định để upload xong trước khi gõ prompt.
        for sec in range(10, 61, 10):
            time.sleep(10)
            if sec in (30, 60):
                log(f"INFO: Dang cho {provider} on dinh sau upload: {sec}s/60s.")
        log(f"INFO: {provider} da cho xong 60s sau upload, bat dau dien prompt.")

        prompt = build_recap_prompt(keep_sec, drop_sec, language, density, note)
        before = len(_assistant_elements(driver, provider))
        _submit_prompt(driver, prompt, log)
        answer = _wait_new_response(driver, provider, before, wait_seconds, log)

        expected = len(segs)
        got = len(base.parse_srt(answer))
        log(f"INFO: SRT nhap tu video goc: {got}/{expected} block.")
        if got != expected:
            # Một vòng sửa tự động, cung cấp map chính xác để không phải đoán lại timestamp.
            fix = f"""SRT vừa rồi có {got} block nhưng cần đúng {expected} block. Hãy sửa lại, chỉ xuất SRT thuần.
Đây là mapping do tool đã tính chính xác; mỗi dòng phải có đúng một block và nội dung phải bám cảnh video gốc tương ứng:
{mapping_hint(segs)}
Giữ văn phong recap liền mạch, không bịa."""
            before = len(_assistant_elements(driver, provider))
            _submit_prompt(driver, fix, log)
            answer = _wait_new_response(driver, provider, before, wait_seconds, log)
            got = len(base.parse_srt(answer))
            log(f"INFO: Sau sua mapping: {got}/{expected} block.")

        exact = force_exact_timeline(answer, segs)
        log(f"INFO: SRT nhap tu video goc da du block: {expected}/{expected}. Timeline da khoa theo video sau cat.")

        # Các pass sau dùng cùng cuộc chat để rà lại nội dung, nhưng luôn khóa timeline lại ở phía tool.
        for p in range(2, max(1, passes) + 1):
            follow = "Kiểm tra lại toàn bộ SRT vừa tạo, sửa nội dung cho bám cảnh và liền mạch như recap hơn. Không thay đổi số block. Chỉ trả về SRT thuần."
            if p == 3:
                follow = "Rà soát lần 3: sửa câu máy móc/lặp, tên nhân vật, ý nghĩa cảnh và mạch nối. Giữ đúng số block. Chỉ trả về SRT."
            elif p >= 4:
                follow = "Rà soát cuối: loại câu bịa/trùng, làm lời kể tự nhiên và liên tục. Giữ đúng số block. Chỉ trả về SRT."
            before = len(_assistant_elements(driver, provider))
            _submit_prompt(driver, follow, log)
            candidate = _wait_new_response(driver, provider, before, wait_seconds, log)
            try:
                exact = force_exact_timeline(candidate, segs)
                log(f"INFO: Web AI pass {p}/{passes}: hop le {len(segs)}/{len(segs)} block")
            except Exception as e:
                log(f"INFO: Pass {p} khong hop le, giu ket qua pass truoc: {e}")

        try:
            log(f"INFO: Khoa chat Web AI: {driver.current_url}")
        except Exception:
            pass
        if keep_chrome_open:
            _OPEN_WEB_DRIVERS.append(driver)
            log(f"INFO: Giu Chrome mo de ban kiem tra ket qua {provider}.")
            driver = None
        return exact
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def _make_chunk(video_path: str, start: float, end: float, out_path: str, log=print):
    ffmpeg = base.find_bin("ffmpeg")
    cmd = [ffmpeg, "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", video_path,
           "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path]
    base.run(cmd, log)


def web_ai_srt_mapped_chunked(video_path: str, provider: str, language: str, keep_sec: float, drop_sec: float,
                              density: str, note: str, wait_seconds: int, profile_dir: str | None,
                              chunk_minutes: int, log=print, passes: int = 1) -> str:
    total = base.duration(video_path)
    all_segs = base.build_segments(total, keep_sec, drop_sec)
    if total <= chunk_minutes * 60 + 1:
        return web_ai_srt_mapped(video_path, provider, language, keep_sec, drop_sec, density, note,
                                 wait_seconds, profile_dir, all_segs, log, passes, True)

    # Chia đúng biên chu kỳ giữ+bỏ để pattern trong mỗi chunk không bị lệch.
    cycle = keep_sec + drop_sec
    cycles_per_chunk = max(1, int((chunk_minutes * 60) // cycle))
    chunk_span = cycles_per_chunk * cycle
    tmp = Path(tempfile.mkdtemp(prefix="recap_web_mapped_chunks_"))
    merged_parts = []
    out_offset = 0.0
    try:
        start = 0.0
        idx = 0
        while start < total - 0.02:
            idx += 1
            end = min(total, start + chunk_span)
            chunk = tmp / f"chunk_{idx:03}.mp4"
            log(f"INFO: Web AI chunk {idx}: source {start:.1f}s -> {end:.1f}s")
            _make_chunk(video_path, start, end, str(chunk), log)
            local_total = end - start
            local_segs = base.build_segments(local_total, keep_sec, drop_sec)
            txt = web_ai_srt_mapped(str(chunk), provider, language, keep_sec, drop_sec, density, note,
                                    wait_seconds, profile_dir, local_segs, log, passes, False)
            merged_parts.append(base.shift_srt(txt, out_offset))
            out_offset += output_duration(local_segs)
            start = end
        # Sau các chunk, mở lại trang cuối cho người dùng kiểm tra không bắt buộc; các driver chunk đã đóng để tránh khóa profile.
        return "\n\n".join(x.strip() for x in merged_parts if x.strip()) + "\n"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def gemini_api_srt_mapped(video_path: str, api_key: str, model: str, language: str,
                          keep_sec: float, drop_sec: float, density: str, note: str,
                          segs: List[Segment], log=print) -> str:
    import google.generativeai as genai
    genai.configure(api_key=api_key.strip())
    log("INFO: Dang upload video goc len Gemini API...")
    f = genai.upload_file(video_path)
    while getattr(f, "state", None) and getattr(f.state, "name", "") == "PROCESSING":
        time.sleep(3)
        f = genai.get_file(f.name)
        log("INFO: Gemini API dang xu ly video...")
    if getattr(getattr(f, "state", None), "name", "") == "FAILED":
        raise RuntimeError("Gemini API xử lý file thất bại")
    gm = genai.GenerativeModel(model)
    prompt = build_recap_prompt(keep_sec, drop_sec, language, density, note)
    answer = base._strip_fence(gm.generate_content([f, prompt], request_options={"timeout": 1800}).text)
    if len(base.parse_srt(answer)) != len(segs):
        fix = f"""Sửa lại SRT vừa tạo thành đúng {len(segs)} block theo mapping sau. Chỉ trả về SRT thuần:\n{mapping_hint(segs)}"""
        answer = base._strip_fence(gm.generate_content([f, answer, fix], request_options={"timeout": 1800}).text)
    return force_exact_timeline(answer, segs)
