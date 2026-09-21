from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import recap_core_v2 as base
import recap_core_v4 as v4
import recap_core_v6 as v6

_SHARED_DRIVER = None


def _driver_alive(driver) -> bool:
    try:
        _ = driver.current_url
        return True
    except Exception:
        return False


def open_tool_browser(profile_dir: str, url: str, log=print) -> int:
    """Mở đúng MỘT Chrome riêng của Vibe Video và tái sử dụng nó về sau."""
    chrome = v4._find_chrome()
    if not chrome:
        raise FileNotFoundError("Không tìm thấy Google Chrome trên máy.")

    profile = str(Path(profile_dir).resolve())
    Path(profile).mkdir(parents=True, exist_ok=True)
    port = v6._choose_debug_port(profile)

    # Nếu Chrome riêng đang chạy, KHÔNG gọi chrome.exe lần nữa để tránh mở thêm cửa sổ/tab.
    if v6._debug_ready(port):
        log(f"INFO: Vibe Video dung lai DUNG Chrome rieng dang mo, port {port}; KHONG mo them cua so.")
        return port

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
    log("INFO: Mo Chrome rieng SACH cua Vibe Video lan dau...")
    subprocess.Popen(args, creationflags=(0x08000000 if os.name == "nt" else 0))
    end = time.time() + 30
    while time.time() < end:
        if v6._debug_ready(port):
            log("INFO: Chrome rieng Vibe Video da san sang. Dang nhap 1 lan, cac lan sau se dung lai.")
            return port
        time.sleep(0.5)
    raise RuntimeError("Chrome riêng đã mở nhưng không bật được cổng điều khiển. Hãy đóng Chrome Vibe Video rồi thử lại.")


def open_automation_driver(profile_dir: str | None, log=print):
    """Bám vào đúng Chrome Vibe Video đang chạy; dùng Selenium Manager theo Chrome hiện tại."""
    global _SHARED_DRIVER
    if _SHARED_DRIVER is not None and _driver_alive(_SHARED_DRIVER):
        log("INFO: Tai su dung CHINH phien Selenium/Chrome cua Vibe Video; khong tao Chrome moi.")
        return _SHARED_DRIVER

    from selenium import webdriver

    profile = str(Path(profile_dir or (base.app_dir() / "chrome_web_profile")).resolve())
    port = open_tool_browser(profile, "https://chatgpt.com/", log)

    opts = webdriver.ChromeOptions()
    opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    chrome = v4._find_chrome()
    if chrome:
        opts.binary_location = chrome

    try:
        _SHARED_DRIVER = webdriver.Chrome(options=opts)
    except Exception as e:
        _SHARED_DRIVER = None
        raise RuntimeError(
            "Không bám được vào Chrome riêng của Vibe Video. Hãy đóng riêng cửa sổ Chrome Vibe Video rồi mở lại từ tool. "
            f"Chi tiết: {e}"
        ) from e

    log("INFO: Selenium da bam vao DUNG Chrome rieng Vibe Video; khong tao profile moi.")
    return _SHARED_DRIVER


def _find_prompt_box_wait(driver, timeout: int = 120):
    from selenium.webdriver.common.by import By

    css = [
        "#prompt-textarea",
        "div#prompt-textarea[contenteditable='true']",
        "div.ProseMirror[contenteditable='true']",
        "[role='textbox'][contenteditable='true']",
        "div[contenteditable='true'][data-lexical-editor='true']",
        "div[contenteditable='true'][data-virtualkeyboard='true']",
        "textarea[placeholder]",
        "textarea",
        "div[contenteditable='true']",
    ]
    end = time.time() + timeout
    while time.time() < end:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

        for sel in css:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for e in reversed(els):
                    if e.is_displayed() and e.is_enabled():
                        return e
            except Exception:
                pass

        # Dự phòng theo role/aria-label khi ChatGPT đổi class.
        try:
            els = driver.find_elements(
                By.XPATH,
                "//*[@contenteditable='true' and (@role='textbox' or contains(@aria-label,'Message') or contains(@aria-label,'Nhắn') or contains(@aria-label,'prompt'))]"
            )
            for e in reversed(els):
                if e.is_displayed() and e.is_enabled():
                    return e
        except Exception:
            pass
        time.sleep(1)
    return None


def _composer_text(box) -> str:
    for attr in ("value", "innerText", "textContent"):
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


def _fill_prompt_all_at_once(driver, prompt: str, log=print):
    """Điền đủ prompt nhiều dòng nhưng tuyệt đối không nhấn Enter giữa chừng."""
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains

    box = _find_prompt_box_wait(driver, 120)
    if box is None:
        raise RuntimeError(
            "Không tìm thấy ô nhập ChatGPT sau 120 giây. Kiểm tra Chrome Vibe Video đã đăng nhập và đang ở trang chat."
        )

    box.click()
    try:
        box.send_keys(Keys.CONTROL, "a")
        box.send_keys(Keys.BACKSPACE)
    except Exception:
        pass

    need = max(20, int(len(prompt.strip()) * 0.90))

    # Cách 1: execCommand insertText thường kích hoạt đúng editor React/ProseMirror.
    try:
        driver.execute_script(
            "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
            box, prompt
        )
        time.sleep(1)
        current = _composer_text(box)
        if len(current.strip()) >= need:
            log(f"INFO: Da dien DU prompt {len(current)} ky tu bang editor; CHUA GUI.")
            return box
    except Exception as e:
        log(f"INFO: Cach dien prompt 1 chua duoc: {e}")

    # Cách 2: cập nhật DOM + phát input/change.
    script = r"""
const el = arguments[0], text = arguments[1];
el.focus();
if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
  const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  setter.call(el, text);
} else {
  el.innerHTML = '';
  for (const line of text.split('\n')) {
    const p = document.createElement('p');
    if (line.length) p.textContent = line; else p.appendChild(document.createElement('br'));
    el.appendChild(p);
  }
}
try { el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text})); }
catch(e) { el.dispatchEvent(new Event('input', {bubbles:true})); }
el.dispatchEvent(new Event('change', {bubbles:true}));
"""
    try:
        driver.execute_script(script, box, prompt)
        time.sleep(1)
        current = _composer_text(box)
        if len(current.strip()) >= need:
            log(f"INFO: Da dien DU prompt {len(current)} ky tu bang DOM; CHUA GUI.")
            return box
    except Exception as e:
        log(f"INFO: Cach dien prompt 2 chua duoc: {e}")

    # Cách 3: gõ theo dòng với Shift+Enter để không submit.
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
    if len(current.strip()) < max(20, int(len(prompt.strip()) * 0.80)):
        raise RuntimeError(
            f"Prompt chưa được điền đủ ({len(current)}/{len(prompt)} ký tự). Vibe Video dừng để không gửi sai."
        )
    log(f"INFO: Da dien DU prompt bang go an toan: {len(current)} ky tu; CHUA GUI.")
    return box


# Thay các hàm nền của V6 bằng bản Vibe ổn định hơn.
v6.open_tool_browser = open_tool_browser
v6.open_automation_driver = open_automation_driver
v6._find_prompt_box_wait = _find_prompt_box_wait
v6._composer_text = _composer_text
v6._fill_prompt_all_at_once = _fill_prompt_all_at_once

web_ai_srt_mapped = v6.web_ai_srt_mapped
web_ai_srt_mapped_chunked = v6.web_ai_srt_mapped_chunked


def xtts_ready():
    py = base.app_dir() / "voice_clone_env" / "Scripts" / "python.exe"
    worker = base.app_dir() / "vibe_voice_worker.py"
    if not py.exists():
        return False, "Chưa cài Voice Clone. Hãy chạy INSTALL-VIBE-VOICE.bat một lần."
    if not worker.exists():
        return False, "Thiếu vibe_voice_worker.py trong thư mục Vibe Video."
    return True, "OK"


def srt_to_wav_xtts(srt_path: str, wav_path: str, sample_audio: str, language_name: str, log=print) -> None:
    ok, msg = xtts_ready()
    if not ok:
        raise RuntimeError(msg)
    if not Path(sample_audio).exists():
        raise FileNotFoundError("Chưa chọn hoặc không tìm thấy audio giọng mẫu.")

    py = base.app_dir() / "voice_clone_env" / "Scripts" / "python.exe"
    worker = base.app_dir() / "vibe_voice_worker.py"
    lang = base.XTTS_LANG.get(language_name, "vi")

    # Ép UTF-8 cho tiến trình con để không còn lỗi cp1252 khi in tiếng Việt.
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    base.run([
        str(py), str(worker),
        "--srt", srt_path,
        "--sample", sample_audio,
        "--out", wav_path,
        "--language", lang,
        "--ffmpeg", base.find_bin("ffmpeg"),
    ], log, cwd=str(base.app_dir()))
