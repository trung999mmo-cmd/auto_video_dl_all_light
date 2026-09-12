from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import List

import recap_core_v2 as base
import recap_core_v4 as v4
from recap_core_v2 import Segment

_OPEN_DRIVERS = []


def _chrome_exe() -> str | None:
    return v4._find_chrome()


def _debug_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as r:
            return r.status == 200
    except Exception:
        return False


def _port_busy(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def _port_file(profile_dir: str | Path) -> Path:
    return Path(profile_dir) / ".video_recap_debug_port"


def _choose_debug_port(profile_dir: str | Path) -> int:
    pf = _port_file(profile_dir)
    try:
        saved = int(pf.read_text(encoding="utf-8").strip())
        if _debug_ready(saved) or not _port_busy(saved):
            return saved
    except Exception:
        pass
    for port in range(9229, 9250):
        if _debug_ready(port) or not _port_busy(port):
            try:
                Path(profile_dir).mkdir(parents=True, exist_ok=True)
                pf.write_text(str(port), encoding="utf-8")
            except Exception:
                pass
            return port
    raise RuntimeError("Không tìm được cổng Chrome riêng cho tool")


def open_tool_browser(profile_dir: str, url: str, log=print) -> int:
    """Open/reuse exactly one dedicated Chrome profile for the tool.

    The browser can stay open. Later Selenium attaches to the same running Chrome
    through remote debugging instead of starting another profile/window.
    """
    chrome = _chrome_exe()
    if not chrome:
        raise FileNotFoundError("Không tìm thấy Google Chrome trên máy")

    profile = str(Path(profile_dir).resolve())
    Path(profile).mkdir(parents=True, exist_ok=True)
    port = _choose_debug_port(profile)
    args = [
        chrome,
        f"--user-data-dir={profile}",
        "--profile-directory=Default",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=ProfilePickerOnStartup",
        "--start-maximized",
        "--new-window",
        url,
    ]

    if _debug_ready(port):
        # Same profile/browser is already alive; this command only opens the URL
        # in that existing dedicated Chrome process.
        subprocess.Popen(args, creationflags=(0x08000000 if os.name == "nt" else 0))
        log(f"INFO: Dung lai Chrome rieng cua tool, profile Default, port {port}.")
        return port

    log(f"INFO: Mo Chrome rieng cua tool, profile Default, port {port}...")
    subprocess.Popen(args, creationflags=(0x08000000 if os.name == "nt" else 0))
    end = time.time() + 25
    while time.time() < end:
        if _debug_ready(port):
            log("INFO: Chrome rieng da san sang. Lan sau tool se dung lai dung Chrome nay.")
            return port
        time.sleep(0.5)
    raise RuntimeError("Chrome riêng đã mở nhưng không bật được cổng điều khiển. Hãy đóng Chrome riêng rồi thử lại.")


def open_automation_driver(profile_dir: str | None, log=print):
    """Attach Selenium Manager to the already-running dedicated Chrome.

    No undetected-chromedriver here: that was the source of the Chrome 153 vs 152
    mismatch. Selenium Manager resolves the driver for the installed Chrome.
    """
    from selenium import webdriver

    profile = str(Path(profile_dir or (base.app_dir() / "chrome_web_profile")).resolve())
    port = open_tool_browser(profile, "https://chatgpt.com/", log)
    opts = webdriver.ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    chrome = _chrome_exe()
    if chrome:
        opts.binary_location = chrome
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        raise RuntimeError(
            "Không bám được vào Chrome riêng của tool. Đóng cửa sổ Chrome riêng rồi bấm chạy lại. "
            f"Chi tiết: {e}"
        ) from e
    log("INFO: Selenium da bam vao DUNG Chrome rieng dang mo; khong tao profile moi.")
    _OPEN_DRIVERS.append(driver)
    return driver


def _composer_text(box) -> str:
    try:
        val = box.get_attribute("value")
        if val:
            return val
    except Exception:
        pass
    for attr in ("innerText", "textContent"):
        try:
            val = box.get_attribute(attr)
            if val:
                return val
        except Exception:
            pass
    try:
        return box.text or ""
    except Exception:
        return ""


def _find_prompt_box_wait(driver, timeout: int = 90):
    from selenium.webdriver.common.by import By

    selectors = [
        "#prompt-textarea",
        "div#prompt-textarea[contenteditable='true']",
        "div.ProseMirror[contenteditable='true']",
        "div[contenteditable='true'][data-lexical-editor='true']",
        "div[contenteditable='true'][data-virtualkeyboard='true']",
        "textarea",
        "div[contenteditable='true']",
    ]
    end = time.time() + timeout
    while time.time() < end:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass
        for sel in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in reversed(els):
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                pass
        time.sleep(1)
    return None


def _fill_prompt_all_at_once(driver, prompt: str, log=print):
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    box = _find_prompt_box_wait(driver, 90)
    if box is None:
        raise RuntimeError(
            "Không tìm thấy ô nhập prompt sau 90 giây. Nếu ChatGPT đang ở màn hình đăng nhập, hãy đăng nhập trong Chrome riêng rồi chạy lại."
        )
    box.click()

    script = r"""
const el = arguments[0];
const text = arguments[1];
el.focus();
function fire() {
  try { el.dispatchEvent(new InputEvent('beforeinput', {bubbles:true, inputType:'insertText', data:text})); } catch(e) {}
  try { el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text})); }
  catch(e) { el.dispatchEvent(new Event('input', {bubbles:true})); }
  el.dispatchEvent(new Event('change', {bubbles:true}));
}
if (el.tagName === 'TEXTAREA') {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
  setter.call(el, text); fire();
} else if (el.tagName === 'INPUT') {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  setter.call(el, text); fire();
} else {
  el.innerHTML = '';
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const p = document.createElement('p');
    if (lines[i].length) p.textContent = lines[i];
    else p.appendChild(document.createElement('br'));
    el.appendChild(p);
  }
  fire();
}
"""

    ok = False
    try:
        driver.execute_script(script, box, prompt)
        time.sleep(1)
        current = _composer_text(box)
        ok = len(current.strip()) >= max(20, int(len(prompt.strip()) * 0.80))
        if ok:
            log(f"INFO: Da dien DU prompt {len(current)} ky tu; VIDEO VAN DANG DINH KEM; CHUA GUI.")
    except Exception as e:
        log(f"INFO: DOM paste chua duoc, chuyen sang go an toan: {e}")

    if not ok:
        try:
            box.click()
            box.send_keys(Keys.CONTROL, "a")
            box.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        lines = prompt.split("\n")
        for i, line in enumerate(lines):
            if line:
                box.send_keys(line)
            if i != len(lines) - 1:
                ActionChains(driver).key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).perform()
        time.sleep(1)
        current = _composer_text(box)
        if len(current.strip()) < max(20, int(len(prompt.strip()) * 0.70)):
            raise RuntimeError(f"Prompt chưa đủ: {len(current)}/{len(prompt)} ký tự. Tool không gửi để tránh sai.")
        log(f"INFO: Da dien DU prompt bang go an toan: {len(current)} ky tu; CHUA GUI.")
    return box


def _user_message_count(driver) -> int:
    from selenium.webdriver.common.by import By
    best = 0
    for sel in ["[data-message-author-role='user']", "article[data-turn='user']"]:
        try:
            best = max(best, len(driver.find_elements(By.CSS_SELECTOR, sel)))
        except Exception:
            pass
    return best


def _click_send_once_and_verify(driver, box, log=print):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    before = _user_message_count(driver)
    clicked = False
    selectors = [
        "button[data-testid='send-button']",
        "button[data-testid='composer-submit-button']",
        "button[aria-label='Send prompt']",
        "button[aria-label*='Send message']",
        "button[aria-label*='Send']",
        "button[aria-label*='Gửi tin nhắn']",
        "button[aria-label*='Gửi']",
        "button[aria-label*='Submit']",
    ]
    end = time.time() + 20
    while time.time() < end and not clicked:
        for sel in selectors:
            try:
                btns = [b for b in driver.find_elements(By.CSS_SELECTOR, sel) if b.is_displayed() and b.is_enabled()]
                if btns:
                    btns[-1].click()
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            time.sleep(0.5)

    if not clicked:
        box.click()
        box.send_keys(Keys.ENTER)
        clicked = True

    # Verify that the composer was actually submitted. Never click twice here.
    verify_end = time.time() + 30
    while time.time() < verify_end:
        time.sleep(1)
        if _user_message_count(driver) > before:
            log("INFO: GUI THANH CONG 1 LAN: VIDEO + TOAN BO PROMPT CUNG MOT TIN NHAN.")
            return
        try:
            now_box = _find_prompt_box_wait(driver, 1)
            if now_box is not None and len(_composer_text(now_box).strip()) < 5:
                log("INFO: GUI THANH CONG 1 LAN: o prompt da rong sau submit.")
                return
        except Exception:
            pass
    raise RuntimeError("Đã bấm Gửi nhưng không xác nhận được tin nhắn đã được gửi. Tool dừng, không bấm gửi lần hai.")


def _submit_prompt(driver, prompt: str, log=print):
    box = _fill_prompt_all_at_once(driver, prompt, log)
    time.sleep(0.5)
    _click_send_once_and_verify(driver, box, log)


def web_ai_srt_mapped(video_path: str, provider: str, language: str, keep_sec: float, drop_sec: float,
                      density: str, note: str, wait_seconds: int, profile_dir: str | None,
                      segs: List[Segment], log=print, passes: int = 1, keep_chrome_open: bool = True) -> str:
    url = "https://chatgpt.com/" if provider.lower().startswith("chatgpt") else "https://gemini.google.com/"
    size_mb = Path(video_path).stat().st_size / 1024 / 1024
    log(f"INFO: Web AI bat dau | {provider} | {len(segs)} block | video {size_mb:.1f}MB")
    driver = open_automation_driver(profile_dir, log)
    try:
        driver.get(url)
        log(f"INFO: Da vao {provider} tren DUNG Chrome rieng cua tool.")
        time.sleep(5)

        file_input = None
        for attempt in range(1, 4):
            log(f"INFO: Tim o dinh kem video lan {attempt}/3...")
            file_input = v4._find_upload_input(driver, 30)
            if file_input is not None:
                try:
                    file_input.send_keys(str(Path(video_path).resolve()))
                    break
                except Exception as e:
                    log(f"INFO: Upload lan {attempt} loi: {e}")
                    file_input = None
            time.sleep(2)
        if file_input is None:
            raise RuntimeError(f"Không tìm thấy/không dùng được ô upload video trên {provider}")

        log(f"INFO: Da dinh kem video: {Path(video_path).name}")
        log("INFO: CHUA GUI. Dang cho upload on dinh truoc khi dien prompt.")
        for sec in range(10, 61, 10):
            time.sleep(10)
            if sec in (30, 60):
                log(f"INFO: Cho upload: {sec}/60s")

        prompt = v4.build_recap_prompt(keep_sec, drop_sec, language, density, note)
        log(f"INFO: Bat dau dien TOAN BO prompt {len(prompt)} ky tu, khong Enter giua dong.")
        before = len(v4._assistant_elements(driver, provider))
        _submit_prompt(driver, prompt, log)
        answer = v4._wait_new_response(driver, provider, before, wait_seconds, log)

        expected = len(segs)
        got = len(base.parse_srt(answer))
        log(f"INFO: SRT nhan duoc: {got}/{expected} block.")
        if got != expected:
            fix = f"""SRT vừa rồi có {got} block nhưng cần đúng {expected} block. Hãy sửa lại, chỉ xuất SRT thuần.
Đây là mapping do tool đã tính chính xác; mỗi dòng phải có đúng một block và nội dung phải bám cảnh video gốc tương ứng:
{v4.mapping_hint(segs)}
Giữ văn phong recap liền mạch, không bịa."""
            before = len(v4._assistant_elements(driver, provider))
            _submit_prompt(driver, fix, log)
            answer = v4._wait_new_response(driver, provider, before, wait_seconds, log)
            got = len(base.parse_srt(answer))
            log(f"INFO: Sau sua mapping: {got}/{expected} block.")

        exact = v4.force_exact_timeline(answer, segs)
        log(f"INFO: SRT hop le {expected}/{expected}; timeline da khoa theo video sau cat.")

        for p in range(2, max(1, passes) + 1):
            follow = "Kiểm tra lại toàn bộ SRT vừa tạo, sửa nội dung cho bám cảnh và liền mạch như recap hơn. Không thay đổi số block. Chỉ trả về SRT thuần."
            if p == 3:
                follow = "Rà soát lần 3: sửa câu máy móc/lặp, tên nhân vật, ý nghĩa cảnh và mạch nối. Giữ đúng số block. Chỉ trả về SRT."
            elif p >= 4:
                follow = "Rà soát cuối: loại câu bịa/trùng, làm lời kể tự nhiên và liên tục. Giữ đúng số block. Chỉ trả về SRT."
            before = len(v4._assistant_elements(driver, provider))
            _submit_prompt(driver, follow, log)
            candidate = v4._wait_new_response(driver, provider, before, wait_seconds, log)
            try:
                exact = v4.force_exact_timeline(candidate, segs)
                log(f"INFO: Web AI pass {p}/{passes}: hop le")
            except Exception as e:
                log(f"INFO: Pass {p} khong hop le, giu pass truoc: {e}")

        try:
            log(f"INFO: Khoa chat: {driver.current_url}")
        except Exception:
            pass
        log("INFO: Giu nguyen Chrome rieng dang mo de ban xem ket qua; lan sau tool dung lai dung profile nay.")
        return exact
    finally:
        # Deliberately do NOT driver.quit(): this Selenium session is attached to
        # the dedicated Chrome that the user wants to keep and reuse.
        pass


def web_ai_srt_mapped_chunked(video_path: str, provider: str, language: str, keep_sec: float, drop_sec: float,
                              density: str, note: str, wait_seconds: int, profile_dir: str | None,
                              chunk_minutes: int, log=print, passes: int = 1) -> str:
    total = base.duration(video_path)
    all_segs = base.build_segments(total, keep_sec, drop_sec)
    if total <= chunk_minutes * 60 + 1:
        return web_ai_srt_mapped(video_path, provider, language, keep_sec, drop_sec, density, note,
                                 wait_seconds, profile_dir, all_segs, log, passes, True)

    cycle = keep_sec + drop_sec
    cycles_per_chunk = max(1, int((chunk_minutes * 60) // cycle))
    chunk_span = cycles_per_chunk * cycle
    tmp = Path(tempfile.mkdtemp(prefix="recap_web_mapped_chunks_v6_"))
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
            v4._make_chunk(video_path, start, end, str(chunk), log)
            local_total = end - start
            local_segs = base.build_segments(local_total, keep_sec, drop_sec)
            txt = web_ai_srt_mapped(str(chunk), provider, language, keep_sec, drop_sec, density, note,
                                    wait_seconds, profile_dir, local_segs, log, passes, True)
            merged_parts.append(base.shift_srt(txt, out_offset))
            out_offset += v4.output_duration(local_segs)
            start = end
        return "\n\n".join(x.strip() for x in merged_parts if x.strip()) + "\n"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
